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

"""Cloud Tasks producer: fan the nightly Seal of Reliability evaluation out to
per-batch workers (issue #1800).

`update_seal_of_reliability` only ever evaluates an explicit `stable_feed_ids` list —
there is no run-the-whole-catalogue mode, and pure-SQL evaluation for the whole catalog
in one invocation would eventually hit `tasks_executor`'s own timeout as the catalog
grows. This producer is what enumerates the catalog and chunks it:

  1. resolves every seal-eligible GTFS feed (same eligibility predicate `update_seals`
     itself applies via `context.is_seal_eligible` — see `context.iter_eligible_stable_ids`);
  2. splits the stable_ids into batches of `batch_size`;
  3. registers the run + one entry per batch in TaskExecutionTracker and enqueues one
     `seal_orchestrator_worker` Cloud Task per batch;
  4. enqueues a single `seal_orchestrator_monitor` barrier task.

Batches, not feeds, are the tracked unit: seal evaluation is pure DB work with no
per-feed side effect requiring isolation (unlike notification dispatch, where each
subscription needs an independent send + claim), so one Cloud Task per ~250 feeds
keeps the daily invocation count low while still removing the single-invocation
timeout ceiling entirely.

Payload (all optional)::

    {
        "dry_run": bool,               # default True
        "batch_size": int,             # default 250
        "criteria": [str] | None,      # default None (every implemented criterion)
        "now": str | None,             # ISO timestamp, default current UTC time
        "limit": int | None,           # cap total eligible feeds considered, default None
        "stable_feed_ids": [str] | None,  # restrict eligibility to these ids, default None
        "deadline_seconds": int,       # default 3600 (1h)
        "monitor_delay_seconds": int,  # default 60
    }
"""

import json
import logging
import math
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from shared.database.database import with_db_session
from shared.helpers.task_execution.task_execution_tracker import TaskExecutionTracker

from tasks.seal_of_reliability.context import (
    count_eligible_feeds,
    iter_eligible_stable_ids,
)

logger = logging.getLogger(__name__)

# TaskExecutionTracker task_name for a seal orchestrator run (fan-out workers +
# monitor all key off this plus a per-run run_id).
SEAL_ORCHESTRATOR_TASK_NAME = "seal_orchestrator_run"

DEFAULT_BATCH_SIZE = 250
DEFAULT_DEADLINE_SECONDS = 60 * 60  # 1h wall-clock cap for a run
DEFAULT_MONITOR_DELAY_SECONDS = 60


def seal_orchestrator_handler(payload: dict) -> dict:
    """Entry point for the `seal_orchestrator` task."""
    payload = payload or {}
    dry_run = bool(payload.get("dry_run", True))
    batch_size = int(payload.get("batch_size", DEFAULT_BATCH_SIZE))
    criteria = payload.get("criteria")
    now = payload.get("now")
    limit = payload.get("limit")
    stable_feed_ids = payload.get("stable_feed_ids")
    deadline_seconds = int(payload.get("deadline_seconds", DEFAULT_DEADLINE_SECONDS))
    monitor_delay_seconds = int(
        payload.get("monitor_delay_seconds", DEFAULT_MONITOR_DELAY_SECONDS)
    )

    return _plan_run(
        dry_run=dry_run,
        batch_size=batch_size,
        criteria=criteria,
        now=now,
        limit=limit,
        stable_feed_ids=stable_feed_ids,
        deadline_seconds=deadline_seconds,
        monitor_delay_seconds=monitor_delay_seconds,
    )


