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

"""
Task: get_task_run_status

Read-only snapshot of a task_run tracked by TaskExecutionTracker.

Returns the current DB state for the given (task_name, run_id) pair without
triggering any GCP Workflows polling or status transitions. Use this task to
inspect a run at any point — before, during, or after it completes.

For active status syncing (polling GCP Workflows and driving run completion)
use sync_task_run_status instead.

Payload:
    {
        "task_name": str,   # required — e.g. "gtfs_validation"
        "run_id": str,      # required — e.g. "7.1.1-SNAPSHOT"
    }
"""

from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.helpers.task_execution.task_execution_tracker import TaskExecutionTracker


def get_task_run_status_handler(payload: dict) -> dict:
    """
    Entry point for the get_task_run_status task.

    Payload structure:
    {
        "task_name": str,   # required
        "run_id": str,      # required
    }

    Returns a status summary dict. Never raises TaskInProgressError — this task
    is always read-only and always returns HTTP 200.
    """
    task_name = payload.get("task_name")
    run_id = payload.get("run_id")
    if not task_name or not run_id:
        raise ValueError("task_name and run_id are required")

    return get_task_run_status(task_name=task_name, run_id=run_id)


@with_db_session
def get_task_run_status(
    task_name: str,
    run_id: str,
    db_session: Session | None = None,
) -> dict:
    """
    Return a snapshot of the task run's current state from the DB.

    Response fields:
        task_name       — the task name
        run_id          — the run identifier
        run_status      — task_run.status (in_progress / completed / failed / None if not found)
        total_count     — number of entities registered at dispatch time
        triggered       — count with status=triggered (workflows still running)
        completed       — count with status=completed
        failed          — count with status=failed
        pending         — total_count minus all logged entries (dispatch not yet complete)
        dispatch_complete — True when pending == 0 (all entities have been dispatched)
        created_at      — when the task_run was first created
        params          — params dict stored at start_run() time
    """
    tracker = TaskExecutionTracker(
        task_name=task_name,
        run_id=run_id,
        db_session=db_session,
    )
    summary = tracker.get_summary()
    summary["dispatch_complete"] = summary["pending"] == 0
    return summary
