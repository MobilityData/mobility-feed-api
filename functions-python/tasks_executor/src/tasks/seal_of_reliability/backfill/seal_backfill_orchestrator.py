#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""Cloud Tasks producer: fan the Seal of Reliability backfill out across the catalog (#1763).

Enumerates the catalog and chunks it for `backfill_seal_of_reliability`, which only marches an
explicit list. The mechanism is `fanout.plan_fanout`, shared with the nightly producer.

Three differences from the nightly run, all because a march is long: `end_date` is resolved
here once and passed to every worker, or two workers either side of midnight would end on
different days; batches are smaller and the deadline longer; and `only_missing` is the
eligibility predicate rather than a worker-side filter, so a feed the nightly job owns never
has a reconstruction written over it.

Payload (all optional)::

    {
        "dry_run": bool,                  # default True
        "batch_size": int,                # default 100
        "start_date": str | None,         # ISO date, default end_date - days_back
        "end_date": str | None,           # ISO date, default yesterday UTC
        "days_back": int,                 # default 365
        "criteria": [str] | None,         # default None (every implemented criterion)
        "limit": int | None,              # cap total feeds considered, default None
        "stable_feed_ids": [str] | None,  # restrict eligibility to these ids, default None
        "only_missing": bool,             # default True
        "snapshot_mode": str,             # final | all | none, default final
        "resume_from_snapshot": bool,     # default False
        "deadline_seconds": int,          # default 7200 (2h)
        "monitor_delay_seconds": int,     # default 300
    }
"""

import logging
from typing import Any, Dict, List, Optional

from shared.database.database import with_db_session

from tasks.seal_of_reliability.backfill.backfill_seal_of_reliability import _parse_day
from tasks.seal_of_reliability.backfill.seal_backfill import (
    DEFAULT_DAYS_BACK,
    DEFAULT_SNAPSHOT_MODE,
    SNAPSHOT_MODES,
    resolve_window,
)
from tasks.seal_of_reliability.context import (
    count_eligible_feeds,
    iter_eligible_stable_ids,
)
from tasks.seal_of_reliability.fanout import FanoutSpec, plan_fanout

logger = logging.getLogger(__name__)

# Distinct from the nightly run's, so the two never share a tracker.
SEAL_BACKFILL_TASK_NAME = "seal_backfill_run"

# Smaller than the nightly 250: per-batch cost scales with days as well as feeds.
DEFAULT_BATCH_SIZE = 100
DEFAULT_DEADLINE_SECONDS = 2 * 60 * 60  # 2h wall-clock cap for a run
DEFAULT_MONITOR_DELAY_SECONDS = 300

# The monitor is shared with the nightly run, so it has to be told which tracker to settle.
SPEC = FanoutSpec(
    task_name=SEAL_BACKFILL_TASK_NAME,
    worker_task="seal_backfill_worker",
    run_id_prefix="seal-backfill",
    task_prefix="seal-backfill",
    log_name="seal_backfill_orchestrator",
    monitor_extra={"task_name": SEAL_BACKFILL_TASK_NAME},
)


def seal_backfill_orchestrator_handler(payload: dict) -> dict:
    """Entry point for the `seal_backfill_orchestrator` task."""
    payload = payload or {}
    snapshot_mode = payload.get("snapshot_mode", DEFAULT_SNAPSHOT_MODE)
    if snapshot_mode not in SNAPSHOT_MODES:
        raise ValueError(
            f"Unknown snapshot_mode {snapshot_mode!r}. Known modes: {list(SNAPSHOT_MODES)}"
        )

    # Resolved here, so a bad date fails once at the producer rather than once per batch.
    window_start, window_end = resolve_window(
        _parse_day(payload.get("start_date"), "start_date"),
        _parse_day(payload.get("end_date"), "end_date"),
        int(payload.get("days_back", DEFAULT_DAYS_BACK)),
    )

    return _plan_run(
        dry_run=bool(payload.get("dry_run", True)),
        batch_size=int(payload.get("batch_size", DEFAULT_BATCH_SIZE)),
        window_start=window_start,
        window_end=window_end,
        criteria=payload.get("criteria"),
        limit=payload.get("limit"),
        stable_feed_ids=payload.get("stable_feed_ids"),
        only_missing=bool(payload.get("only_missing", True)),
        snapshot_mode=snapshot_mode,
        resume_from_snapshot=bool(payload.get("resume_from_snapshot", False)),
        deadline_seconds=int(payload.get("deadline_seconds", DEFAULT_DEADLINE_SECONDS)),
        monitor_delay_seconds=int(
            payload.get("monitor_delay_seconds", DEFAULT_MONITOR_DELAY_SECONDS)
        ),
    )


@with_db_session
def _plan_run(
    dry_run: bool,
    batch_size: int,
    window_start,
    window_end,
    criteria: Optional[List[str]],
    limit: Optional[int],
    stable_feed_ids: Optional[List[str]],
    only_missing: bool,
    snapshot_mode: str,
    resume_from_snapshot: bool,
    deadline_seconds: int,
    monitor_delay_seconds: int,
    db_session=None,
) -> Dict[str, Any]:
    """Resolve the feeds to backfill, chunk them, and (unless dry_run) fan the run out."""
    window = {
        "start_date": window_start.isoformat(),
        "end_date": window_end.isoformat(),
    }
    settings = {
        "only_missing": only_missing,
        "snapshot_mode": snapshot_mode,
        "resume_from_snapshot": resume_from_snapshot,
    }

    plan = plan_fanout(
        db_session,
        SPEC,
        count_feeds=lambda session: count_eligible_feeds(
            session,
            stable_feed_ids=stable_feed_ids,
            limit=limit,
            exclude_backfilled=only_missing,
        ),
        iter_batches=lambda session, size: iter_eligible_stable_ids(
            session,
            size,
            stable_feed_ids=stable_feed_ids,
            limit=limit,
            exclude_backfilled=only_missing,
        ),
        build_worker_payload=lambda run_id, batch_id, ids: {
            "run_id": run_id,
            "batch_id": batch_id,
            "stable_feed_ids": ids,
            "criteria": criteria,
            **window,
            **settings,
        },
        run_params=lambda run_started_at: {
            "dry_run": False,
            "batch_size": batch_size,
            "criteria": criteria,
            **window,
            **settings,
            "run_started_at": run_started_at,
            "deadline_seconds": deadline_seconds,
        },
        batch_size=batch_size,
        dry_run=dry_run,
        monitor_delay_seconds=monitor_delay_seconds,
    )
    # Echoed back so an operator can see what a dry run resolved to.
    return {**plan, **window, **settings}