@with_db_session
def _plan_run(
    dry_run: bool,
    batch_size: int,
    criteria: Optional[List[str]],
    now: Optional[str],
    limit: Optional[int],
    stable_feed_ids: Optional[List[str]],
    deadline_seconds: int,
    monitor_delay_seconds: int,
    db_session=None,
) -> Dict[str, Any]:
    """Resolve eligible feeds, chunk them, and (unless dry_run) fan the run out."""
    total_feeds = count_eligible_feeds(
        db_session, stable_feed_ids=stable_feed_ids, limit=limit
    )
    num_batches = math.ceil(total_feeds / batch_size) if total_feeds else 0
    run_started_at = datetime.now(timezone.utc)
    run_id = f"seal-{run_started_at.strftime('%Y%m%dT%H%M%S')}"

    logger.info(
        "seal_orchestrator: run=%s total_feeds=%d batch_size=%d batches=%d dry_run=%s",
        run_id,
        total_feeds,
        batch_size,
        num_batches,
        dry_run,
    )

    if dry_run or not num_batches:
        return {
            "run_id": run_id,
            "total_feeds": total_feeds,
            "batch_size": batch_size,
            "batches": num_batches,
            "enqueued": 0,
            "dry_run": dry_run,
        }

    run_params = {
        "dry_run": False,
        "batch_size": batch_size,
        "criteria": criteria,
        "now": now,
        "run_started_at": run_started_at.isoformat(),
        "deadline_seconds": deadline_seconds,
    }
    batch_ids = [f"batch-{index:04d}" for index in range(num_batches)]
    _start_run(run_id, batch_ids, run_params)

    enqueued = 0
    stable_id_batches = iter_eligible_stable_ids(
        db_session, batch_size, stable_feed_ids=stable_feed_ids, limit=limit
    )
    for batch_id, batch_stable_ids in zip(batch_ids, stable_id_batches):
        worker_payload = {
            "run_id": run_id,
            "batch_id": batch_id,
            "stable_feed_ids": batch_stable_ids,
            "criteria": criteria,
            "now": now,
        }
        if _enqueue(
            in_body_task="seal_orchestrator_worker",
            payload=worker_payload,
            queue_env="SEAL_ORCHESTRATOR_QUEUE",
            task_name=_safe_task_name(f"seal-orchestrator-{run_id}-{batch_id}"),
        ):
            enqueued += 1
        else:
            # Dead on arrival: don't leave this batch as `triggered` for the monitor
            # to only notice once the deadline passes.
            _mark_enqueue_failed(run_id, batch_id)

    # Single barrier/summary task; polls until the run drains, then reports.
    # Delayed slightly so it doesn't fire before any worker has had a chance to run.
    _enqueue(
        in_body_task="seal_orchestrator_monitor",
        payload={"run_id": run_id},
        queue_env="SEAL_ORCHESTRATOR_MONITOR_QUEUE",
        task_name=_safe_task_name(f"seal-orchestrator-monitor-{run_id}"),
        schedule_seconds=monitor_delay_seconds,
    )

    return {
        "run_id": run_id,
        "total_feeds": total_feeds,
        "batch_size": batch_size,
        "batches": num_batches,
        "enqueued": enqueued,
        "dry_run": False,
    }


@with_db_session
def _start_run(
    run_id: str,
    batch_ids: List[str],
    run_params: dict,
    db_session=None,
) -> None:
    """Register the run and one tracked entry per batch."""
    tracker = TaskExecutionTracker(
        task_name=SEAL_ORCHESTRATOR_TASK_NAME,
        run_id=run_id,
        db_session=db_session,
    )
    tracker.start_run(total_count=len(batch_ids), params=run_params)
    for batch_id in batch_ids:
        tracker.mark_triggered(batch_id)
    db_session.commit()


@with_db_session
def _mark_enqueue_failed(run_id: str, batch_id: str, db_session=None) -> None:
    tracker = TaskExecutionTracker(
        task_name=SEAL_ORCHESTRATOR_TASK_NAME,
        run_id=run_id,
        db_session=db_session,
    )
    tracker.mark_failed(batch_id, error_message="enqueue failed")
    db_session.commit()


def _safe_task_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "-", name)[:500]


def _enqueue(
    *,
    in_body_task: str,
    payload: dict,
    queue_env: str,
    task_name: str,
    schedule_seconds: int = 0,
) -> bool:
    """Enqueue a Cloud Task targeting the tasks_executor function.

    Returns True on enqueue (or already-exists), False when misconfigured.
    """
    project = os.getenv("PROJECT_ID")
    queue = os.getenv(queue_env)
    gcp_region = os.getenv("GCP_REGION")
    environment = os.getenv("ENVIRONMENT")
    if not all([project, queue, gcp_region, environment]):
        logger.warning(
            "_enqueue: missing env (PROJECT_ID/GCP_REGION/ENVIRONMENT/%s) — "
            "skipping enqueue of %s",
            queue_env,
            task_name,
        )
        return False

    try:
        from google.cloud import tasks_v2
        from google.protobuf import timestamp_pb2
        from datetime import timedelta
        from shared.common.gcp_utils import create_http_task_with_name

        url = (
            f"https://{gcp_region}-{project}.cloudfunctions.net/"
            f"tasks_executor-{environment}"
        )
        body = json.dumps({"task": in_body_task, "payload": payload}).encode()

        schedule_time: Optional[Any] = None
        if schedule_seconds > 0:
            run_at = datetime.now(timezone.utc) + timedelta(seconds=schedule_seconds)
            schedule_time = timestamp_pb2.Timestamp()
            schedule_time.FromDatetime(run_at.replace(tzinfo=None))

        create_http_task_with_name(
            client=tasks_v2.CloudTasksClient(),
            body=body,
            url=url,
            project_id=project,
            gcp_region=gcp_region,
            queue_name=queue,
            task_name=task_name,
            task_time=schedule_time,
            http_method=tasks_v2.HttpMethod.POST,
        )
        return True
    except Exception as e:  # pragma: no cover - network/env dependent
        if "already exists" in str(e).lower() or "ALREADY_EXISTS" in str(e):
            logger.info("_enqueue: task %s already exists — skipping", task_name)
            return True
        logger.warning("_enqueue: could not enqueue %s: %s", task_name, e)
        return False
