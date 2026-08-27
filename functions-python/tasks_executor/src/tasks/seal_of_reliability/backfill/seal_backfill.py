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
"""Seal of Reliability backfill (issue #1763).

Gives feeds with no seal state a starting one, so the nightly job (#1761) has a "yesterday"
to step from: cold-start each feed at `march_start`, replay the nightly evaluation forward a
day at a time to `end_date`, write only the final day. Marching is what builds the
path-dependent state (grace streaks, probation) the final state depends on. A dry run returns
the plan without writing.

`march_start = max(start_date, feed.created_at)` — skips days before the feed existed, and is
what Stable counts its 180 days from. `end_date` is resolved once by the caller, never per
feed, so every feed of a run ends on the same day.

Two limits, argued in misc/AI/seal_backfill_algorithm_1763.md: Official and Stable have no
history and are read at today's values; and the cold start's error is not bounded by the
window, so `days_back` is a cost/coverage default rather than a correctness guarantee.
"""

import logging
import time as clock
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsfeed, SealCriterion

from tasks.seal_of_reliability.context import (
    FeedSealContext,
    batched,
    collect_inputs,
    is_seal_eligible,
)
from tasks.seal_of_reliability.backfill.simulation import (
    MAX_TRACE_ROWS,
    check_simulation_fits,
    collapse_runs,
    observe,
    parse_simulation,
    policy_for,
    trace_row,
)
from shared.common.seal_criteria import CriterionStatus, SealCriterionName
from tasks.seal_of_reliability.seal_updater import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_MAX_REPORTED_FEEDS,
    SEAL_TABLE,
    SNAPSHOT_STATE_COLUMNS,
    SNAPSHOT_TABLE,
    _load_previous_seals,
    _resolve_evaluators,
    _roll_up_has_seal,
    _upsert_criteria,
    _upsert_criterion_snapshot,
    _validate_requested_feed_ids,
    is_partial_run,
)
from tasks.seal_of_reliability.state_machine import SealCriterionState, transition

logger = logging.getLogger(__name__)

# Days rather than months, so the arithmetic needs no calendar library: 365 is #1763's
# "12 months".
DEFAULT_DAYS_BACK: int = 365

# What to record in seal_criterion_snapshot: only the last day (per #1763), every simulated
# day (millions of rows over a year, but what lets #1803 resume inside the window), or none.
SNAPSHOT_MODES: Tuple[str, ...] = ("final", "all", "none")
DEFAULT_SNAPSHOT_MODE: str = "final"

CRITERION_TABLE = SealCriterion.__table__


def yesterday_utc() -> date:
    """The default `end_date`: the last day that is fully over in UTC."""
    return datetime.now(timezone.utc).date() - timedelta(days=1)


def resolve_window(
    start_date: Optional[date],
    end_date: Optional[date],
    days_back: int,
) -> Tuple[date, date]:
    """Resolve the run-wide window once, so every feed of a run ends on the same day."""
    if days_back <= 0:
        raise ValueError("days_back must be a positive integer")

    resolved_end = end_date or yesterday_utc()
    resolved_start = start_date or (resolved_end - timedelta(days=days_back))

    if resolved_start > resolved_end:
        raise ValueError(
            f"start_date ({resolved_start.isoformat()}) is after end_date "
            f"({resolved_end.isoformat()})"
        )
    return resolved_start, resolved_end


def march_start_for(feed: Gtfsfeed, start_date: date) -> date:
    """The later of the window start and the feed's creation.

    Also the value Stable counts from, and what makes the cold start exact for a feed younger
    than the window: it has no history before its creation to be wrong about.
    """
    created = feed.created_at
    if created is None:  # NOT NULL in the schema; defensive only
        return start_date
    created_day = (
        created.astimezone(timezone.utc).date()
        if created.tzinfo is not None
        else created.date()
    )
    return max(start_date, created_day)


def _feeds_with_seal_state(db_session: Session, feed_ids: Sequence[str]) -> Set[str]:
    """Feeds that already have seal state, which `only_missing` excludes.

    Re-marching a feed the nightly job owns would write a simulation over real history.
    """
    if not feed_ids:
        return set()
    rows = db_session.execute(
        select(CRITERION_TABLE.c.feed_id)
        .where(CRITERION_TABLE.c.feed_id.in_(list(feed_ids)))
        .distinct()
    ).all()
    return {row.feed_id for row in rows}


