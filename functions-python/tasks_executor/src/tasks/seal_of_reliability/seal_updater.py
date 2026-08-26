#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""Nightly Seal of Reliability evaluation (issue #1761).

Reads feed, dataset, validation report and availability data; writes only seal_criterion,
seal_criterion_snapshot and feed_reliability_seal. The source tables are never modified.

The seal tables are written with Core `insert(...).on_conflict_do_update` statements
against `__table__` for bulk upsert.

seal_criterion holds the current state, one row per feed and criterion. seal_criterion_snapshot
records the same state under the day it was evaluated (issue #1809), one row per feed,
criterion and day, so past values survive and a correction can resume from a day rather than
cold-start the window. The job takes the snapshots but never reads them: the state it needs is the
current one.
"""

import logging
import time
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    FeedReliabilitySeal,
    Gtfsfeed,
    SealCriterion,
    SealCriterionSnapshot,
)

from tasks.seal_of_reliability.context import (
    batched,
    build_contexts,
    is_seal_eligible,
)
from tasks.seal_of_reliability.criteria import (
    CriterionPhase,
    CriterionStatus,
    SealCriterionName,
)
from tasks.seal_of_reliability.evaluators import EVALUATORS
from tasks.seal_of_reliability.state_machine import (
    SealCriterionState,
    phase,
    transition,
)

DEFAULT_BATCH_SIZE: int = 200

# Limit the number of feeds reported so the return does not get gigantic.
DEFAULT_MAX_REPORTED_FEEDS: int = 50

SEAL_TABLE = FeedReliabilitySeal.__table__
CRITERION_TABLE = SealCriterion.__table__
SNAPSHOT_TABLE = SealCriterionSnapshot.__table__

# The state columns of a snapshot row: everything but its key. Taken from the table rather than
# listed here, so a column added to seal_criterion_snapshot is written without touching this file
# — and, if it has no matching field on SealCriterionState, fails loudly on the first run
# instead of being silently left NULL.
SNAPSHOT_STATE_COLUMNS: Tuple[str, ...] = tuple(
    column.name
    for column in SNAPSHOT_TABLE.columns
    if column.name not in ("feed_id", "criterion", "snapshot_date")
)


def _resolve_evaluators(criteria: Optional[Sequence[str]]) -> List:
    """Return the evaluators to run, optionally filtered to `criteria`."""
    if criteria is None:
        return list(EVALUATORS)
    wanted = {str(name) for name in criteria}
    known = {evaluator.name.value for evaluator in EVALUATORS}
    unknown = sorted(wanted - known)
    if unknown:
        raise ValueError(
            f"Unknown criteria: {unknown}. Known criteria: {sorted(known)}"
        )
    return [evaluator for evaluator in EVALUATORS if evaluator.name.value in wanted]


def _validate_requested_feed_ids(
    requested: Sequence[str],
    found: Set[str],
    evaluated: Set[str],
) -> None:
    """Warn about requested feeds that will not be evaluated, or raise if that is all of them."""
    unusable = sorted(set(requested) - evaluated)
    if not unusable:
        return  # every requested feed is being evaluated, so there is nothing to report

    # `found` already came from the by-id load, so telling "not found" apart from
    # "found but ineligible" costs nothing extra here.
    unknown = sorted(set(unusable) - found)
    ineligible = sorted(set(unusable) & found)

    problems = []
    if unknown:
        problems.append(f"not found: {unknown}")
    if ineligible:
        problems.append(
            f"not eligible for the seal: {ineligible} (must be gtfs, "
            "operational_status=published, and status not in (deprecated, development))"
        )
    summary = "; ".join(problems)

    if not evaluated:
        # The run did nothing at all, which a log line is too quiet for.
        raise ValueError(f"no requested feed can be evaluated — {summary}")

    # Only a warning, so one stale id does not cost a run over fifty feeds.
    logging.warning("Skipping %d of the requested feed(s): %s", len(unusable), summary)


def _load_previous_states(
    db_session: Session, feed_ids: Sequence[str]
) -> Dict[Tuple[str, str], SealCriterionState]:
    """Map (feed_id, criterion) -> stored state for a batch of feeds."""
    if not feed_ids:
        return {}
    rows = db_session.execute(
        select(CRITERION_TABLE).where(CRITERION_TABLE.c.feed_id.in_(list(feed_ids)))
    ).all()
    return {
        (row.feed_id, row.criterion): SealCriterionState(
            feed_id=row.feed_id,
            criterion=SealCriterionName(row.criterion),
            observed_status=CriterionStatus(row.observed_status),
            confirmed_status=CriterionStatus(row.confirmed_status),
            evaluated_at=row.evaluated_at,
            last_verdict_at=row.last_verdict_at,
            first_observed_failure_at=row.first_observed_failure_at,
            last_observed_failure_at=row.last_observed_failure_at,
            last_confirmed_failure_at=row.last_confirmed_failure_at,
            probation_start=row.probation_start,
        )
        for row in rows
    }


def _load_previous_seals(
    db_session: Session, feed_ids: Sequence[str]
) -> Dict[str, bool]:
    """Map feed_id -> stored has_seal, for feeds that already have a seal row."""
    if not feed_ids:
        return {}
    rows = db_session.execute(
        select(SEAL_TABLE.c.feed_id, SEAL_TABLE.c.has_seal).where(
            SEAL_TABLE.c.feed_id.in_(list(feed_ids))
        )
    ).all()
    return {row.feed_id: bool(row.has_seal) for row in rows}


def _roll_up_has_seal(states: Dict[str, SealCriterionState]) -> bool:
    """True when every criterion in service is a confirmed pass and not on probation.

    A criterion is *in service* when its `confirmed_status` is a verdict. `confirmed_status`
    is only ever PASS, FAIL, NEVER_EVALUATED or NOT_APPLICABLE — never UNKNOWN, since an
    unevaluable run leaves the stored value alone rather than writing UNKNOWN into it (see
    `transition`). So the roll-up only has to skip the two non-verdict values it can see:

    * NEVER_EVALUATED — never produced a verdict, so it is skipped rather than counted as a
      failure. This is what lets the seal be computed before every criterion has a data
      source: one whose source starts collecting later simply is not part of the roll-up.
    * NOT_APPLICABLE — deliberately excluded for this feed, so it is skipped too. This is why
      a seasonal feed is not denied the seal by a criterion that is meaningless for it.

    An unevaluable run (UNKNOWN) does not appear here at all: `transition` has already frozen the
    criterion at its last verdict, so it stays in the roll-up with that verdict if it had
    one, or stays NEVER_EVALUATED and skipped if it never did.

    A criterion IN_GRACE_PERIOD is a confirmed pass and holds the seal.
    One ON_PROBATION denies it.
    """
    in_service = [
        state for state in states.values() if state.confirmed_status.is_verdict
    ]
    if not in_service:
        return False
    return all(
        state.confirmed_status is CriterionStatus.PASS
        and phase(state) is not CriterionPhase.ON_PROBATION
        for state in in_service
    )


def _upsert_criteria(
    db_session: Session, states: Sequence[SealCriterionState], now: datetime
) -> None:
    """Insert or update seal_criterion rows for the given states."""
    if not states:
        return
    payload = [
        {
            "feed_id": state.feed_id,
            "criterion": state.criterion.value,
            "observed_status": state.observed_status.value,
            "confirmed_status": state.confirmed_status.value,
            "evaluated_at": state.evaluated_at,
            "last_verdict_at": state.last_verdict_at,
            "first_observed_failure_at": state.first_observed_failure_at,
            "last_observed_failure_at": state.last_observed_failure_at,
            "last_confirmed_failure_at": state.last_confirmed_failure_at,
            "probation_start": state.probation_start,
            "updated_at": now,
        }
        for state in states
    ]
    statement = insert(CRITERION_TABLE).values(payload)
    db_session.execute(
        statement.on_conflict_do_update(
            index_elements=[CRITERION_TABLE.c.feed_id, CRITERION_TABLE.c.criterion],
            set_={
                "observed_status": statement.excluded.observed_status,
                "confirmed_status": statement.excluded.confirmed_status,
                "evaluated_at": statement.excluded.evaluated_at,
                "last_verdict_at": statement.excluded.last_verdict_at,
                "first_observed_failure_at": statement.excluded.first_observed_failure_at,
                "last_observed_failure_at": statement.excluded.last_observed_failure_at,
                "last_confirmed_failure_at": statement.excluded.last_confirmed_failure_at,
                "probation_start": statement.excluded.probation_start,
                "updated_at": statement.excluded.updated_at,
            },
        )
    )


def snapshot_date_of(now: datetime) -> date:
    """The UTC day a run evaluating at `now` takes its snapshots under.

    Naive values are read as UTC rather than rejected: the entry point normalizes what an
    operator passes, but `update_seals` is also called directly.
    """
    if now.tzinfo is None:
        return now.date()
    return now.astimezone(timezone.utc).date()


def _snapshot_row(state: SealCriterionState, snapshot_date: date) -> dict:
    """One seal_criterion_snapshot row: the key, then the state columns read off by name.

    The column names and the SealCriterionState field names are deliberately the same, which
    is what lets the state columns be taken from the table instead of listed here.
    """
    row = {
        "feed_id": state.feed_id,
        "criterion": state.criterion.value,
        "snapshot_date": snapshot_date,
    }
    for column in SNAPSHOT_STATE_COLUMNS:
        value = getattr(state, column)
        row[column] = value.value if isinstance(value, CriterionStatus) else value
    return row


def _upsert_criterion_snapshot(
    db_session: Session, states: Sequence[SealCriterionState], snapshot_date: date
) -> None:
    """Record the states under `snapshot_date` in seal_criterion_snapshot.

    Same states and same transaction as `_upsert_criteria`, so the two tables cannot
    disagree: a criterion's latest snapshot is its current state.

    The day is the key, so a rerun or a replay of the same day overwrites its row instead of
    adding one — the number of runs in a day leaves no trace. Earlier days are never touched
    by a run evaluating a later one; they are the record.
    """
    if not states:
        return
    payload = [_snapshot_row(state, snapshot_date) for state in states]
    statement = insert(SNAPSHOT_TABLE).values(payload)
    db_session.execute(
        statement.on_conflict_do_update(
            index_elements=[
                SNAPSHOT_TABLE.c.feed_id,
                SNAPSHOT_TABLE.c.criterion,
                SNAPSHOT_TABLE.c.snapshot_date,
            ],
            set_={
                column: getattr(statement.excluded, column)
                for column in SNAPSHOT_STATE_COLUMNS
            },
        )
    )


def _upsert_seals(db_session: Session, outcomes: Sequence[dict], now: datetime) -> None:
    """Insert or update feed_reliability_seal rows.

    A row is written for every evaluated feed, whether or not it qualifies. That matters
    beyond bookkeeping: `created_at` on this row is what a criterion measuring "how long
    have we been tracking this feed" reads, so a feed that does not qualify still needs one,
    or such a criterion could never start counting and the feed could never come to qualify.

    seal_earned_at and seal_lost_at are written only when has_seal actually changes, so
    they record transitions rather than the time of the last evaluation.
    """
    for outcome in outcomes:
        row = {
            "feed_id": outcome["feed_id"],
            "has_seal": outcome["has_seal"],
            "updated_at": now,
        }
        if outcome["granted"]:
            row["seal_earned_at"] = now
        elif outcome["revoked"]:
            row["seal_lost_at"] = now

        statement = insert(SEAL_TABLE).values(**row)
        update_set = {
            "has_seal": statement.excluded.has_seal,
            "updated_at": statement.excluded.updated_at,
        }
        if "seal_earned_at" in row:
            update_set["seal_earned_at"] = statement.excluded.seal_earned_at
        if "seal_lost_at" in row:
            update_set["seal_lost_at"] = statement.excluded.seal_lost_at
        db_session.execute(
            statement.on_conflict_do_update(
                index_elements=[SEAL_TABLE.c.feed_id], set_=update_set
            )
        )


@with_db_session
def update_seals(
    db_session: Session,
    stable_feed_ids: Sequence[str],
    dry_run: bool = True,
    limit: Optional[int] = None,
    criteria: Optional[Sequence[str]] = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    now: Optional[datetime] = None,
    max_reported_feeds: int = DEFAULT_MAX_REPORTED_FEEDS,
) -> dict:
    """Evaluate the seal criteria for the requested feeds and store the result.

    The task always runs against an explicit list of feeds — there is no
    run-the-whole-catalogue mode. Every requested feed is evaluated before anything is
    written, so a dry run exercises exactly the same code path as a real run.

    Args:
        db_session: SQLAlchemy session, injected by @with_db_session.
        stable_feed_ids: The feeds to evaluate. Required and non-empty. Unknown or ineligible
            ids are skipped with a logged warning; it raises only if none can be evaluated.
        dry_run: Evaluate and report without writing. Default True.
        limit: Cap the number of feeds evaluated, from the requested list.
        criteria: Evaluate only these criteria. A partial set skips the has_seal roll-up,
            since the criteria that were not evaluated cannot be judged.
        batch_size: Feeds loaded per query batch.
        now: Evaluation timestamp. Defaults to the current UTC time.
        max_reported_feeds: Cap on the `feeds` list in the report. The count dropped is
            always returned as `feeds_omitted`.

    Returns:
        A report dict.
    """
    if not stable_feed_ids:
        raise ValueError("stable_feed_ids is required and must be non-empty")

    started = time.monotonic()
    now = now or datetime.now(timezone.utc)
    evaluators = _resolve_evaluators(criteria)
    partial_run = len(evaluators) < len(EVALUATORS)

    # Plain by-id load: no eligibility predicate here, since these ids were already
    # explicitly requested. Eligibility is checked in Python below, on the loaded rows.
    query = db_session.query(Gtfsfeed).filter(
        Gtfsfeed.stable_id.in_(list(stable_feed_ids))
    )
    if limit is not None:
        query = query.limit(limit)
    feeds = query.all()
    eligible_feeds = [feed for feed in feeds if is_seal_eligible(feed)]

    _validate_requested_feed_ids(
        stable_feed_ids,
        found={feed.stable_id for feed in feeds},
        evaluated={feed.stable_id for feed in eligible_feeds},
    )

    logging.info(
        "Evaluating %d criterion/criteria for %d feed(s) (dry_run=%s, now=%s).",
        len(evaluators),
        len(eligible_feeds),
        dry_run,
        now.isoformat(),
    )

    all_states: List[SealCriterionState] = []
    outcomes: List[dict] = []
    feed_reports: List[dict] = []
    unknown_count = 0
    not_applicable_count = 0
    first_evaluations = 0

    for batch in batched(eligible_feeds, batch_size):
        batch_ids = [feed.id for feed in batch]
        contexts = build_contexts(db_session, batch, now)
        previous_states = _load_previous_states(db_session, batch_ids)
        previous_seals = _load_previous_seals(db_session, batch_ids)

        for feed in batch:
            ctx = contexts[feed.id]
            feed_states: Dict[str, SealCriterionState] = {}
            criteria_report: List[dict] = []

            for evaluator in evaluators:
                observation = evaluator.evaluate(ctx)
                previous = previous_states.get((feed.id, evaluator.name.value))
                state = transition(
                    prev=previous,
                    observation=observation,
                    grace_period=evaluator.grace_period,
                    probation_period=evaluator.probation_period,
                    now=now,
                    feed_id=feed.id,
                )
                if observation.observed_status is CriterionStatus.UNKNOWN:
                    unknown_count += 1
                elif observation.observed_status is CriterionStatus.NOT_APPLICABLE:
                    not_applicable_count += 1

                # Every run produces a state, including the two no-verdict paths, because
                # `evaluated_at` records the attempt. So every criterion of every evaluated
                # feed is written, not only the ones that moved.
                feed_states[evaluator.name.value] = state
                all_states.append(state)

                # A first *verdict*, not a first row: a criterion whose every earlier run was
                # UNKNOWN already has a row, yet has still never been evaluated.
                if state.last_verdict_at is not None and (
                    previous is None or previous.last_verdict_at is None
                ):
                    first_evaluations += 1

                criteria_report.append(
                    {
                        "criterion": evaluator.name.value,
                        "observed_status": observation.observed_status.value,
                        "confirmed_status": state.confirmed_status.value,
                        "previously_confirmed_status": (
                            previous.confirmed_status.value
                            if previous is not None
                            else None
                        ),
                        "phase": phase(state).value,
                        "reason": observation.reason,
                    }
                )

            if partial_run:
                # No roll-up on a partial run, so there is no seal state to report.
                feed_reports.append(
                    {"stable_id": ctx.stable_id, "criteria": criteria_report}
                )
                continue

            # Merge in any stored criteria this run did not produce a new state for, so the
            # roll-up sees the full set even when an evaluator returned "not evaluable".
            merged = {
                criterion: state
                for (owner_id, criterion), state in previous_states.items()
                if owner_id == feed.id
            }
            merged.update(feed_states)

            # A feed with no seal row yet is treated as not holding one, so a first run can
            # grant the seal but can never withdraw one: nothing was held to lose.
            had_seal = previous_seals.get(feed.id)
            has_seal = _roll_up_has_seal(merged)
            outcome = {
                "feed_id": feed.id,
                "stable_id": ctx.stable_id,
                "had_seal": bool(had_seal),
                "has_seal": has_seal,
                # A first evaluation is a grant if it passes, but it is not a loss if
                # it fails: nothing was held, so nothing was lost. Only these two
                # flags stamp seal_earned_at / seal_lost_at.
                "granted": has_seal and not had_seal,
                "revoked": bool(had_seal) and not has_seal,
            }
            outcomes.append(outcome)

            # Every requested feed is reported, capped at max_reported_feeds below.
            feed_reports.append(
                {
                    "stable_id": ctx.stable_id,
                    "had_seal": outcome["had_seal"],
                    "has_seal": has_seal,
                    "criteria": criteria_report,
                }
            )

    revoked = [outcome for outcome in outcomes if outcome["revoked"]]
    granted = [outcome for outcome in outcomes if outcome["granted"]]
    if not dry_run:
        snapshot_date = snapshot_date_of(now)
        for state_batch in batched(all_states, batch_size):
            _upsert_criteria(db_session, state_batch, now)
            _upsert_criterion_snapshot(db_session, state_batch, snapshot_date)
            db_session.commit()
        for outcome_batch in batched(outcomes, batch_size):
            _upsert_seals(db_session, outcome_batch, now)
            db_session.commit()

    report = {
        "message": (
            f"{'Dry run: evaluated' if dry_run else 'Updated'} {len(eligible_feeds)} "
            f"feed(s) across {len(evaluators)} criterion/criteria."
        ),
        "dry_run": dry_run,
        "evaluated_at": now.isoformat(),
        # The day the snapshots were taken under, which is the day a replay would name to
        # overwrite them.
        "snapshot_date": snapshot_date_of(now).isoformat(),
        "total_feeds": len(eligible_feeds),
        "criteria": [evaluator.name.value for evaluator in evaluators],
        "partial_run": partial_run,
        "criterion_rows_written": 0 if dry_run else len(all_states),
        # Criteria whose inputs were missing this run, and criteria that do not apply to the
        # feed at all. Both are no-verdict outcomes but they are not the same thing: the
        # first freezes a criterion in the roll-up, the second withdraws it.
        "unknown": unknown_count,
        "not_applicable": not_applicable_count,
        "first_evaluations": first_evaluations,
        # seals_before_run + seals_granted - seals_revoked == seals_after_run.
        # On a dry run the "after" figure is what would be stored, not what is.
        "seals_before_run": sum(1 for outcome in outcomes if outcome["had_seal"]),
        "seals_after_run": sum(1 for outcome in outcomes if outcome["has_seal"]),
        "seals_granted": len(granted),
        "seals_revoked": len(revoked),
        # The two transitions in feed_reliability_seal, by feed. Counts alone cannot say
        # which feed moved, and that is the first thing anyone asks of a run.
        "granted_stable_ids": [outcome["stable_id"] for outcome in granted],
        "revoked_stable_ids": [outcome["stable_id"] for outcome in revoked],
        "elapsed_seconds": round(time.monotonic() - started, 2),
    }
    if partial_run:
        report["note"] = (
            "Partial criteria run: has_seal was not recalculated because the criteria "
            "that were not evaluated cannot be judged."
        )
    # A sample, not the record: the two seal tables hold every verdict. The omitted count
    # is always present so a truncated list can never be mistaken for the whole story.
    report["feeds"] = feed_reports[:max_reported_feeds]
    report["feeds_omitted"] = max(0, len(feed_reports) - max_reported_feeds)

    # Log without `feeds`: Cloud Logging drops a LogEntry over 256 KB, so a run naming a
    # few hundred feeds would lose the whole log entry. The counts belong in logs; `feeds`
    # is for the caller reading the response.
    logging.info(
        "Task completed: %s",
        {key: value for key, value in report.items() if key != "feeds"},
    )
    return report
