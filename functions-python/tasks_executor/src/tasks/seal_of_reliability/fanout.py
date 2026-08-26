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
"""The Cloud Tasks fan-out both seal producers share.

The nightly run (#1800) and the backfill (#1763) differ in what they send a worker and which
feeds they select, but the mechanism between those two points is identical: count, chunk,
register the run, enqueue a worker per batch, reconcile the count against what the stream
actually yielded, enqueue one monitor. That reconciliation is the subtle part — it is what
stops a batch sitting `triggered` until the deadline — and having it in one place is the
reason this module exists.

A producer supplies a `FanoutSpec` (the names and queues it uses) plus three callables: how
to count its feeds, how to stream them, and how to build a worker payload. Everything else is
here.
"""

import json
import logging
import math
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Sequence

from shared.database.database import with_db_session
from shared.helpers.task_execution.task_execution_tracker import TaskExecutionTracker

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FanoutSpec:
    """What distinguishes one producer's fan-out from the other's.

    `monitor_extra` is merged into the monitor's payload. The nightly run needs nothing
    there; the backfill passes its tracker `task_name`, since the two share one monitor.
    """

    task_name: str  # TaskExecutionTracker task_name for the run
    worker_task: str  # in-body task name of the worker to enqueue
    run_id_prefix: str  # run ids are "<prefix>-<UTC timestamp>"
    task_prefix: str  # Cloud Tasks names are "<prefix>-<run_id>-<batch_id>"
    log_name: str  # what this producer calls itself in logs
    queue_env: str = "SEAL_ORCHESTRATOR_QUEUE"
    monitor_queue_env: str = "SEAL_ORCHESTRATOR_MONITOR_QUEUE"
    monitor_task: str = "seal_orchestrator_monitor"
    monitor_extra: Mapping[str, Any] = field(default_factory=dict)


def safe_task_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "-", name)[:500]


def enqueue_task(
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
            "enqueue_task: missing env (PROJECT_ID/GCP_REGION/ENVIRONMENT/%s) — "
            "skipping enqueue of %s",
            queue_env,
            task_name,
        )
        return False

    try:
        from google.cloud import tasks_v2
        from google.protobuf import timestamp_pb2
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
            logger.info("enqueue_task: task %s already exists — skipping", task_name)
            return True
        logger.warning("enqueue_task: could not enqueue %s: %s", task_name, e)
        return False


@with_db_session
def start_run(
    task_name: str,
    run_id: str,
    batch_ids: List[str],
    run_params: dict,
    db_session=None,
) -> None:
    """Register the run and one tracked entry per batch."""
    tracker = TaskExecutionTracker(
        task_name=task_name, run_id=run_id, db_session=db_session
    )
    tracker.start_run(total_count=len(batch_ids), params=run_params)
    for batch_id in batch_ids:
        tracker.mark_triggered(batch_id)
    db_session.commit()


@with_db_session
def mark_enqueue_failed(
    task_name: str,
    run_id: str,
    batch_id: str,
    error_message: str = "enqueue failed",
    db_session=None,
) -> None:
    tracker = TaskExecutionTracker(
        task_name=task_name, run_id=run_id, db_session=db_session
    )
    tracker.mark_failed(batch_id, error_message=error_message)
    db_session.commit()


def new_run_id(spec: FanoutSpec, started_at: datetime) -> str:
    return f"{spec.run_id_prefix}-{started_at.strftime('%Y%m%dT%H%M%S')}"