def day_start(day: date) -> datetime:
    """The `now` a simulated day is evaluated at: midnight UTC.

    Fixed so `snapshot_date_of(now)` is the day itself and probation's `_next_day_start(now)`
    lands on the following midnight, with no rounding to reason about.
    """
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


def days_between(first: date, last: date) -> List[date]:
    """Every day from `first` to `last`, ascending, both ends included."""
    return [first + timedelta(days=offset) for offset in range((last - first).days + 1)]


def _state_from_snapshot(row) -> SealCriterionState:
    """Rebuild a `SealCriterionState` from one snapshot row.

    Columns come from the table rather than a list — the mirror of `_snapshot_row`, which
    writes them — so a new column is read back without editing this, and fails loudly if
    `SealCriterionState` has no field for it.
    """
    values = {}
    for column in SNAPSHOT_STATE_COLUMNS:
        value = getattr(row, column)
        if column in ("observed_status", "confirmed_status"):
            value = CriterionStatus(value)
        values[column] = value
    return SealCriterionState(
        feed_id=row.feed_id,
        criterion=SealCriterionName(row.criterion),
        **values,
    )


def _seed_states(
    db_session: Session,
    feeds: Sequence[Gtfsfeed],
    windows: Dict[str, Tuple[date, date]],
    resume_from_snapshot: bool,
) -> Dict[Tuple[str, str], SealCriterionState]:
    """The state each (feed, criterion) enters its first simulated day with.

    Empty unless `resume_from_snapshot`, which seeds each pair from its latest snapshot
    before that feed's march start — a complete state, so a cold start becomes a resume
    (#1803). Pairs with no snapshot are absent, and cold-start as usual: a resume reaching
    further back than the snapshots go degrades rather than fails.
    """
    if not resume_from_snapshot or not feeds:
        return {}

    # One query for the batch. Each feed has its own cut-off, hence the OR; DISTINCT ON
    # keeps the latest row per pair.
    cutoffs = [
        and_(
            SNAPSHOT_TABLE.c.feed_id == feed.id,
            SNAPSHOT_TABLE.c.snapshot_date < windows[feed.id][0],
        )
        for feed in feeds
        if feed.id in windows
    ]
    if not cutoffs:
        return {}

    rows = db_session.execute(
        select(SNAPSHOT_TABLE)
        .where(or_(*cutoffs))
        .distinct(SNAPSHOT_TABLE.c.feed_id, SNAPSHOT_TABLE.c.criterion)
        .order_by(
            SNAPSHOT_TABLE.c.feed_id,
            SNAPSHOT_TABLE.c.criterion,
            SNAPSHOT_TABLE.c.snapshot_date.desc(),
        )
    ).all()
    return {(row.feed_id, row.criterion): _state_from_snapshot(row) for row in rows}


