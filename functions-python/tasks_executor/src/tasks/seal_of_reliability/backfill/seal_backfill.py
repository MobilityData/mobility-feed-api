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
to step from: cold-start each feed at `march_start`, replay the nightly evaluation forward to
`end_date`, write only the final day. Marching is what builds the path-dependent state (grace
streaks, probation) the final state depends on.

`march_start = max(start_date, feed.created_at)`, which is also what Stable counts its 180
days from. `end_date` is resolved once by the caller, so every feed of a run ends on the same
day.

The feed is also the unit of recovery: everything a feed's march produces is committed
together once that march is over, and `only_missing` skips a feed only once it holds every
criterion of the run. So re-running an interrupted run finishes it, and re-running a finished
one writes nothing.

On each marched day, a criterion is evaluated only where `seal_criterion_snapshot` holds no
verdict of its own for it. A row already holding PASS, FAIL or NOT_APPLICABLE supplies the
day's `observed_status` and the evaluator is not called; a missing row, or one holding
UNKNOWN or NEVER_EVALUATED, is no verdict, so the evaluator is called. Grace, probation and
the streak are worked out from whichever status was used, day by day, as always.

Two limits, argued in misc/AI/seal_backfill_algorithm_1763.md: Official and Stable have no
history and are read at today's values, and the cold start's error is not bounded by the
window — so `days_back` is a cost decision, not a correctness guarantee.
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
    is_simulated,
    observe,
    parse_simulation,
    policy_for,
    refuse_simulated_write,
    trace_row,
)
from shared.common.seal_criteria import CriterionStatus, SealCriterionName
from tasks.seal_of_reliability.evaluators.base import CriterionObservation
from tasks.seal_of_reliability.seal_updater import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_MAX_REPORTED_FEEDS,
    SEAL_TABLE,
    SNAPSHOT_STATE_COLUMNS,
    SNAPSHOT_TABLE,
    _load_previous_seals,
    _resolve_evaluators,
    _roll_up_has_seal,
    _snapshot_row,
    _upsert_criteria,
    _upsert_criterion_snapshot,
    _validate_requested_feed_ids,
    _write_snapshot_rows,
    is_partial_run,
)
from tasks.seal_of_reliability.state_machine import SealCriterionState, transition

logger = logging.getLogger(__name__)

# Days rather than months, so the arithmetic needs no calendar library: 365 is #1763's
# "12 months".
DEFAULT_DAYS_BACK: int = 365

# What to record in seal_criterion_snapshot: only the last day (per #1763), every marched
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


def _find_fully_backfilled_feeds(
    db_session: Session, feed_ids: Sequence[str], criteria: Sequence[str]
) -> Set[str]:
    """Pick out the feeds already holding a `seal_criterion` row for every one of `criteria`.

    `only_missing` drops them from the run. Every criterion rather than any row, because
    `_march` commits one feed at a time and only once its march is over: a feed holding all
    of them finished, one holding some was interrupted and marches again.
    """
    if not feed_ids or not criteria:
        return set()
    wanted = set(criteria)
    rows = db_session.execute(
        select(CRITERION_TABLE.c.feed_id, CRITERION_TABLE.c.criterion)
        .where(
            CRITERION_TABLE.c.feed_id.in_(list(feed_ids)),
            CRITERION_TABLE.c.criterion.in_(sorted(wanted)),
        )
        .distinct()
    ).all()
    held: Dict[str, Set[str]] = {}
    for row in rows:
        held.setdefault(row.feed_id, set()).add(row.criterion)
    return {
        feed_id for feed_id, criteria_held in held.items() if criteria_held >= wanted
    }


def _load_recorded_observations(
    db_session: Session,
    feed_ids: Sequence[str],
    first_day: date,
    last_day: date,
    criteria: Sequence[str],
) -> Dict[Tuple[str, str, date], CriterionStatus]:
    """Read the verdicts the nightly job already stored for the days this batch will march.

    Returns a dict keyed by (feed id, criterion, day), holding **verdicts only**: PASS, FAIL
    and NOT_APPLICABLE. A day the nightly job stored as UNKNOWN or NEVER_EVALUATED is not a
    verdict and is left out of the dict, exactly like a day it never stored at all.

    So when `_march` looks a day up, there are exactly two cases:

    1. the day **is** in the dict — it uses that status and does not call the evaluator;
    2. the day **is not** in the dict, either because nothing was stored for it or because
       what was stored is UNKNOWN or NEVER_EVALUATED — it calls the evaluator as usual.

    Why prefer a stored verdict: the nightly job checked the feed on the day itself, while a
    backfill can only guess what that day looked like using data available now. When both have
    an answer, the one taken at the time is the better of the two.

    One query for the whole batch. Doing it per day would be thousands of round trips.
    """
    if not feed_ids or not criteria:
        return {}
    rows = db_session.execute(
        select(
            SNAPSHOT_TABLE.c.feed_id,
            SNAPSHOT_TABLE.c.criterion,
            SNAPSHOT_TABLE.c.snapshot_date,
            SNAPSHOT_TABLE.c.observed_status,
        ).where(
            SNAPSHOT_TABLE.c.feed_id.in_(list(feed_ids)),
            SNAPSHOT_TABLE.c.criterion.in_(sorted(set(criteria))),
            SNAPSHOT_TABLE.c.snapshot_date.between(first_day, last_day),
            SNAPSHOT_TABLE.c.observed_status.notin_(
                [
                    CriterionStatus.UNKNOWN.value,
                    CriterionStatus.NEVER_EVALUATED.value,
                ]
            ),
        )
    ).all()
    return {
        (row.feed_id, row.criterion, row.snapshot_date): CriterionStatus(
            row.observed_status
        )
        for row in rows
    }