def _reconcile(
    spec: FanoutSpec,
    run_id: str,
    batch_ids: List[str],
    consumed: int,
    stream: Iterator[List[str]],
) -> None:
    """Settle the difference between the plan-time count and what the stream yielded.

    Both directions come from the same cause: the count and the stream are separate queries,
    so eligibility can move in the gap between them.
    """
    if consumed < len(batch_ids):
        # Fewer chunks than planned. The leftovers are already `triggered` from start_run
        # and would otherwise sit there until the deadline failed the whole run.
        missing = batch_ids[consumed:]
        logger.error(
            "%s: run=%s stream yielded %d batch(es), expected %d — marking %d failed: %s",
            spec.log_name,
            run_id,
            consumed,
            len(batch_ids),
            len(missing),
            missing,
        )
        for batch_id in missing:
            mark_enqueue_failed(
                spec.task_name,
                run_id,
                batch_id,
                error_message="no eligible-feed data for this batch (count/stream mismatch)",
            )
        return

    # zip() with batch_ids (a list) first never calls next() on the stream for a final
    # round once batch_ids is exhausted, so this reflects what is genuinely left over.
    extra_chunk = next(stream, None)
    if extra_chunk is not None:
        # More chunks than planned: feeds became newly eligible in the gap. Log-only —
        # self-healing would mean mutating total_count after start_run fixed it, for a
        # race whose only consequence is a feed waiting for the next run.
        logger.error(
            "%s: run=%s stream had more batches than the plan-time count of %d expected "
            "(>=%d additional feed(s) seen) — those feeds were not processed this run",
            spec.log_name,
            run_id,
            len(batch_ids),
            len(extra_chunk),
        )


def plan_fanout(
    db_session,
    spec: FanoutSpec,
    *,
    count_feeds: Callable[[Any], int],
    iter_batches: Callable[[Any, int], Iterator[List[str]]],
    build_worker_payload: Callable[[str, str, Sequence[str]], dict],
    run_params: Callable[[str], dict],
    batch_size: int,
    dry_run: bool,
    monitor_delay_seconds: int,
) -> Dict[str, Any]:
    """Count, chunk, register, enqueue and reconcile. Returns the plan.

    `run_params` is a callable rather than a dict so a producer can fold in `run_started_at`,
    which is decided here.

    On a dry run — or when nothing is eligible — nothing is registered and nothing is
    enqueued, so the returned plan is purely informational.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")

    run_started_at = datetime.now(timezone.utc)
    total_feeds = count_feeds(db_session)
    num_batches = math.ceil(total_feeds / batch_size) if total_feeds else 0
    run_id = new_run_id(spec, run_started_at)

    logger.info(
        "%s: run=%s total_feeds=%d batch_size=%d batches=%d dry_run=%s",
        spec.log_name,
        run_id,
        total_feeds,
        batch_size,
        num_batches,
        dry_run,
    )

    plan = {
        "run_id": run_id,
        "total_feeds": total_feeds,
        "batch_size": batch_size,
        "batches": num_batches,
        "enqueued": 0,
        "dry_run": dry_run,
    }
    if dry_run or not num_batches:
        return plan

    batch_ids = [f"batch-{index:04d}" for index in range(num_batches)]
    start_run(spec.task_name, run_id, batch_ids, run_params(run_started_at.isoformat()))

    enqueued = 0
    consumed = 0
    stream = iter_batches(db_session, batch_size)
    for batch_id, batch_stable_ids in zip(batch_ids, stream):
        consumed += 1
        if enqueue_task(
            in_body_task=spec.worker_task,
            payload=build_worker_payload(run_id, batch_id, batch_stable_ids),
            queue_env=spec.queue_env,
            task_name=safe_task_name(f"{spec.task_prefix}-{run_id}-{batch_id}"),
        ):
            enqueued += 1
        else:
            # Dead on arrival: don't leave it `triggered` until the deadline.
            mark_enqueue_failed(spec.task_name, run_id, batch_id)

    _reconcile(spec, run_id, batch_ids, consumed, stream)

    # Single barrier task, delayed so it does not fire before any worker has run.
    enqueue_task(
        in_body_task=spec.monitor_task,
        payload={"run_id": run_id, **spec.monitor_extra},
        queue_env=spec.monitor_queue_env,
        task_name=safe_task_name(f"{spec.task_prefix}-monitor-{run_id}"),
        schedule_seconds=monitor_delay_seconds,
    )

    plan["enqueued"] = enqueued
    return plan
