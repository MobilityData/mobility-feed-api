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

`backfill_seal_of_reliability` only ever marches an explicit `stable_feed_ids` list. This
producer is what enumerates the catalog and chunks it, the same shape as the nightly
`seal_orchestrator`:

  1. resolves every seal-eligible GTFS feed that has no seal state yet;
  2. splits the stable_ids into batches of `batch_size`;
  3. registers the run + one entry per batch in TaskExecutionTracker and enqueues one
     `seal_backfill_worker` Cloud Task per batch;
  4. enqueues a single `seal_orchestrator_monitor` barrier task, carrying this run's
     `task_name` so the shared monitor settles the right tracker.

Three things differ from the nightly producer, and all three follow from a march being
long where a nightly evaluation is a single day:

* **`end_date` is resolved here, once**, and passed to every worker. Left to each worker to
  default, two workers of the same run started either side of midnight would march to
  different final days and write states that do not correspond to the same moment.
* **Batches are smaller** and the **deadline is longer**. A batch marches a year for each of
  its feeds, not one day.
* **`only_missing` is the eligibility predicate, not a filter the worker applies.** A feed
  the nightly job already owns has real accumulated history, and must not have a simulation
  written over it.

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
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from shared.database.database import with_db_session
from shared.helpers.task_execution.task_execution_tracker import TaskExecutionTracker

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
from tasks.seal_of_reliability.orchestrator.seal_orchestrator import (
    _enqueue,
    _safe_task_name,
)

logger = logging.getLogger(__name__)

# TaskExecutionTracker task_name for a backfill run. Distinct from the nightly run's, so
# the two never share a tracker and the monitor aggregates only its own batches.
SEAL_BACKFILL_TASK_NAME = "seal_backfill_run"

# Smaller than the nightly default of 250: a batch marches every one of its feeds across the
# whole window, so the per-batch cost scales with days as well as feeds.
DEFAULT_BATCH_SIZE = 100
DEFAULT_DEADLINE_SECONDS = 2 * 60 * 60  # 2h wall-clock cap for a run
DEFAULT_MONITOR_DELAY_SECONDS = 300


