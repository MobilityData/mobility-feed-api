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

"""Cloud Tasks barrier/monitor: emit one admin summary when a run has drained.

A single ``notifications_dispatch_monitor`` task is enqueued per run by the
producer. It uses the Cloud Tasks queue's NATIVE retry to poll: while workers
are still in flight (and within the run deadline) it raises
``TaskInProgressError`` → HTTP 503 so the queue retries it after its configured
backoff. Once every worker has reported (``triggered == 0``) — or the deadline
passes — it aggregates the run's delivery stats from ``notification_log`` and
emits exactly one ``admin.event_summary`` notification_event, then marks the run
complete so a redelivery is a no-op.

Requires the monitor queue to be configured with unlimited attempts and a pinned
backoff (see Terraform). The in-handler deadline guards against a never-draining
run polling forever.

Payload::

    { "run_id": str }   # required
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from shared.database.database import with_db_session
from shared.database.users_database import with_users_db_session
from shared.helpers.task_execution.task_execution_tracker import (
    STATUS_COMPLETED,
    TaskExecutionTracker,
    TaskInProgressError,
)
from shared.notifications.notification_constants import NotificationLogStatus
from shared.users_database_gen.sqlacodegen_models import NotificationLog
from tasks.notifications.dispatch_notifications import (
    DISPATCH_TASK_NAME,
    emit_admin_summary,
)

logger = logging.getLogger(__name__)


def notifications_dispatch_monitor_handler(payload: dict) -> dict:
    """Entry point for the ``notifications_dispatch_monitor`` task."""
    run_id = (payload or {}).get("run_id")
    if not run_id:
        raise ValueError("run_id is required")
    return _monitor(run_id)


@with_db_session
def _monitor(run_id: str, db_session=None) -> dict:
    tracker = TaskExecutionTracker(
        task_name=DISPATCH_TASK_NAME,
        run_id=run_id,
        db_session=db_session,
    )
    summary = tracker.get_summary()

    if summary["run_status"] is None:
        logger.warning("monitor: unknown run %s; nothing to do", run_id)
        return {"run_id": run_id, "status": "unknown"}

    # Already finalised — a redelivery must not emit a second summary.
    if summary["run_status"] == STATUS_COMPLETED:
        return {"run_id": run_id, "status": "already_complete"}

    params = summary.get("params") or {}
    run_started_at = _parse_iso(params.get("run_started_at"))
    deadline_seconds = int(params.get("deadline_seconds", 0) or 0)
    cadence = params.get("cadence", "unknown")

    settled = summary["triggered"] == 0
    past_deadline = (
        run_started_at is not None
        and deadline_seconds > 0
        and (datetime.now(timezone.utc) - run_started_at).total_seconds()
        > deadline_seconds
    )

    if not settled and not past_deadline:
        raise TaskInProgressError(
            f"run {run_id} still in progress: {summary['triggered']} worker(s) pending"
        )

    # Drained (or deadline reached): aggregate delivery stats and emit ONE summary.
    delivery_stats = _aggregate_delivery_stats(since=run_started_at)
    stats = {
        "subscriptions_processed": summary["completed"] + summary["failed"],
        "workers_failed": summary["failed"],
        "events_found": delivery_stats["events_found"],
        "emails_sent": delivery_stats["emails_sent"],
        "emails_failed": delivery_stats["emails_failed"],
        "permanently_failed": delivery_stats["permanently_failed"],
        "incomplete_workers": summary["triggered"],  # >0 only if deadline reached
    }

    if stats["subscriptions_processed"] > 0 or stats["incomplete_workers"] > 0:
        _emit_summary(stats=stats, cadence=cadence)

    tracker.finish_run(status=STATUS_COMPLETED)
    db_session.commit()

    logger.info(
        "monitor: run %s settled (past_deadline=%s) stats=%s",
        run_id,
        past_deadline,
        stats,
    )
    return {"run_id": run_id, "status": "complete", **stats}


@with_users_db_session
def _aggregate_delivery_stats(
    since: Optional[datetime], db_session=None
) -> Dict[str, int]:
    """Aggregate notification_log outcomes for this run from the users DB.

    Scoped by ``sent_at >= run_started_at`` so it reflects only this run's sends.
    """
    q = db_session.query(NotificationLog)
    if since is not None:
        q = q.filter(NotificationLog.sent_at >= since)
    rows = q.with_entities(NotificationLog.status).all()

    sent = sum(1 for r in rows if r.status == NotificationLogStatus.SENT)
    failed = sum(
        1
        for r in rows
        if r.status
        in (NotificationLogStatus.FAILED, NotificationLogStatus.PERMANENTLY_FAILED)
    )
    perm = sum(1 for r in rows if r.status == NotificationLogStatus.PERMANENTLY_FAILED)
    return {
        "events_found": len(rows),
        "emails_sent": sent,
        "emails_failed": failed,
        "permanently_failed": perm,
    }


@with_users_db_session
def _emit_summary(stats: Dict[str, int], cadence: str, db_session=None) -> None:
    emit_admin_summary(db_session=db_session, stats=stats, cadence=cadence)
    db_session.commit()


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
