"""Execution state of users' tasks, read from TaskExecutionTracker's rows in the feeds database.

A user_task lives in the users database; the worker that runs it records its status, progress and
error with TaskExecutionTracker, with task_name = user_task.kind and entity_id = user_task.id. The
two databases share no foreign key, so the state is looked up by those two values. The tracker
never holds the user id: ownership is checked in the users database before any task id reaches
this module.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import TaskExecutionLog

# TaskExecutionTracker's statuses, repeated here because the API cannot import the tracker.
TRACKER_TRIGGERED = "triggered"
TRACKER_IN_PROGRESS = "in_progress"
TRACKER_COMPLETED = "completed"
TRACKER_FAILED = "failed"


@dataclass(frozen=True)
class TaskState:
    status: str  # one of the TRACKER_* statuses
    phase: Optional[str]  # what the worker is doing, as display text, from its last heartbeat
    progress: Optional[int]  # percentage of the current phase, from the worker's last heartbeat


@with_db_session
def task_states(task_name: str, task_ids: List[str], db_session: Session) -> Dict[str, TaskState]:
    """The latest tracked state of each task, keyed by task id. Tasks never triggered are absent."""
    if not task_ids:
        return {}
    rows = (
        db_session.query(TaskExecutionLog)
        .filter(TaskExecutionLog.task_name == task_name, TaskExecutionLog.entity_id.in_(task_ids))
        # One row per task: a task retried under a new run_id (converter version) has several.
        .distinct(TaskExecutionLog.entity_id)
        .order_by(TaskExecutionLog.entity_id, TaskExecutionLog.triggered_at.desc(), TaskExecutionLog.id.desc())
        .all()
    )
    return {row.entity_id: _state(row) for row in rows}


def _state(row: TaskExecutionLog) -> TaskState:
    metadata = row.metadata_ or {}
    phase = metadata.get("phase")
    return TaskState(
        status=row.status,
        phase=phase if isinstance(phase, str) and phase else None,
        progress=_progress(metadata),
    )


def _progress(metadata: dict) -> Optional[int]:
    """The percentage done, from the `done` and `total` counts the worker reports in its heartbeat."""
    done, total = metadata.get("done"), metadata.get("total")
    if not isinstance(done, (int, float)) or not isinstance(total, (int, float)) or total <= 0:
        return None
    return max(0, min(100, int(done * 100 / total)))