def seal_backfill_orchestrator_handler(payload: dict) -> dict:
    """Entry point for the `seal_backfill_orchestrator` task."""
    payload = payload or {}
    snapshot_mode = payload.get("snapshot_mode", DEFAULT_SNAPSHOT_MODE)
    if snapshot_mode not in SNAPSHOT_MODES:
        raise ValueError(
            f"Unknown snapshot_mode {snapshot_mode!r}. Known modes: {list(SNAPSHOT_MODES)}"
        )

    # Validated and resolved here rather than in the workers, so a bad date fails the run at
    # the producer instead of once per batch.
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
    if batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")

    run_started_at = datetime.now(timezone.utc)
    total_feeds = count_eligible_feeds(
        db_session,
        stable_feed_ids=stable_feed_ids,
        limit=limit,
        exclude_backfilled=only_missing,
    )
    num_batches = math.ceil(total_feeds / batch_size) if total_feeds else 0
    run_id = f"seal-backfill-{run_started_at.strftime('%Y%m%dT%H%M%S')}"

    logger.info(
        "seal_backfill_orchestrator: run=%s total_feeds=%d batch_size=%d batches=%d "
        "window=%s..%s dry_run=%s",
        run_id,
        total_feeds,
        batch_size,
        num_batches,
        window_start.isoformat(),
        window_end.isoformat(),
        dry_run,
    )

    plan = {
        "run_id": run_id,
        "total_feeds": total_feeds,
        "batch_size": batch_size,
        "batches": num_batches,
        "start_date": window_start.isoformat(),
        "end_date": window_end.isoformat(),
        "only_missing": only_missing,
        "snapshot_mode": snapshot_mode,
        "resume_from_snapshot": resume_from_snapshot,
        "enqueued": 0,
        "dry_run": dry_run,
    }
    if dry_run or not num_batches:
        return plan

    run_params = {
        "dry_run": False,
        "batch_size": batch_size,
        "criteria": criteria,
        "start_date": window_start.isoformat(),
        "end_date": window_end.isoformat(),
        "only_missing": only_missing,
        "snapshot_mode": snapshot_mode,
        "resume_from_snapshot": resume_from_snapshot,
        "run_started_at": run_started_at.isoformat(),
        "deadline_seconds": deadline_seconds,
    }
    batch_ids = [f"batch-{index:04d}" for index in range(num_batches)]
    _start_run(run_id, batch_ids, run_params)

    enqueued = 0
    consumed = 0
    stable_id_batches = iter_eligible_stable_ids(
        db_session,
        batch_size,
        stable_feed_ids=stable_feed_ids,
        limit=limit,
        exclude_backfilled=only_missing,
    )
    for batch_id, batch_stable_ids in zip(batch_ids, stable_id_batches):
        consumed += 1
        worker_payload = {
            "run_id": run_id,
            "batch_id": batch_id,
            "stable_feed_ids": batch_stable_ids,
            "criteria": criteria,
            # Both ends are explicit, so a worker never re-derives the window.
            "start_date": window_start.isoformat(),
            "end_date": window_end.isoformat(),
            "only_missing": only_missing,
            "snapshot_mode": snapshot_mode,
            "resume_from_snapshot": resume_from_snapshot,
        }
        if _enqueue(
            in_body_task="seal_backfill_worker",
            payload=worker_payload,
            queue_env="SEAL_ORCHESTRATOR_QUEUE",
            task_name=_safe_task_name(f"seal-backfill-{run_id}-{batch_id}"),
        ):
            enqueued += 1
        else:
            # Dead on arrival: don't leave this batch as `triggered` for the monitor to
            # only notice once the deadline passes.
            _mark_enqueue_failed(run_id, batch_id)

    if consumed < len(batch_ids):
        # The eligible-feed stream yielded fewer chunks than the plan-time count implied —
        # eligibility narrowed in the gap between the two queries. Fail the leftovers
        # immediately rather than leaving them `triggered` until the deadline.
        missing = batch_ids[consumed:]
        logger.error(
            "seal_backfill_orchestrator: run=%s stream yielded %d batch(es), expected %d "
            "— marking %d failed: %s",
            run_id,
            consumed,
            len(batch_ids),
            len(missing),
            missing,
        )
        for batch_id in missing:
            _mark_enqueue_failed(
                run_id,
                batch_id,
                error_message="no eligible-feed data for this batch (count/stream mismatch)",
            )
    else:
        extra_chunk = next(stable_id_batches, None)
        if extra_chunk is not None:
            # More chunks than planned: feeds became newly eligible in the gap. Log-only —
            # a backfill is operator-triggered, so the fix is to run it again.
            logger.error(
                "seal_backfill_orchestrator: run=%s stream had more batches than the "
                "plan-time count of %d expected (>=%d additional feed(s)) — those feeds "
                "were not backfilled; re-run to pick them up",
                run_id,
                len(batch_ids),
                len(extra_chunk),
            )

    _enqueue(
        in_body_task="seal_orchestrator_monitor",
        payload={"run_id": run_id, "task_name": SEAL_BACKFILL_TASK_NAME},
        queue_env="SEAL_ORCHESTRATOR_MONITOR_QUEUE",
        task_name=_safe_task_name(f"seal-backfill-monitor-{run_id}"),
        schedule_seconds=monitor_delay_seconds,
    )

    plan["enqueued"] = enqueued
    return plan


@with_db_session
def _start_run(
    run_id: str,
    batch_ids: List[str],
    run_params: dict,
    db_session=None,
) -> None:
    """Register the run and one tracked entry per batch."""
    tracker = TaskExecutionTracker(
        task_name=SEAL_BACKFILL_TASK_NAME,
        run_id=run_id,
        db_session=db_session,
    )
    tracker.start_run(total_count=len(batch_ids), params=run_params)
    for batch_id in batch_ids:
        tracker.mark_triggered(batch_id)
    db_session.commit()


@with_db_session
def _mark_enqueue_failed(
    run_id: str,
    batch_id: str,
    error_message: str = "enqueue failed",
    db_session=None,
) -> None:
    tracker = TaskExecutionTracker(
        task_name=SEAL_BACKFILL_TASK_NAME,
        run_id=run_id,
        db_session=db_session,
    )
    tracker.mark_failed(batch_id, error_message=error_message)
    db_session.commit()
