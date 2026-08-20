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

"""Cloud Tasks barrier/monitor: settle a seal orchestrator run (issue #1800).

A single `seal_orchestrator_monitor` task is enqueued per run by the `seal_orchestrator`
producer. It uses the Cloud Tasks queue's NATIVE retry to poll: while batches are still
in flight (and within the run's `deadline_seconds`) it raises `TaskInProgressError` →
HTTP 503 so the queue retries it after its configured backoff. This is the guard against
listening forever if a worker dies without ever reporting back (a crashed worker, an
exhausted Cloud Tasks retry budget, ...): once the deadline passes, the monitor stops
polling and settles the run regardless of what is still `triggered`.

The run is finalised as `failed` if any batch failed or never reported by the deadline,
and `completed` only when every batch reported success — unlike the notification
dispatch monitor (which always finalises as `completed`, since a stats email is still
useful even with some workers unaccounted for), an incomplete seal run should surface as
a clear failure: the whole point of tracking start/end is to know when a nightly run did
NOT fully update the seal for every feed.

Payload::

    { "run_id": str }   # required
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import TaskExecutionLog
from shared.helpers.task_execution.task_execution_tracker import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    TaskExecutionTracker,
    TaskInProgressError,
)

from tasks.seal_of_reliability.seal_orchestrator import SEAL_ORCHESTRATOR_TASK_NAME

logger = logging.getLogger(__name__)

# Cap on how many granted/revoked stable_ids the summary reports directly; the two seal
# tables hold every transition regardless, so this only bounds the response size.
MAX_REPORTED_IDS = 200

_SETTLED_STATUSES = (STATUS_COMPLETED, STATUS_FAILED)


def seal_orchestrator_monitor_handler(payload: dict) -> dict:
    """Entry point for the `seal_orchestrator_monitor` task."""
    run_id = (payload or {}).get("run_id")
    if not run_id:
        raise ValueError("run_id is required")
    return _monitor(run_id)


@with_db_session
def _monitor(run_id: str, db_session=None) -> dict:
    tracker = TaskExecutionTracker(
        task_name=SEAL_ORCHESTRATOR_TASK_NAME,
        run_id=run_id,
        db_session=db_session,
    )
    summary = tracker.get_summary()

    if summary["run_status"] is None:
        logger.warning(
            "seal_orchestrator_monitor: unknown run %s; nothing to do", run_id
        )
        return {"run_id": run_id, "status": "unknown"}

    # Already finalised — a redelivery must not re-finish the run, but it should still
    # report the same aggregate (read-only, no mutation) rather than a bare status string:
    # this is the only way to see a settled run's feed-processing totals after the fact.
    if summary["run_status"] in _SETTLED_STATUSES:
        aggregated = _aggregate_batches(db_session, run_id)
        return {
            "run_id": run_id,
            "status": "already_complete",
            "batches_total": summary["total_count"],
            "batches_completed": summary["completed"],
            "batches_failed": summary["failed"],
            "batches_incomplete": summary["triggered"],
            **aggregated,
        }

    params = summary.get("params") or {}
    run_started_at = _parse_iso(params.get("run_started_at"))
    deadline_seconds = int(params.get("deadline_seconds", 0) or 0)

    settled = summary["triggered"] == 0
    past_deadline = (
        run_started_at is not None
        and deadline_seconds > 0
        and (datetime.now(timezone.utc) - run_started_at).total_seconds()
        > deadline_seconds
    )

    if not settled and not past_deadline:
        raise TaskInProgressError(
            f"run {run_id} still in progress: {summary['triggered']} batch(es) pending"
        )

    aggregated = _aggregate_batches(db_session, run_id)
    incomplete = summary["triggered"]  # > 0 only if the deadline was reached first
    final_status = (
        STATUS_FAILED if summary["failed"] > 0 or incomplete > 0 else STATUS_COMPLETED
    )

    tracker.finish_run(status=final_status)
    db_session.commit()

    result = {
        "run_id": run_id,
        "status": "complete" if final_status == STATUS_COMPLETED else "failed",
        "batches_total": summary["total_count"],
        "batches_completed": summary["completed"],
        "batches_failed": summary["failed"],
        "batches_incomplete": incomplete,
        **aggregated,
    }
    logger.info(
        "seal_orchestrator_monitor: run %s settled (past_deadline=%s) result=%s",
        run_id,
        past_deadline,
        {
            k: v
            for k, v in result.items()
            if k not in ("granted_stable_ids", "revoked_stable_ids")
        },
    )
    return result


def _aggregate_batches(db_session, run_id: str) -> Dict[str, Any]:
    """Sum each completed batch's stored `update_seals` report into one run-level report."""
    rows = (
        db_session.query(TaskExecutionLog.metadata_)
        .filter(
            TaskExecutionLog.task_name == SEAL_ORCHESTRATOR_TASK_NAME,
            TaskExecutionLog.run_id == run_id,
            TaskExecutionLog.metadata_.isnot(None),
        )
        .all()
    )

    total_feeds = 0
    criterion_rows_written = 0
    seals_granted = 0
    seals_revoked = 0
    granted_stable_ids: list = []
    revoked_stable_ids: list = []

    for (metadata,) in rows:
        if not metadata:
            continue
        total_feeds += metadata.get("total_feeds", 0) or 0
        criterion_rows_written += metadata.get("criterion_rows_written", 0) or 0
        seals_granted += metadata.get("seals_granted", 0) or 0
        seals_revoked += metadata.get("seals_revoked", 0) or 0
        granted_stable_ids.extend(metadata.get("granted_stable_ids") or [])
        revoked_stable_ids.extend(metadata.get("revoked_stable_ids") or [])

    ids_omitted = max(0, len(granted_stable_ids) - MAX_REPORTED_IDS) + max(
        0, len(revoked_stable_ids) - MAX_REPORTED_IDS
    )

    return {
        "total_feeds_evaluated": total_feeds,
        "criterion_rows_written": criterion_rows_written,
        "seals_granted": seals_granted,
        "seals_revoked": seals_revoked,
        "granted_stable_ids": granted_stable_ids[:MAX_REPORTED_IDS],
        "revoked_stable_ids": revoked_stable_ids[:MAX_REPORTED_IDS],
        "ids_omitted": ids_omitted,
    }


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
