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

Establishes a starting seal state for feeds that have none, so the nightly job (#1761) has a
"yesterday" to step from. For each feed it cold-starts at `march_start`, replays the nightly
evaluation forward one day at a time to `end_date`, and writes only the final day. The
intermediate days are held in memory and discarded — marching forward is what builds up the
path-dependent state (grace-period streaks, probation) that makes the final state right.

A dry run resolves and returns the plan — which feeds, which window per feed, how many days —
without marching or writing anything.

Per-feed window
---------------
`march_start = max(start_date, feed.created_at)`. Clamping to the feed's own creation date
does two things: it skips days before the feed existed, and it is the value the Stable
criterion measures its 180 days from. A feed younger than the window therefore gets an exact
cold start rather than a guessed one — there is no history before its creation to be wrong
about.

`end_date` is resolved once by the caller and passed down, never recomputed per feed. Two
workers of the same run started either side of midnight would otherwise march to different
final days.

What the backfill cannot know
-----------------------------
Official and Stable have no historical record, so they can only be evaluated against their
current values. Neither has a grace period or probation, so a wrong value on a past day does
not propagate into the days after it (see #1763).

The cold start assumes an empty prior state — no failure streak, no probation — which may not
match reality for a feed whose history is truncated by `start_date`. Errors from that
assumption are not bounded by the window: a single observed failure inside it can extend the
divergence by another probation period, and repeatedly. The window is therefore a
cost/coverage default, not a correctness guarantee.
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
from tasks.seal_of_reliability.criteria import CriterionStatus, SealCriterionName
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

# How far back the window reaches when `start_date` is not given. Expressed in days rather
# than months so the arithmetic is exact and needs no calendar library: 365 is the "12 months"
# of #1763. It is roughly twice the 180-day probation period, which is where the number came
# from — but see the module docstring: that reasoning bounds nothing, so treat this as a
# default for how much history to replay rather than as a correctness threshold.
DEFAULT_DAYS_BACK: int = 365

# What to record in seal_criterion_snapshot.
#   final — only the last day's state, per #1763. The intermediate days are discarded.
#   all   — every simulated day. Costs len(days) x feeds x criteria rows, which is millions
#           over a year, but it is what would let #1803 resume inside the backfilled window
#           instead of cold-starting again.
#   none  — write nothing to the snapshot table.
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
    """Resolve the run-wide window, applying defaults and rejecting a nonsensical one.

    Resolved once for the whole run rather than per feed, so every feed of a run marches to
    the same final day whatever time the run started or how long it takes.
    """
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
    """Where this feed's march begins: the later of the window start and its creation.

    Clamping to `feed.created_at` is not only an optimisation. It is also the value the
    Stable criterion counts its 180 days from, and it is what makes the cold start exact for
    a feed younger than the window: such a feed has no history before its creation, so the
    empty starting state is the truth rather than an assumption.
    """
    created = feed.created_at
    if created is None:
        # created_at is NOT NULL in the schema, so this is defensive only: a feed with no
        # creation date gets the full window rather than being skipped.
        return start_date
    created_day = (
        created.astimezone(timezone.utc).date()
        if created.tzinfo is not None
        else created.date()
    )
    return max(start_date, created_day)


def _feeds_with_seal_state(db_session: Session, feed_ids: Sequence[str]) -> Set[str]:
    """The subset of `feed_ids` that already has at least one seal_criterion row.

    `only_missing` filters on this: #1763 backfills feeds that have no stored state to carry
    forward, and re-running the march over a feed the nightly job already owns would throw
    away real history in favour of a simulation of it.
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

    A fixed time of day, so that `snapshot_date_of(now)` is the day itself and
    `_next_day_start(now)` — which probation uses — lands on the following midnight with no
    rounding to reason about. The nightly job's own `now` is whatever time it ran; the march
    only has to be consistent with itself and day-aligned.
    """
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


def days_between(first: date, last: date) -> List[date]:
    """Every day from `first` to `last`, ascending, both ends included."""
    return [first + timedelta(days=offset) for offset in range((last - first).days + 1)]


def _state_from_snapshot(row) -> SealCriterionState:
    """Rebuild a `SealCriterionState` from one seal_criterion_snapshot row.

    The state columns are taken from the table rather than listed, the mirror of
    `seal_updater._snapshot_row` which writes them: a column added to the snapshot table is
    read back without touching this function, and fails loudly here if `SealCriterionState`
    has no field for it rather than being silently dropped.
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

    Empty unless `resume_from_snapshot`, in which case each pair is seeded from its latest
    snapshot strictly before that feed's march start — a complete state, which is what turns
    a cold start into a resume (#1803).

    Pairs with no snapshot are simply absent from the result, and `transition` builds them
    from nothing on their first day, exactly as a cold start would. A resume that reaches
    further back than the snapshots go therefore degrades to a cold start for those criteria
    rather than failing.
    """
    if not resume_from_snapshot or not feeds:
        return {}

    # One query for the batch. Each feed has its own cut-off, so the conditions are OR-ed
    # rather than sharing a single date; DISTINCT ON keeps the latest row per pair.
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

    Two things differ from the nightly job's `_upsert_seals`, and both are about
    `created_at`:

    * It is written explicitly, as the feed's march start rather than the write time. That
      column is what the Stable criterion counts its 180 days from, so left at its
      `DEFAULT now()` every backfilled feed would fail Stable on every simulated day and the
      backfill would grant no seals at all.
    * It is **insert-only**, absent from the conflict clause. A re-backfill of a feed the
      nightly job already owns must not reset a countdown that has been running for real.

    `seal_earned_at` is stamped with `now` — the run's end_date — for a feed the backfill
    grants. The march does know the day the roll-up flipped, but under a cold start that day
    is often the very first simulated one, which would claim a feed earned its seal a year
    ago on the strength of a single simulated day. `end_date` says only that the seal record
    begins here, which is exactly what a backfill establishes.
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


def _march(
    db_session: Session,
    feeds: Sequence[Gtfsfeed],
    windows: Dict[str, Tuple[date, date]],
    evaluators: Sequence,
    end_date: date,
    snapshot_mode: str,
    resume_from_snapshot: bool,
    partial_run: bool,
) -> dict:
    """Replay the nightly evaluation day by day for one batch, and write the final day.

    The evaluation itself is the nightly job's, unmodified: `transition` is called once per
    feed, criterion and day with `now` set to that day. What this adds is that the returned
    state is threaded into the next day in memory instead of being written, so a year's march
    costs one write per feed rather than three hundred and sixty-five.

    Ascending day order is not a convenience, it is the algorithm — each day's state is the
    input to the next.
    """
    if not feeds:
        return {"feeds": 0, "criterion_rows": 0, "snapshot_rows": 0, "outcomes": []}

    marched_days = days_between(min(start for start, _ in windows.values()), end_date)

    # One load per criterion for the whole batch and the whole range. A criterion querying
    # per day would turn this into several thousand queries; see `CriterionEvaluator.load_inputs`.
    inputs = collect_inputs(db_session, feeds, marched_days, evaluators)

    states = _seed_states(db_session, feeds, windows, resume_from_snapshot)
    snapshot_rows = 0

    for today in marched_days:
        now = day_start(today)
        # A feed whose march starts later is simply not evaluated yet: its window was
        # clamped to its own created_at, and days before that have nothing to say about it.
        active = [feed for feed in feeds if windows[feed.id][0] <= today]
        if not active:
            continue

        days_states: List[SealCriterionState] = []
        for feed in active:
            ctx = FeedSealContext(
                feed_id=feed.id,
                now=now,
                stable_id=feed.stable_id,
                official=feed.official,
                inputs=inputs,
            )
            for evaluator in evaluators:
                key = (feed.id, evaluator.name.value)
                states[key] = transition(
                    prev=states.get(key),
                    observation=evaluator.evaluate(ctx),
                    grace_period=evaluator.grace_period,
                    probation_period=evaluator.probation_period,
                    now=now,
                    feed_id=feed.id,
                )
                days_states.append(states[key])

        if snapshot_mode == "all":
            # The expensive mode, and the only one that writes inside the loop. Flushed per
            # day rather than accumulated so a year's march does not hold every day's state
            # in memory at once.
            _upsert_criterion_snapshot(db_session, days_states, today)
            snapshot_rows += len(days_states)
            db_session.commit()

    final_states = list(states.values())
    outcomes = _final_outcomes(db_session, feeds, windows, states, partial_run)

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
    }


def _final_outcomes(
    db_session: Session,
    feeds: Sequence[Gtfsfeed],
    windows: Dict[str, Tuple[date, date]],
    states: Dict[Tuple[str, str], SealCriterionState],
    partial_run: bool,
) -> List[dict]:
    """Roll `has_seal` up from the final day's state, one entry per marched feed.

    Skipped entirely on a partial criteria run, mirroring `update_seals`: criteria that were
    not evaluated cannot be judged, so the roll-up would be answering a question it has only
    part of the evidence for.
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
                # A first evaluation is a grant if it passes, but not a loss if it fails:
                # nothing was held, so nothing was lost.
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
) -> dict:
    """Plan and run the backfill for the requested feeds.

    Like `update_seals`, this always runs against an explicit list of feeds — enumerating the
    catalogue is a producer's job, not this function's.

    Args:
        db_session: SQLAlchemy session, injected by @with_db_session.
        stable_feed_ids: The feeds to backfill. Required and non-empty. Unknown or ineligible
            ids are skipped with a logged warning; it raises only if none can be used.
        start_date: First day of the window. Clamped up to each feed's `created_at`. Defaults
            to `end_date - days_back`.
        end_date: Last day simulated, and the day the written state belongs to. Defaults to
            yesterday UTC. Resolved once here so every feed of a run ends on the same day.
        days_back: Window length used when `start_date` is absent. Default 365.
        dry_run: Resolve and return the plan without marching or writing. Default True.
        limit: Cap the number of feeds, applied to the requested list.
        criteria: Backfill only these criteria. Same names as the nightly task.
        batch_size: Feeds loaded and marched per batch.
        only_missing: Skip feeds that already have seal state, which is #1763's stated scope.
            Set False to re-backfill a feed and overwrite what is stored.
        snapshot_mode: One of `SNAPSHOT_MODES` — how much of the march to record in
            seal_criterion_snapshot. Default "final".
        resume_from_snapshot: Seed each criterion from its snapshot at `march_start - 1`
            rather than cold-starting empty. The #1803 hook; requires snapshots to exist.
        max_reported_feeds: Cap on the `feeds` list in the report.

    Returns:
        A report. `days` is the longest march in the run; feeds clamped to their own
        `created_at` march fewer.
    """
    started = clock.monotonic()
    if not stable_feed_ids:
        raise ValueError("stable_feed_ids is required and must be non-empty")
    if snapshot_mode not in SNAPSHOT_MODES:
        raise ValueError(
            f"Unknown snapshot_mode {snapshot_mode!r}. Known modes: {list(SNAPSHOT_MODES)}"
        )
    if batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")

    window_start, window_end = resolve_window(start_date, end_date, days_back)
    evaluators = _resolve_evaluators(criteria)

    # Plain by-id load, then eligibility in Python on the loaded rows — the same shape as
    # `update_seals`, so a feed that does not exist can be told apart from one that exists
    # but is not eligible without a second query.
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
    longest_march = (
        max((end - start).days + 1 for start, end in windows.values()) if windows else 0
    )

    feed_plans = [
        {
            "stable_id": feed.stable_id,
            "march_start": windows[feed.id][0].isoformat(),
            "end_date": window_end.isoformat(),
            "days": (window_end - windows[feed.id][0]).days + 1,
            # The march start doubles as the Stable criterion's anchor, and is what
            # feed_reliability_seal.created_at will be set to on insert.
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

    if not dry_run:
        outcomes: List[dict] = []
        for batch in batched(selected, batch_size):
            result = _march(
                db_session,
                batch,
                windows,
                evaluators,
                window_end,
                snapshot_mode,
                resume_from_snapshot,
                partial_run,
            )
            report["criterion_rows_written"] += result["criterion_rows"]
            report["snapshot_rows_written"] += result["snapshot_rows"]
            outcomes.extend(result["outcomes"])

        granted = [outcome for outcome in outcomes if outcome["granted"]]
        # A backfill can only revoke when only_missing is False, since a feed with no
        # stored seal held nothing to lose. Reported anyway so the run-level aggregate in
        # `seal_orchestrator_monitor` reads the same keys from both fan-outs.
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

    # Logged without `feeds`: Cloud Logging drops a LogEntry over 256 KB, so a run naming a
    # few hundred feeds would lose the whole entry.
    logger.info(
        "Backfill %s: %s",
        "plan" if dry_run else "complete",
        {key: value for key, value in report.items() if key != "feeds"},
    )

    return report
