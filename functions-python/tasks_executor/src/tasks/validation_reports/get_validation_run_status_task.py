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
Task: get_validation_run_status

Returns a progress summary for a GTFS validation run identified by validator_version.

For runs with bypass_db_update=False (post-release), completion is tracked via the
task_execution_log table updated by process_validation_report.

For runs with bypass_db_update=True (pre-release / staging), process_validation_report
is never called by the workflow, so completion is determined by polling the GCP
Workflows Executions API using the execution_ref stored in task_execution_log.
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
)

GTFS_VALIDATION_TASK_NAME = "gtfs_validation"


def get_validation_run_status_handler(payload) -> dict:
    """
    Returns progress summary for a GTFS validation run.

    Payload structure:
    {
        "validator_version": str,      # required — e.g. "7.0.0"
        "sync_workflow_status": bool,  # [optional] Poll GCP Workflows API to update
                                       # completion status for bypass_db_update=True runs.
                                       # Default: False (fast, read-only from DB)
    }
    """
    validator_version = payload.get("validator_version")
    if not validator_version:
        raise ValueError("validator_version is required")

    sync_workflow_status = payload.get("sync_workflow_status", False)
    sync_workflow_status = (
        sync_workflow_status
        if isinstance(sync_workflow_status, bool)
        else str(sync_workflow_status).lower() == "true"
    )

    return get_validation_run_status(
        validator_version=validator_version,
        sync_workflow_status=sync_workflow_status,
    )


@with_db_session
def get_validation_run_status(
    validator_version: str,
    sync_workflow_status: bool = False,
    db_session: Session | None = None,
) -> dict:
    """
    Returns a progress summary for the given validator_version run.

    When sync_workflow_status=True, queries the GCP Workflows Executions API
    for all entries in 'triggered' state and updates task_execution_log accordingly.
    This is needed for bypass_db_update=True (pre-release) runs where
    process_validation_report is never called.
    """
    tracker = TaskExecutionTracker(
        task_name=GTFS_VALIDATION_TASK_NAME,
        run_id=validator_version,
        db_session=db_session,
    )

    if sync_workflow_status:
        _sync_workflow_statuses(validator_version, db_session, tracker)
        db_session.commit()

    summary = tracker.get_summary()

    # dispatch_complete: True only when all intended triggers have been dispatched.
    # If False, rebuild_missing_validation_reports timed out mid-loop and should be called again.
    summary["dispatch_complete"] = summary["pending"] == 0

    # total_candidates comes from params (stored separately from total_count which is
    # the per-call limit). May be None for older runs that predate this field.
    run_params = summary.get("params") or {}
    summary["total_candidates"] = run_params.get("total_candidates")

    failed_entries = (
        db_session.query(TaskExecutionLog)
        .filter(
            TaskExecutionLog.task_name == GTFS_VALIDATION_TASK_NAME,
            TaskExecutionLog.run_id == validator_version,
            TaskExecutionLog.status == STATUS_FAILED,
        )
        .all()
    )
    summary["failed_entity_ids"] = [e.entity_id for e in failed_entries]
    summary["ready_for_bigquery"] = (
        summary["run_status"] is not None
        and summary["pending"] == 0
        and summary["triggered"] == 0
        and summary["failed"] == 0
    )

    return summary


def _sync_workflow_statuses(
    validator_version: str,
    db_session: Session,
    tracker: TaskExecutionTracker,
) -> None:
    """
    Poll GCP Workflows Executions API for all entries still in 'triggered' state
    and update task_execution_log with their current status (completed/failed).

    Used for bypass_db_update=True runs where process_validation_report is not called.
    """
    triggered_entries = (
        db_session.query(TaskExecutionLog)
        .filter(
            TaskExecutionLog.task_name == GTFS_VALIDATION_TASK_NAME,
            TaskExecutionLog.run_id == validator_version,
            TaskExecutionLog.status == STATUS_TRIGGERED,
            TaskExecutionLog.execution_ref.isnot(None),
        )
        .all()
    )

    if not triggered_entries:
        logging.info("No triggered entries to sync for version %s", validator_version)
        return

    logging.info(
        "Syncing %s triggered workflow executions from GCP API", len(triggered_entries)
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
