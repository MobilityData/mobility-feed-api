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

"""Cloud Tasks producer: fan a dispatch run out to per-subscription workers.

Triggered by Cloud Scheduler. For each resolved cadence it:
  1. picks a fresh ``run_id`` (cadence + invocation timestamp) so every task name
     is DYNAMIC — re-running never collides with Cloud Tasks' name tombstones;
  2. finds the active subscriptions for that cadence (users DB);
  3. registers the run + one entry per subscription in TaskExecutionTracker
     (feeds DB) and enqueues one ``notifications_dispatch_subscription`` Cloud
     Task each;
  4. enqueues a single ``notifications_dispatch_monitor`` barrier task.

Idempotency is enforced by the DB claim in ``process_subscription`` (lock-free),
not by task-name dedup — so dynamic names are safe.

Payload (all optional)::

    {
        "cadence": "scheduled" | "daily" | "weekly" | "all",
        "weekly_weekday": 0..6,
        "status_filter": "new" | "failed" | "all",
        "max_retries": int, "stale_claim_seconds": int,
        "user_ids": [str], "force": bool, "dry_run": bool,
        "monitor_delay_seconds": int, "deadline_seconds": int
    }
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from shared.database.database import with_db_session
from shared.database.users_database import with_users_db_session
from shared.helpers.task_execution.task_execution_tracker import TaskExecutionTracker
from tasks.notifications.dispatch_notifications import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_STALE_CLAIM_SECONDS,
    DISPATCH_TASK_NAME,
    SCHEDULED_CADENCE,
    _resolve_scheduled_cadences,
    find_subscriptions,
)

logger = logging.getLogger(__name__)

DEFAULT_MONITOR_DELAY_SECONDS = 60
DEFAULT_DEADLINE_SECONDS = 6 * 60 * 60  # 6h wall-clock cap for a run


def notifications_dispatch_plan_handler(payload: dict) -> dict:
    """Entry point for the ``notifications_dispatch_plan`` task."""
    payload = payload or {}
    cadence = payload.get("cadence", SCHEDULED_CADENCE)
    weekly_weekday = int(payload.get("weekly_weekday", 0))
    cadences = _resolve_scheduled_cadences(cadence, weekly_weekday)

    results: Dict[str, Any] = {}
    for run_cadence in cadences:
        results[run_cadence] = _plan_cadence(run_cadence, payload)

    return {"cadences": cadences, "by_cadence": results}


@with_users_db_session
def _plan_cadence(
    run_cadence: str,
    payload: dict,
    db_session=None,
) -> Dict[str, Any]:
    """Fan out a single cadence: enumerate subscriptions and enqueue workers."""
    dry_run = bool(payload.get("dry_run", False))
    status_filter = payload.get("status_filter", "new")
    user_ids: List[str] = payload.get("user_ids", []) or []
    force = bool(payload.get("force", False))
    max_retries = int(payload.get("max_retries", DEFAULT_MAX_RETRIES))
    stale_claim_seconds = int(
        payload.get("stale_claim_seconds", DEFAULT_STALE_CLAIM_SECONDS)
    )
    monitor_delay = int(
        payload.get("monitor_delay_seconds", DEFAULT_MONITOR_DELAY_SECONDS)
    )
    deadline_seconds = int(payload.get("deadline_seconds", DEFAULT_DEADLINE_SECONDS))

    now = datetime.now(timezone.utc)
    run_id = f"{run_cadence}-{now.strftime('%Y%m%dT%H%M%S')}"

    subscriptions = find_subscriptions(
        db_session=db_session,
        cadence=run_cadence,
        user_ids=user_ids,
        force=force,
    )
    subscription_ids = [s.id for s in subscriptions]
    logger.info(
        "plan cadence=%s run_id=%s subscriptions=%d dry_run=%s",
        run_cadence,
        run_id,
        len(subscription_ids),
        dry_run,
    )

    if dry_run or not subscription_ids:
        return {
            "run_id": run_id,
            "subscriptions": len(subscription_ids),
            "enqueued": 0,
            "dry_run": dry_run,
        }

    run_params = {
        "cadence": run_cadence,
        "status_filter": status_filter,
        "max_retries": max_retries,
        "stale_claim_seconds": stale_claim_seconds,
        "run_started_at": now.isoformat(),
        "deadline_seconds": deadline_seconds,
    }
    _start_run(run_id, subscription_ids, run_params)

    enqueued = 0
    for subscription_id in subscription_ids:
        worker_payload = {
            "subscription_id": subscription_id,
            "run_id": run_id,
            "status_filter": status_filter,
            "max_retries": max_retries,
            "stale_claim_seconds": stale_claim_seconds,
        }
        if _enqueue(
            in_body_task="notifications_dispatch_subscription",
            payload=worker_payload,
            queue_env="NOTIFICATION_DISPATCH_QUEUE",
            task_name=_safe_task_name(
                f"notifications-dispatch-{run_id}-{subscription_id}"
            ),
        ):
            enqueued += 1

    # Single barrier/summary task; polls until the run drains, then emits one
    # admin.event_summary. Delayed slightly so it doesn't fire before workers.
    _enqueue(
        in_body_task="notifications_dispatch_monitor",
        payload={"run_id": run_id},
        queue_env="NOTIFICATION_DISPATCH_MONITOR_QUEUE",
        task_name=_safe_task_name(f"notifications-dispatch-monitor-{run_id}"),
        schedule_seconds=monitor_delay,
    )

    return {
        "run_id": run_id,
        "subscriptions": len(subscription_ids),
        "enqueued": enqueued,
        "dry_run": False,
    }


@with_db_session
def _start_run(
    run_id: str,
    subscription_ids: List[str],
    run_params: dict,
    db_session=None,
) -> None:
    """Register the run and one tracked entry per subscription (feeds DB)."""
    tracker = TaskExecutionTracker(
        task_name=DISPATCH_TASK_NAME,
        run_id=run_id,
        db_session=db_session,
    )
    tracker.start_run(total_count=len(subscription_ids), params=run_params)
    for subscription_id in subscription_ids:
        tracker.mark_triggered(subscription_id)
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
