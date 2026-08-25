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

STATUS: the invocation is complete and validated; **the day march itself is not implemented**.
A dry run resolves and returns the full plan — which feeds, which window per feed, how many
days — and a non-dry run raises rather than silently writing nothing. See `_march` below.

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
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsfeed, SealCriterion

from tasks.seal_of_reliability.context import is_seal_eligible
from tasks.seal_of_reliability.seal_updater import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_MAX_REPORTED_FEEDS,
    _resolve_evaluators,
    _validate_requested_feed_ids,
)

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


def _march(
    db_session: Session,
    feeds: Sequence[Gtfsfeed],
    windows: Dict[str, Tuple[date, date]],
    evaluators: Sequence,
    snapshot_mode: str,
    resume_from_snapshot: bool,
) -> List[dict]:
    """Replay the nightly evaluation day by day and write the final state. NOT IMPLEMENTED.

    What this has to do, once built:

    1. Ask each criterion to bulk-load its inputs for the whole day range at once — one load
       per criterion per batch, never one per day. A year marched with per-day queries turns
       a handful of queries into several thousand.
    2. Seed each (feed, criterion) with an empty `SealCriterionState`, or with the state read
       from `seal_criterion_snapshot` at `march_start - 1` when `resume_from_snapshot` is set
       (#1803).
    3. For each day in order, evaluate every criterion and apply `state_machine.transition`,
       threading the returned state into the next day in memory. Nothing is written per day.
    4. Roll up `has_seal` on the final day and upsert `seal_criterion` and
       `feed_reliability_seal`, plus `seal_criterion_snapshot` per `snapshot_mode`.
    5. Write `feed_reliability_seal.created_at = march_start` on insert only, so Stable counts
       from the right day and a re-backfill cannot reset a countdown already running.

    Two behaviours are still undecided and must be settled before this is built:

    * `seal_earned_at` — as `_upsert_seals` stands it would be stamped with the write time,
      so every backfilled feed would look like it earned its seal on backfill day. The march
      knows the day the roll-up actually flipped and could stamp that instead.
    * Whether the evaluators can answer for a past day at all. They currently read the
      current feed row only; each criterion needs to own its own historical lookup first.
    """
    raise NotImplementedError(
        "The Seal of Reliability day march is not implemented yet (#1763). Run with "
        "dry_run=true to resolve and inspect the plan."
    )


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
    """Plan and (once `_march` exists) run the backfill for the requested feeds.

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
        A plan report. `days` is the longest march in the run; feeds clamped to their own
        `created_at` march fewer.
    """
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

    report = {
        "message": (
            f"Planned a backfill of {len(selected)} feed(s) across "
            f"{len(evaluators)} criterion/criteria, ending {window_end.isoformat()}."
        ),
        "dry_run": dry_run,
        "implemented": False,
        "start_date": window_start.isoformat(),
        "end_date": window_end.isoformat(),
        "days": longest_march,
        "total_feeds": len(selected),
        "skipped_already_backfilled": len(already_backfilled),
        "criteria": [evaluator.name.value for evaluator in evaluators],
        "only_missing": only_missing,
        "snapshot_mode": snapshot_mode,
        "resume_from_snapshot": resume_from_snapshot,
        "batch_size": batch_size,
    }
    report["feeds"] = feed_plans[:max_reported_feeds]
    report["feeds_omitted"] = max(0, len(feed_plans) - max_reported_feeds)

    logger.info(
        "Backfill plan: %s",
        {key: value for key, value in report.items() if key != "feeds"},
    )

    if not dry_run:
        # Raise rather than return a report that looks like a completed run. Until `_march`
        # exists there is nothing to write, and reporting success for that would be worse
        # than failing.
        _march(
            db_session,
            selected,
            windows,
            evaluators,
            snapshot_mode,
            resume_from_snapshot,
        )

    return report
