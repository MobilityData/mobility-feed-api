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

Reads feed, dataset, validation report and availability data; writes only sealcriterion
and feedreliabilityseal. The raw source tables are never modified.

Both seal tables are written with Core statements against `__table__` rather than through
ORM objects. `feedreliabilityseal.feed_id` is both its primary key and a foreign key to
feed(id), which sqlacodegen maps as joined-table inheritance
(`class Feedreliabilityseal(Feed)`, a sibling of Gtfsfeed in the polymorphic hierarchy), so
persisting an ORM instance would try to insert a new feed. Core statements address the
table directly and are unaffected.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Feed,
    Feedreliabilityseal,
    Sealcriterion,
)

from tasks.seal_of_reliability.context import (
    batched,
    build_contexts,
    get_seal_feeds_query,
)
from tasks.seal_of_reliability.criteria import SealCriterionName
from tasks.seal_of_reliability.evaluators import EVALUATORS
from tasks.seal_of_reliability.state_machine import SealCriterionState, transition

DEFAULT_BATCH_SIZE: int = 200

# Limit the number of evaluation reported to so the return does not get gigantic.
DEFAULT_MAX_REPORTED_EVALUATIONS: int = 50

SEAL_TABLE = Feedreliabilityseal.__table__
CRITERION_TABLE = Sealcriterion.__table__


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
    db_session: Session,
    requested: Sequence[str],
    evaluated: Set[str],
) -> None:
    """Warn about requested feeds that will not be evaluated, or raise if that is all of them."""
    unusable = sorted(set(requested) - evaluated)
    if not unusable:
        return  # every requested feed is being evaluated, so there is nothing to report

    # One extra query, and only now that something has already been dropped.
    existing = {
        row.stable_id
        for row in db_session.execute(
            select(Feed.stable_id).where(Feed.stable_id.in_(unusable))
        ).all()
    }
    unknown = sorted(set(unusable) - existing)

    problems = []
    if unknown:
        problems.append(f"not found: {unknown}")
    if existing:
        problems.append(
            f"not eligible for the seal: {sorted(existing)} (must be gtfs, "
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
            observed_pass=row.observed_pass,
            confirmed_pass=row.confirmed_pass,
            evaluated_at=row.evaluated_at,
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

    A criterion is *in service* once it has produced a verdict at any point
    (`observed_pass is not None`). One that never has is skipped rather than counted as a
    failure, which is what lets the seal be computed before every criterion has a data
    source: a criterion whose source only starts collecting later sits at NULL until then
    and simply is not part of the roll-up.

    That waiver is self-limiting because `transition` never writes NULL back, so a
    criterion can only be skipped before its first verdict ever. Once it has produced one it
    stays in the roll-up with its last verdict, and an upstream outage freezes it rather
    than quietly waiving it.

    The non-empty guard stops the roll-up being vacuously true: "every criterion in service
    qualifies" holds trivially for a feed nothing has ever been measured on.

    `confirmed_pass is True` rather than a bare truthiness test is defensive; within the
    in-service set it cannot be NULL, since the two booleans are always written together.
    """
    in_service = [state for state in states.values() if state.observed_pass is not None]
    if not in_service:
        return False
    return all(
        state.confirmed_pass is True and state.probation_start is None
        for state in in_service
    )


def _is_notable(
    previous: Optional[SealCriterionState], state: Optional[SealCriterionState]
) -> bool:
    """True when this evaluation moved a criterion's verdict.

    A first evaluation is not notable on its own: the initial run over the whole catalogue
    would otherwise report every feed, which is exactly the unbounded payload this is meant
    to avoid. The `first_evaluations` count covers that case instead. A first evaluation
    that lands on a failure *is* reported, since that is the actionable half.
    """
    if state is None:
        return False
    if previous is None:
        return state.observed_pass is False or state.confirmed_pass is False
    return (
        state.observed_pass != previous.observed_pass
        or state.confirmed_pass != previous.confirmed_pass
    )


def _upsert_criteria(
    db_session: Session, states: Sequence[SealCriterionState], now: datetime
) -> None:
    """Insert or update sealcriterion rows for the given states."""
    if not states:
        return
    payload = [
        {
            "feed_id": state.feed_id,
            "criterion": state.criterion.value,
            "observed_pass": state.observed_pass,
            "confirmed_pass": state.confirmed_pass,
            "evaluated_at": state.evaluated_at,
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
                "observed_pass": statement.excluded.observed_pass,
                "confirmed_pass": statement.excluded.confirmed_pass,
                "evaluated_at": statement.excluded.evaluated_at,
                "first_observed_failure_at": statement.excluded.first_observed_failure_at,
                "last_observed_failure_at": statement.excluded.last_observed_failure_at,
                "last_confirmed_failure_at": statement.excluded.last_confirmed_failure_at,
                "probation_start": statement.excluded.probation_start,
                "updated_at": statement.excluded.updated_at,
            },
        )
    )


def _upsert_seals(db_session: Session, outcomes: Sequence[dict], now: datetime) -> None:
    """Insert or update feedreliabilityseal rows.

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
    dry_run: bool = True,
    stable_feed_ids: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
    criteria: Optional[Sequence[str]] = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    now: Optional[datetime] = None,
    max_reported_evaluations: int = DEFAULT_MAX_REPORTED_EVALUATIONS,
) -> dict:
    """Evaluate the seal criteria for every eligible feed and store the result.

    Every feed is evaluated before anything is written, so a dry run exercises exactly the
    same code path as a real run.

    Args:
        db_session: SQLAlchemy session, injected by @with_db_session.
        dry_run: Evaluate and report without writing. Default True.
        stable_feed_ids: Evaluate only these feeds. Unknown or ineligible ids are skipped
            with a logged warning; it raises only if none of them can be evaluated. When
            given, `evaluations` reports every criterion of those feeds rather than only
            the ones whose verdict moved.
        limit: Cap the number of feeds evaluated.
        criteria: Evaluate only these criteria. A partial set skips the has_seal roll-up,
            since the criteria that were not evaluated cannot be judged.
        batch_size: Feeds loaded per query batch.
        now: Evaluation timestamp. Defaults to the current UTC time.
        max_reported_evaluations: Cap on the `evaluations` list in the report. The count dropped is
            always returned as `evaluations_omitted`.

    Returns:
        A report dict.
    """
    started = time.monotonic()
    now = now or datetime.now(timezone.utc)
    evaluators = _resolve_evaluators(criteria)
    partial_run = len(evaluators) < len(EVALUATORS)

    query = get_seal_feeds_query(db_session, stable_feed_ids=stable_feed_ids)
    if limit is not None:
        query = query.limit(limit)
    feeds = query.all()

    if stable_feed_ids is not None:
        _validate_requested_feed_ids(
            db_session, stable_feed_ids, {feed.stable_id for feed in feeds}
        )

    logging.info(
        "Evaluating %d criterion/criteria for %d feed(s) (dry_run=%s, now=%s).",
        len(evaluators),
        len(feeds),
        dry_run,
        now.isoformat(),
    )

    all_states: List[SealCriterionState] = []
    outcomes: List[dict] = []
    evaluations: List[dict] = []
    not_evaluable = 0
    first_evaluations = 0

    for batch in batched(feeds, batch_size):
        batch_ids = [feed.id for feed in batch]
        contexts = build_contexts(db_session, batch, now)
        previous_states = _load_previous_states(db_session, batch_ids)
        previous_seals = _load_previous_seals(db_session, batch_ids)

        for feed in batch:
            ctx = contexts[feed.id]
            feed_states: Dict[str, SealCriterionState] = {}

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
                if observation.observed_pass is None:
                    not_evaluable += 1
                if state is not None:
                    feed_states[evaluator.name.value] = state
                    if state is not previous:
                        all_states.append(state)
                if previous is None and state is not None:
                    first_evaluations += 1

                # `evaluations` reports the notable outcomes, not one entry per
                # evaluation: a criterion whose verdict moved, or every criterion of a feed
                # the caller named explicitly. One entry per feed per criterion would grow
                # with the catalogue (~424 bytes each, so megabytes for a full run) and is
                # what the sealcriterion table is for. This matches `failures` in
                # check_gtfs_feed_availability and `dispatched` in backfill_changelog.
                named = stable_feed_ids is not None
                if named or _is_notable(previous, state):
                    evaluations.append(
                        {
                            "stable_id": ctx.stable_id,
                            "criterion": evaluator.name.value,
                            "observed_pass": observation.observed_pass,
                            "confirmed_pass": (
                                state.confirmed_pass if state is not None else None
                            ),
                            "previously_confirmed_pass": (
                                previous.confirmed_pass
                                if previous is not None
                                else None
                            ),
                            "on_probation": (
                                state.probation_start is not None
                                if state is not None
                                else None
                            ),
                            "reason": observation.reason,
                        }
                    )

            if partial_run:
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
            outcomes.append(
                {
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
            )

    revoked = [outcome for outcome in outcomes if outcome["revoked"]]
    granted = [outcome for outcome in outcomes if outcome["granted"]]
    if not dry_run:
        for state_batch in batched(all_states, batch_size):
            _upsert_criteria(db_session, state_batch, now)
            db_session.commit()
        for outcome_batch in batched(outcomes, batch_size):
            _upsert_seals(db_session, outcome_batch, now)
            db_session.commit()

    report = {
        "message": (
            f"{'Dry run: evaluated' if dry_run else 'Updated'} {len(feeds)} feed(s) "
            f"across {len(evaluators)} criterion/criteria."
        ),
        "dry_run": dry_run,
        "evaluated_at": now.isoformat(),
        "total_feeds": len(feeds),
        "criteria": [evaluator.name.value for evaluator in evaluators],
        "partial_run": partial_run,
        "criterion_rows_written": 0 if dry_run else len(all_states),
        "not_evaluable": not_evaluable,
        "first_evaluations": first_evaluations,
        # seals_before_run + seals_granted - seals_revoked == seals_after_run.
        # On a dry run the "after" figure is what would be stored, not what is.
        "seals_before_run": sum(1 for outcome in outcomes if outcome["had_seal"]),
        "seals_after_run": sum(1 for outcome in outcomes if outcome["has_seal"]),
        "seals_granted": len(granted),
        "seals_revoked": len(revoked),
        # The two transitions in feedreliabilityseal, by feed. Counts alone cannot say
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
    # A sample, not the record: sealcriterion holds every verdict. The omitted count is
    # always present so a truncated list can never be mistaken for the whole story.
    report["evaluations"] = evaluations[:max_reported_evaluations]
    report["evaluations_omitted"] = max(0, len(evaluations) - max_reported_evaluations)

    # Log without `evaluations`: Cloud Logging drops a LogEntry over 256 KB, so a run
    # naming a few hundred feeds would lose the whole log entry. The counts belong in logs;
    # `evaluations` is for the caller reading the response.
    logging.info(
        "Task completed: %s",
        {key: value for key, value in report.items() if key != "evaluations"},
    )
    return report
