#
#   MobilityData 2025
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

"""
Task: sync_task_run_status

Generic self-scheduling monitor for any task_run tracked by TaskExecutionTracker.

For each task_execution_log entry still in 'triggered' state that has an
execution_ref (a GCP Workflows execution name), this task polls the GCP Workflows
Executions API and updates the status to completed or failed.

When all entries are settled (no pending, no triggered), the parent task_run is
marked completed.  If work is still in progress the task re-schedules itself as
a Cloud Task (default delay: 10 minutes) and returns.

Payload:
    {
        "task_name": str,             # required — e.g. "gtfs_validation"
        "run_id": str,                # required — e.g. "7.1.1-SNAPSHOT"
        "sync_delay_seconds": int,    # [optional] Re-schedule delay. Default: 600
    }
"""

import logging

from google.cloud.workflows import executions_v1
from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import TaskExecutionLog
from shared.helpers.task_execution.task_execution_tracker import (
    TaskExecutionTracker,
    STATUS_TRIGGERED,
    STATUS_FAILED,
    STATUS_COMPLETED,
)


def sync_task_run_status_handler(payload: dict) -> dict:
    """
    Entry point for the sync_task_run_status task.

    Payload structure:
    {
        "task_name": str,            # required
        "run_id": str,               # required
        "sync_delay_seconds": int,   # [optional] Default: 600
    }
    """
    task_name = payload.get("task_name")
    run_id = payload.get("run_id")
    if not task_name or not run_id:
        raise ValueError("task_name and run_id are required")

    sync_delay_seconds = int(payload.get("sync_delay_seconds", 600))

    return sync_task_run_status(
        task_name=task_name,
        run_id=run_id,
        sync_delay_seconds=sync_delay_seconds,
    )


@with_db_session
def sync_task_run_status(
    task_name: str,
    run_id: str,
    sync_delay_seconds: int = 600,
    db_session: Session | None = None,
) -> dict:
    """
    Sync execution statuses and, if complete, mark the task_run as finished.

    For triggered entries that have an execution_ref, polls the GCP Workflows
    API to check whether the workflow succeeded or failed.

    If not yet complete, re-schedules itself via a Cloud Task after
    sync_delay_seconds seconds.
    """
    tracker = TaskExecutionTracker(
        task_name=task_name,
        run_id=run_id,
        db_session=db_session,
    )

    _sync_workflow_statuses(task_name, run_id, db_session, tracker)
    db_session.commit()

    summary = tracker.get_summary()
    summary["dispatch_complete"] = summary["pending"] == 0

    run_params = summary.get("params") or {}
    summary["total_candidates"] = run_params.get("total_candidates")

    failed_entries = (
        db_session.query(TaskExecutionLog)
        .filter(
            TaskExecutionLog.task_name == task_name,
            TaskExecutionLog.run_id == run_id,
            TaskExecutionLog.status == STATUS_FAILED,
        )
        .all()
    )
    summary["failed_entity_ids"] = [e.entity_id for e in failed_entries]

    all_settled = (
        summary["dispatch_complete"]
        and summary["triggered"] == 0
        and summary["failed"] == 0
    )
    summary["ready_for_bigquery"] = all_settled

    if all_settled:
        tracker.finish_run(STATUS_COMPLETED)
        db_session.commit()
        logging.info(
            "sync_task_run_status: run %s/%s is complete — marked task_run completed",
            task_name,
            run_id,
        )
    else:
        tracker.schedule_status_sync(delay_seconds=sync_delay_seconds)
        logging.info(
            "sync_task_run_status: run %s/%s still in progress — re-scheduled in %ss "
            "(pending=%s, triggered=%s, failed=%s)",
            task_name,
            run_id,
            sync_delay_seconds,
            summary["pending"],
            summary["triggered"],
            summary["failed"],
        )

    return summary


def _sync_workflow_statuses(
    task_name: str,
    run_id: str,
    db_session: Session,
    tracker: TaskExecutionTracker,
) -> None:
    """
    Poll GCP Workflows Executions API for all entries still in 'triggered' state
    that have an execution_ref, and update task_execution_log accordingly.
    """
    triggered_entries = (
        db_session.query(TaskExecutionLog)
        .filter(
            TaskExecutionLog.task_name == task_name,
            TaskExecutionLog.run_id == run_id,
            TaskExecutionLog.status == STATUS_TRIGGERED,
            TaskExecutionLog.execution_ref.isnot(None),
        )
        .all()
    )

    if not triggered_entries:
        logging.info(
            "sync_task_run_status: no triggered entries with execution_ref for %s/%s",
            task_name,
            run_id,
        )
        return

    logging.info(
        "sync_task_run_status: syncing %s triggered executions via GCP Workflows API",
        len(triggered_entries),
    )
    client = executions_v1.ExecutionsClient()

    for entry in triggered_entries:
        try:
            execution = client.get_execution(request={"name": entry.execution_ref})
            state = execution.state

            if state == executions_v1.Execution.State.SUCCEEDED:
                tracker.mark_completed(entry.entity_id)
                logging.info(
                    "Execution %s SUCCEEDED for entity %s",
                    entry.execution_ref,
                    entry.entity_id,
                )
            elif state in (
                executions_v1.Execution.State.FAILED,
                executions_v1.Execution.State.CANCELLED,
            ):
                error_msg = getattr(execution.error, "payload", str(state))
                tracker.mark_failed(entry.entity_id, error_message=error_msg)
                logging.warning(
                    "Execution %s %s for entity %s: %s",
                    entry.execution_ref,
                    state.name,
                    entry.entity_id,
                    error_msg,
                )
            # ACTIVE / QUEUED → still running, leave as triggered
        except Exception as e:
            logging.error(
                "Error fetching execution status for %s: %s", entry.execution_ref, e
            )