def _upsert_seals_from_backfill(
    db_session: Session,
    outcomes: Sequence[dict],
    now: datetime,
) -> None:
    """Write feed_reliability_seal for the marched feeds.

    Differs from the nightly `_upsert_seals` only in `created_at`, which is written as the
    feed's march start (left at `DEFAULT now()`, Stable would fail on every simulated day and
    the backfill would grant nothing) and is **insert-only**, so a re-backfill cannot reset a
    countdown already running.

    `seal_earned_at` gets `end_date`. The march knows the day the roll-up flipped, but under
    a cold start that is often day one — which would claim a feed earned its seal a year ago
    on one simulated day.
    """
    for outcome in outcomes:
        row = {
            "feed_id": outcome["feed_id"],
            "has_seal": outcome["has_seal"],
            "created_at": day_start(outcome["tracking_start"]),
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
        # created_at is deliberately not in update_set — see the docstring.
        if "seal_earned_at" in row:
            update_set["seal_earned_at"] = statement.excluded.seal_earned_at
        if "seal_lost_at" in row:
            update_set["seal_lost_at"] = statement.excluded.seal_lost_at
        db_session.execute(
            statement.on_conflict_do_update(
                index_elements=[SEAL_TABLE.c.feed_id], set_=update_set
            )
        )


def _longest_march(windows: Dict[str, Tuple[date, date]]) -> int:
    """Days in the longest window of the run, both ends included.

    Feeds clamped to their own `created_at` march fewer, so this is an upper bound rather
    than a length they all share. It is the report's `days`, and the range a simulated day
    offset has to fall inside. Zero when nothing was selected.
    """
    return max(((end - start).days + 1 for start, end in windows.values()), default=0)


def _march(
    db_session: Session,
    feeds: Sequence[Gtfsfeed],
    windows: Dict[str, Tuple[date, date]],
    evaluators: Sequence,
    end_date: date,
    snapshot_mode: str,
    resume_from_snapshot: bool,
    partial_run: bool,
    simulation: Optional[Dict[str, Dict[int, CriterionStatus]]] = None,
    trace: bool = False,
    write: bool = True,
) -> dict:
    """Replay the nightly evaluation day by day for one batch, and write the final day.

    The evaluation is the nightly job's, unmodified; what this adds is threading each day's
    state into the next in memory, so a year costs one write per feed rather than 366.
    Ascending order is the algorithm, not a convenience: each day feeds the next.
    """
    if not feeds:
        return {
            "feeds": 0,
            "criterion_rows": 0,
            "snapshot_rows": 0,
            "outcomes": [],
            "trace": [],
        }

    marched_days = days_between(min(start for start, _ in windows.values()), end_date)

    # One load per criterion for the whole range; per-day queries would be thousands.
    inputs = collect_inputs(db_session, feeds, marched_days, evaluators)

    states = _seed_states(db_session, feeds, windows, resume_from_snapshot)
    simulation = simulation or {}
    snapshot_rows = 0
    trace_rows: List[dict] = []

    for today in marched_days:
        now = day_start(today)
        # A feed whose march starts later is simply not evaluated yet: its window was
        # clamped to its own created_at, and days before that have nothing to say about it.
        active = [feed for feed in feeds if windows[feed.id][0] <= today]
        if not active:
            continue

        days_states: List[SealCriterionState] = []
        for feed in active:
            # Every day-invariant field on the context is set here, not just the ones the
            # criteria implemented today read: one left out defaults to None and the
            # criterion reading it degrades to a silent UNKNOWN or a wrong FAIL rather than
            # an error. `latest_dataset` and anything else that varies by day arrives
            # through `inputs` instead.
            ctx = FeedSealContext(
                feed_id=feed.id,
                now=now,
                stable_id=feed.stable_id,
                official=feed.official,
                is_producer_url_unstable=feed.is_producer_url_unstable,
                seasonal=feed.seasonal,
                feed_created_at=feed.created_at,
                inputs=inputs,
            )
            offset = (today - windows[feed.id][0]).days
            for evaluator in evaluators:
                key = (feed.id, evaluator.name.value)
                observation = observe(evaluator, ctx, simulation, offset)
                # A simulation may lend a criterion a grace period or probation it does not
                # have, which is the only way Official shows any debouncing at all.
                grace, probation = policy_for(evaluator, simulation)
                states[key] = transition(
                    prev=states.get(key),
                    observation=observation,
                    grace_period=grace,
                    probation_period=probation,
                    now=now,
                    feed_id=feed.id,
                )
                days_states.append(states[key])
                if trace and len(trace_rows) < MAX_TRACE_ROWS:
                    trace_rows.append(
                        trace_row(feed, evaluator, offset, observation, states[key])
                    )

        if write and snapshot_mode == "all":
            # The only mode that writes inside the loop, flushed per day so a year's march
            # does not hold every day in memory.
            _upsert_criterion_snapshot(db_session, days_states, today)
            snapshot_rows += len(days_states)
            db_session.commit()

    final_states = list(states.values())
    outcomes = _final_outcomes(db_session, feeds, windows, states, partial_run)

    if write:
        _upsert_criteria(db_session, final_states, day_start(end_date))
        if snapshot_mode == "final":
            _upsert_criterion_snapshot(db_session, final_states, end_date)
            snapshot_rows += len(final_states)
        if outcomes:
            _upsert_seals_from_backfill(db_session, outcomes, day_start(end_date))
        db_session.commit()

    return {
        "feeds": len(feeds),
        "criterion_rows": len(final_states),
        "snapshot_rows": snapshot_rows,
        "outcomes": outcomes,
        "trace": trace_rows,
    }


def _final_outcomes(
    db_session: Session,
    feeds: Sequence[Gtfsfeed],
    windows: Dict[str, Tuple[date, date]],
    states: Dict[Tuple[str, str], SealCriterionState],
    partial_run: bool,
) -> List[dict]:
    """Roll `has_seal` up from the final day's state, one entry per marched feed.

    Skipped on a partial criteria run, as in `update_seals`: criteria that were not evaluated
    cannot be judged.
    """
    if partial_run:
        return []

    previous = _load_previous_seals(db_session, [feed.id for feed in feeds])
    outcomes = []
    for feed in feeds:
        feed_states = {
            criterion: state
            for (owner_id, criterion), state in states.items()
            if owner_id == feed.id
        }
        had_seal = bool(previous.get(feed.id))
        has_seal = _roll_up_has_seal(feed_states)
        outcomes.append(
            {
                "feed_id": feed.id,
                "stable_id": feed.stable_id,
                "tracking_start": windows[feed.id][0],
                "had_seal": had_seal,
                "has_seal": has_seal,
                # A first evaluation can grant but never revoke: nothing was held to lose.
                "granted": has_seal and not had_seal,
                "revoked": had_seal and not has_seal,
            }
        )
    return outcomes


@with_db_session
def backfill_seals(
    db_session: Session,
    stable_feed_ids: Sequence[str],
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    days_back: int = DEFAULT_DAYS_BACK,
    dry_run: bool = True,
    limit: Optional[int] = None,
    criteria: Optional[Sequence[str]] = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    only_missing: bool = True,
    snapshot_mode: str = DEFAULT_SNAPSHOT_MODE,
    resume_from_snapshot: bool = False,
    max_reported_feeds: int = DEFAULT_MAX_REPORTED_FEEDS,
    simulate: Optional[dict] = None,
    trace: bool = False,
) -> dict:
    """Plan and run the backfill for an explicit list of feeds.

    Enumerating the catalogue is the producer's job, as with `update_seals`. Unknown or
    ineligible ids are skipped with a warning; it raises only if none can be used. See
    `backfill_seal_of_reliability` for the parameters as an operator passes them.

    `simulate` forces observed statuses on named days, and `trace` returns the state each
    day left behind, always collapsed to one entry per unchanged stretch — a year of days is
    mostly repetition, and no caller wanted it row by row. Both are inspection tools and
    neither may write: see the dry_run check below.

    Returns a report; `days` is the longest march in the run, since feeds clamped to their
    own `created_at` march fewer.
    """
    started = clock.monotonic()
    if not stable_feed_ids:
        raise ValueError("stable_feed_ids is required and must be non-empty")
    if simulate and not dry_run:
        # A simulated verdict written to seal_criterion is indistinguishable from an earned
        # one — the row carries no provenance. Refuse rather than quietly downgrade, so an
        # operator cannot believe a real run happened.
        raise ValueError(
            "simulate requires dry_run: forced verdicts must never be written to the seal "
            "tables, where nothing would mark them as simulated"
        )
    if snapshot_mode not in SNAPSHOT_MODES:
        raise ValueError(
            f"Unknown snapshot_mode {snapshot_mode!r}. Known modes: {list(SNAPSHOT_MODES)}"
        )
    if batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")

    window_start, window_end = resolve_window(start_date, end_date, days_back)
    evaluators = _resolve_evaluators(criteria)
    simulation = parse_simulation(simulate, evaluators)

    # By-id load then eligibility in Python, as `update_seals` does: tells "not found" from
    # "found but ineligible" without a second query.
    query = db_session.query(Gtfsfeed).filter(
        Gtfsfeed.stable_id.in_(list(stable_feed_ids))
    )
    if limit is not None:
        query = query.limit(limit)
    feeds = query.all()
    eligible = [feed for feed in feeds if is_seal_eligible(feed)]

    already_backfilled = (
        _feeds_with_seal_state(db_session, [feed.id for feed in eligible])
        if only_missing
        else set()
    )
    selected = [feed for feed in eligible if feed.id not in already_backfilled]

    _validate_requested_feed_ids(
        stable_feed_ids,
        found={feed.stable_id for feed in feeds},
        evaluated={feed.stable_id for feed in eligible},
    )

    windows = {
        feed.id: (march_start_for(feed, window_start), window_end) for feed in selected
    }
    longest_march = _longest_march(windows)
    if simulation:
        check_simulation_fits(simulation, longest_march)

    feed_plans = [
        {
            "stable_id": feed.stable_id,
            "march_start": windows[feed.id][0].isoformat(),
            "end_date": window_end.isoformat(),
            "days": (window_end - windows[feed.id][0]).days + 1,
            # Also Stable's anchor, and what created_at gets on insert.
            "tracking_start": windows[feed.id][0].isoformat(),
        }
        for feed in selected
    ]

    partial_run = is_partial_run(evaluators)

    report = {
        "message": (
            f"{'Planned' if dry_run else 'Ran'} a backfill of {len(selected)} feed(s) "
            f"across {len(evaluators)} criterion/criteria, ending "
            f"{window_end.isoformat()}."
        ),
        "dry_run": dry_run,
        "start_date": window_start.isoformat(),
        "end_date": window_end.isoformat(),
        "days": longest_march,
        "total_feeds": len(selected),
        "skipped_already_backfilled": len(already_backfilled),
        "criteria": [evaluator.name.value for evaluator in evaluators],
        "partial_run": partial_run,
        "only_missing": only_missing,
        "snapshot_mode": snapshot_mode,
        "resume_from_snapshot": resume_from_snapshot,
        "batch_size": batch_size,
        "criterion_rows_written": 0,
        "snapshot_rows_written": 0,
        "seals_granted": 0,
        "seals_revoked": 0,
        "seals_after_run": 0,
        "granted_stable_ids": [],
        "revoked_stable_ids": [],
    }

    # A plain dry run stops at the plan. One asked to simulate or trace has to march —
    # that is the whole point — so it marches with writing suppressed.
    inspecting = bool(simulation) or trace
    if not dry_run or inspecting:
        outcomes: List[dict] = []
        trace_rows: List[dict] = []
        for batch in batched(selected, batch_size):
            result = _march(
                db_session,
                batch,
                windows,
                evaluators,
                window_end,
                "none" if dry_run else snapshot_mode,
                resume_from_snapshot,
                partial_run,
                simulation=simulation,
                trace=trace,
                write=not dry_run,
            )
            if not dry_run:
                report["criterion_rows_written"] += result["criterion_rows"]
                report["snapshot_rows_written"] += result["snapshot_rows"]
            outcomes.extend(result["outcomes"])
            trace_rows.extend(result["trace"])
        if trace:
            report["trace"] = collapse_runs(trace_rows)
            # Counted on the marched days, not on the collapsed entries: the cap is what the
            # march stopped recording, and collapsing happens after.
            report["trace_truncated"] = len(trace_rows) >= MAX_TRACE_ROWS
        if simulation:
            report["simulated"] = {
                criterion: forced.as_reported()
                for criterion, forced in simulation.items()
            }

        granted = [outcome for outcome in outcomes if outcome["granted"]]
        # Only reachable with only_missing=False, but reported anyway so the monitor's
        # aggregate reads the same keys from both fan-outs.
        revoked = [outcome for outcome in outcomes if outcome["revoked"]]
        report["seals_granted"] = len(granted)
        report["seals_revoked"] = len(revoked)
        report["seals_after_run"] = sum(
            1 for outcome in outcomes if outcome["has_seal"]
        )
        report["granted_stable_ids"] = [outcome["stable_id"] for outcome in granted]
        report["revoked_stable_ids"] = [outcome["stable_id"] for outcome in revoked]

    if partial_run:
        report["note"] = (
            "Partial criteria run: has_seal was not recalculated because the criteria "
            "that were not evaluated cannot be judged."
        )

    report["elapsed_seconds"] = round(clock.monotonic() - started, 2)
    report["feeds"] = feed_plans[:max_reported_feeds]
    report["feeds_omitted"] = max(0, len(feed_plans) - max_reported_feeds)

    # Without `feeds`: Cloud Logging drops a LogEntry over 256 KB.
    logger.info(
        "Backfill %s: %s",
        "plan" if dry_run else "complete",
        {key: value for key, value in report.items() if key != "feeds"},
    )

    return report