def day_start(day: date) -> datetime:
    """The `now` a marched day is evaluated at: midnight UTC.

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
    evaluators: Sequence,
    resume_from_snapshot: bool,
) -> Dict[Tuple[str, str], SealCriterionState]:
    """The state each pair (one feed, one criterion) enters its first marched day with.

    Empty unless `resume_from_snapshot`. With it, a pair starts from its latest snapshot
    before that feed's march start — a whole stored state, so the march carries on from it
    instead of cold-starting (#1803). A pair with no snapshot that far back is left out and
    cold-starts as usual, so asking to resume from before the snapshots begin is not an error.

    `_upsert_criteria` writes everything left in `states` at the end of the march, so a
    criterion seeded here but never marched over would be written back at its pre-window
    state, over what the nightly job has recorded since. That is why the result holds only
    the criteria this run marches.
    """
    if not resume_from_snapshot or not feeds:
        return {}

    marched_criteria = [evaluator.name.value for evaluator in evaluators]
    if not marched_criteria:
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
        .where(
            SNAPSHOT_TABLE.c.criterion.in_(marched_criteria),
            or_(*cutoffs),
        )
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

    Differs from the nightly `_upsert_seals` in `created_at` only: the feed's march start,
    since at `DEFAULT now()` Stable would fail on every marched day, and **insert-only**, so a
    re-backfill cannot reset a countdown already running.

    `seal_earned_at` gets `end_date` rather than the day the roll-up flipped, which under a
    cold start is often day one.
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

    An upper bound, not a shared length: feeds clamped to their own `created_at` march fewer.
    It is the report's `days` and the range a simulated offset must fall inside; zero when
    nothing was selected.
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
    """Replay the nightly evaluation for one batch, feed by feed, and write the final day.

    The evaluation is the nightly job's, unmodified; this threads each day's state into the
    next in memory. Ascending order within a feed is the algorithm, not a convenience: each
    day feeds the next. Feeds are independent, so which one marches first changes nothing.

    Each feed's criteria, seal and snapshots are committed together once its own march is
    over, which makes the feed the unit of recovery: an interrupted run leaves finished feeds
    durable and no feed half-written, for `_find_fully_backfilled_feeds` to skip on a restart.
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

    states = _seed_states(db_session, feeds, windows, evaluators, resume_from_snapshot)
    simulation = simulation or {}
    snapshot_rows = 0
    criterion_rows = 0
    trace_rows: List[dict] = []
    outcomes: List[dict] = []
    criterion_names = [evaluator.name.value for evaluator in evaluators]
    # The two queries below run here, before the loop, rather than inside it. Two reasons.
    # One query for the whole batch instead of one per feed. And the loop commits as it goes,
    # so a query moved inside it would start seeing rows this very run has written: seals
    # would look unchanged because we just wrote them, and marched days would look like the
    # nightly job's observations because we just saved them. Read once up front and both stay
    # what they were when the run started.
    feed_ids = [feed.id for feed in feeds]
    previous_seals = _load_previous_seals(db_session, feed_ids)
    recorded_observations = _load_recorded_observations(
        db_session, feed_ids, marched_days[0], end_date, criterion_names
    )

    for feed in feeds:
        feed_start = windows[feed.id][0]
        marched_snapshots: List[dict] = []
        # A feed marches only its own days: its window was clamped to its own created_at,
        # and days before that have nothing to say about it.
        for today in days_between(feed_start, end_date):
            now = day_start(today)
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
            offset = (today - feed_start).days
            days_states: List[SealCriterionState] = []
            for evaluator in evaluators:
                key = (feed.id, evaluator.name.value)
                recorded = (
                    None
                    if is_simulated(simulation, evaluator, offset)
                    else recorded_observations.get(
                        (feed.id, evaluator.name.value, today)
                    )
                )
                if recorded is None:
                    observation = observe(evaluator, ctx, simulation, offset)
                else:
                    # The nightly job read this day on the day itself, so there is nothing to
                    # reconstruct and the evaluator is not called at all. Only the observation
                    # is settled this way: grace, probation and the streak are still worked
                    # out by `transition` below, from this status and the day before it.
                    observation = CriterionObservation(
                        criterion=evaluator.name,
                        observed_status=recorded,
                        reason=f"recorded: {recorded.value} on {today.isoformat()}",
                    )
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
                # Collected rather than written: the whole march goes out as one statement
                # below, instead of a round trip per marched day.
                marched_snapshots.extend(
                    _snapshot_row(state, today) for state in days_states
                )
                snapshot_rows += len(days_states)

        # `states` also holds pairs seeded by `resume_from_snapshot`, so read the feed's own
        # by key rather than filtering the dict; a pair with no marched day and no seed is
        # simply absent.
        feed_states = [
            states[(feed.id, name)]
            for name in criterion_names
            if (feed.id, name) in states
        ]
        if not feed_states:
            # No day of its own inside the window. `backfill_seals` drops such a feed before
            # the batch is built, so this is a guard: without it the feed would still get a
            # seal row, for a stretch it has nothing to say about.
            continue

        outcome = _feed_outcome(feed, windows, feed_states, previous_seals, partial_run)
        if outcome:
            outcomes.append(outcome)

        if write:
            # The feed's whole result in one transaction: its criteria, its seal, and — in
            # "all" mode — every day it marched. Committed here and nowhere else, so the
            # criterion rows a restart reads as "done" cannot outrun the march.
            _write_snapshot_rows(db_session, marched_snapshots)
            _upsert_criteria(db_session, feed_states, day_start(end_date))
            criterion_rows += len(feed_states)
            if snapshot_mode == "final":
                _upsert_criterion_snapshot(db_session, feed_states, end_date)
                snapshot_rows += len(feed_states)
            if outcome:
                _upsert_seals_from_backfill(db_session, [outcome], day_start(end_date))
            db_session.commit()

    return {
        "feeds": len(feeds),
        "criterion_rows": criterion_rows if write else len(states),
        "snapshot_rows": snapshot_rows,
        "outcomes": outcomes,
        "trace": trace_rows,
    }


def _feed_outcome(
    feed: Gtfsfeed,
    windows: Dict[str, Tuple[date, date]],
    feed_states: Sequence[SealCriterionState],
    previous_seals: Dict[str, bool],
    partial_run: bool,
) -> Optional[dict]:
    """Roll `has_seal` up from one feed's final state, for the same transaction that writes it.

    None on a partial criteria run, as in `update_seals`: criteria that were not evaluated
    cannot be judged, so no seal row is written and the feed is left out of the report's
    granted/revoked counts.
    """
    if partial_run:
        return None

    had_seal = bool(previous_seals.get(feed.id))
    has_seal = _roll_up_has_seal(
        {state.criterion.value: state for state in feed_states}
    )
    return {
        "feed_id": feed.id,
        "stable_id": feed.stable_id,
        "tracking_start": windows[feed.id][0],
        "had_seal": had_seal,
        "has_seal": has_seal,
        # A first evaluation can grant but never revoke: nothing was held to lose.
        "granted": has_seal and not had_seal,
        "revoked": had_seal and not has_seal,
    }


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
    collapse_trace: bool = True,
) -> dict:
    """Plan and run the backfill for an explicit list of feeds.

    Enumerating the catalogue is the producer's job, as with `update_seals`. Unknown or
    ineligible ids are skipped with a warning; it raises only if none can be used. See
    `backfill_seal_of_reliability` for the parameters as an operator passes them.

    `simulate` forces observed statuses on named days; `trace` returns the state each day left
    behind, collapsed by default. `collapse_trace=False` returns every day, which is what a
    snapshot would have stored — the ticking fields vary inside a stretch, so the collapsed
    form only brackets them. Neither may write: see the dry_run check below.

    Returns a report; `days` is the longest march in the run.
    """
    started = clock.monotonic()
    if not stable_feed_ids:
        raise ValueError("stable_feed_ids is required and must be non-empty")
    if simulate and not dry_run:
        refuse_simulated_write()
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
        _find_fully_backfilled_feeds(
            db_session,
            [feed.id for feed in eligible],
            [evaluator.name.value for evaluator in evaluators],
        )
        if only_missing
        else set()
    )
    candidates = [feed for feed in eligible if feed.id not in already_backfilled]

    _validate_requested_feed_ids(
        stable_feed_ids,
        found={feed.stable_id for feed in feeds},
        evaluated={feed.stable_id for feed in eligible},
    )

    # A feed created after the window closes has no day inside it to march. Dropped here, or
    # it would come out of the run with a seal row for a stretch it did not exist for.
    windows = {}
    for feed in candidates:
        march_start = march_start_for(feed, window_start)
        if march_start <= window_end:
            windows[feed.id] = (march_start, window_end)
    selected = [feed for feed in candidates if feed.id in windows]
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
        "skipped_created_after_end_date": len(candidates) - len(selected),
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
            report["trace"] = (
                collapse_runs(trace_rows) if collapse_trace else trace_rows
            )
            report["trace_collapsed"] = collapse_trace
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
