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
Generic task execution tracker backed by the task_run and task_execution_log DB tables.

Mirrors the DatasetTraceService / BatchExecutionService pattern (currently Datastore-based)
so that batch_process_dataset, batch_datasets, and gbfs_validator can migrate to this
class in the future.

Usage:
    tracker = TaskExecutionTracker(
        task_name="gtfs_validation",
        run_id="7.0.0",
        db_session=session,
    )
    tracker.start_run(total_count=5000, params={"validator_endpoint": "...", "env": "staging"})

    if not tracker.is_triggered(dataset_id):
        execute_workflow(...)
        tracker.mark_triggered(dataset_id, execution_ref=execution.name)

    # Later, in process_validation_report:
    tracker.mark_completed(dataset_id)

    summary = tracker.get_summary()
    # {"total_count": 5000, "triggered": 150, "completed": 140, "failed": 2, "pending": 4858, ...}
"""

import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from shared.database_gen.sqlacodegen_models import TaskExecutionLog, TaskRun

STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_TRIGGERED = "triggered"


class TaskInProgressError(Exception):
    """
    Raised by task handlers to signal that the task run is not yet complete.
    tasks_executor maps this to HTTP 503, which causes Cloud Tasks to retry
    according to the queue's retry_config (typically every 10 minutes).
    """


class TaskExecutionTracker:
    """
    Tracks execution state for a named task run across restarts and partial executions.

    Two-level model:
      - task_run: one record per logical run (identified by task_name + run_id)
      - task_execution_log: one record per entity processed within the run

    entity_id may be None for tasks that do not operate on specific entities
    (e.g. refresh_materialized_view).
    """

    def __init__(self, task_name: str, run_id: str, db_session: Session):
        self.task_name = task_name
        self.run_id = run_id
        self.db_session = db_session
        self._task_run_id: Optional[uuid.UUID] = None

    # ------------------------------------------------------------------
    # Run-level operations
    # ------------------------------------------------------------------

    def start_run(
        self, total_count: Optional[int] = None, params: Optional[dict] = None
    ) -> uuid.UUID:
        """
        Upsert a task_run record and return its UUID.

        Safe to call multiple times for the same (task_name, run_id) — subsequent calls
        update total_count and params but preserve created_at and the existing status
        unless it is still in_progress.
        """
        stmt = (
            insert(TaskRun)
            .values(
                task_name=self.task_name,
                run_id=self.run_id,
                status=STATUS_IN_PROGRESS,
                total_count=total_count,
                params=params,
            )
            .on_conflict_do_update(
                constraint="task_run_task_name_run_id_key",
                set_={
                    "total_count": total_count,
                    "params": params,
                },
            )
            .returning(TaskRun.id)
        )
        result = self.db_session.execute(stmt)
        self.db_session.flush()
        self._task_run_id = result.scalar_one()
        logging.info(
            "TaskExecutionTracker: run %s/%s started (id=%s, total=%s)",
            self.task_name,
            self.run_id,
            self._task_run_id,
            total_count,
        )
        return self._task_run_id

    def finish_run(self, status: str = STATUS_COMPLETED) -> None:
        """Mark the task_run as completed or failed."""
        self.db_session.query(TaskRun).filter(
            TaskRun.task_name == self.task_name,
            TaskRun.run_id == self.run_id,
        ).update(
            {"status": status, "completed_at": datetime.now(timezone.utc)},
            synchronize_session=False,
        )
        logging.info(
            "TaskExecutionTracker: run %s/%s finished with status=%s",
            self.task_name,
            self.run_id,
            status,
        )

    # ------------------------------------------------------------------
    # Entity-level operations
    # ------------------------------------------------------------------

    def is_triggered(self, entity_id: Optional[str]) -> bool:
        """
        Return True if an execution log entry already exists for this entity
        with status triggered or completed (i.e. should not be re-triggered).
        """
        query = self.db_session.query(TaskExecutionLog).filter(
            TaskExecutionLog.task_name == self.task_name,
            TaskExecutionLog.run_id == self.run_id,
            TaskExecutionLog.status.in_([STATUS_TRIGGERED, STATUS_COMPLETED]),
        )
        if entity_id is None:
            query = query.filter(TaskExecutionLog.entity_id.is_(None))
        else:
            query = query.filter(TaskExecutionLog.entity_id == entity_id)
        return query.first() is not None

    def mark_triggered(
        self,
        entity_id: Optional[str],
        execution_ref: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        bypass_db_update: bool = False,
    ) -> None:
        """
        Insert a task_execution_log row with status=triggered.
        Idempotent: if a row already exists for this (task_name, entity_id, run_id),
        it updates execution_ref and metadata.
        """
        task_run_id = self._resolve_task_run_id()
        stmt = (
            insert(TaskExecutionLog)
            .values(
                task_run_id=task_run_id,
                task_name=self.task_name,
                entity_id=entity_id,
                run_id=self.run_id,
                status=STATUS_TRIGGERED,
                execution_ref=execution_ref,
                bypass_db_update=bypass_db_update,
                metadata_=metadata,
            )
            .on_conflict_do_update(
                constraint="task_execution_log_task_name_entity_id_run_id_key",
                set_={
                    "execution_ref": execution_ref,
                    "metadata": metadata,
                    "status": STATUS_TRIGGERED,
                },
            )
        )
        self.db_session.execute(stmt)
        self.db_session.flush()
        logging.debug(
            "TaskExecutionTracker: marked triggered entity=%s run=%s/%s ref=%s",
            entity_id,
            self.task_name,
            self.run_id,
            execution_ref,
        )

    def mark_completed(self, entity_id: Optional[str]) -> None:
        """Mark an entity execution as completed."""
        self._update_entity_status(entity_id, STATUS_COMPLETED)

    def mark_failed(
        self, entity_id: Optional[str], error_message: Optional[str] = None
    ) -> None:
        """Mark an entity execution as failed, optionally storing an error message."""
        query = self.db_session.query(TaskExecutionLog).filter(
            TaskExecutionLog.task_name == self.task_name,
            TaskExecutionLog.run_id == self.run_id,
        )
        if entity_id is None:
            query = query.filter(TaskExecutionLog.entity_id.is_(None))
        else:
            query = query.filter(TaskExecutionLog.entity_id == entity_id)
        query.update(
            {
                "status": STATUS_FAILED,
                "error_message": error_message,
                "completed_at": datetime.now(timezone.utc),
            },
            synchronize_session=False,
        )
        self.db_session.flush()

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_summary(self) -> dict:
        """
        Return a summary of the run from both task_run and task_execution_log.

        Returns:
            {
                "task_name": str,
                "run_id": str,
                "run_status": str,
                "total_count": int | None,
                "created_at": datetime | None,
                "params": dict | None,
                "triggered": int,
                "completed": int,
                "failed": int,
                "pending": int,   # > 0 means dispatch loop didn't complete; call rebuild again
            }
        """
        task_run = (
            self.db_session.query(TaskRun)
            .filter(
                TaskRun.task_name == self.task_name,
                TaskRun.run_id == self.run_id,
            )
            .first()
        )
        if not task_run:
            return {
                "task_name": self.task_name,
                "run_id": self.run_id,
                "run_status": None,
                "total_count": None,
                "created_at": None,
                "params": None,
                "triggered": 0,
                "completed": 0,
                "failed": 0,
                "pending": 0,
            }

        counts: dict[str, int] = {
            STATUS_TRIGGERED: 0,
            STATUS_COMPLETED: 0,
            STATUS_FAILED: 0,
        }
        rows = (
            self.db_session.query(
                TaskExecutionLog.status,
                TaskExecutionLog.id,
            )
            .filter(
                TaskExecutionLog.task_name == self.task_name,
                TaskExecutionLog.run_id == self.run_id,
            )
            .all()
        )
        for row in rows:
            if row.status in counts:
                counts[row.status] += 1

        total = task_run.total_count or 0
        processed = (
            counts[STATUS_TRIGGERED] + counts[STATUS_COMPLETED] + counts[STATUS_FAILED]
        )
        pending = max(0, total - processed)

        return {
            "task_name": self.task_name,
            "run_id": self.run_id,
            "run_status": task_run.status,
            "total_count": task_run.total_count,
            "created_at": task_run.created_at,
            "params": task_run.params,
            "triggered": counts[STATUS_TRIGGERED],
            "completed": counts[STATUS_COMPLETED],
            "failed": counts[STATUS_FAILED],
            "pending": pending,
        }

    def schedule_status_sync(self, delay_seconds: int = 0) -> None:
        """
        Enqueue a single Cloud Task that will call sync_task_run_status for this run.

        The task name is derived solely from task_name + run_id so the call is fully
        idempotent — if a task with this name already exists in the queue Cloud Tasks
        returns ALREADY_EXISTS and this method silently skips enqueueing.

        Retries are driven entirely by the queue's retry_config (constant 10-min
        intervals). The task handler returns 503 while the run is in progress and
        200 only when complete, so Cloud Tasks knows when to stop retrying.

        Requires env vars: PROJECT_ID, GCP_REGION, ENVIRONMENT, TASK_RUN_SYNC_QUEUE,
        SERVICE_ACCOUNT_EMAIL.  No-op with a warning when any are missing.
        """
        project = os.getenv("PROJECT_ID")
        queue = os.getenv("TASK_RUN_SYNC_QUEUE")
        gcp_region = os.getenv("GCP_REGION")
        environment = os.getenv("ENVIRONMENT")

        if not all([project, queue, gcp_region, environment]):
            logging.warning(
                "schedule_status_sync: missing env vars (PROJECT_ID/GCP_REGION/"
                "ENVIRONMENT/TASK_RUN_SYNC_QUEUE) — skipping Cloud Task enqueue"
            )
            return

        try:
            from google.cloud import tasks_v2
            from google.protobuf import timestamp_pb2
            from shared.helpers.utils import create_http_task_with_name

            safe_name = re.sub(
                r"[^a-zA-Z0-9_-]", "-", f"{self.task_name}-{self.run_id}"
            )
            task_name = f"sync-{safe_name}"[:500]

            url = (
                f"https://{gcp_region}-{project}.cloudfunctions.net/"
                f"tasks_executor-{environment}"
            )
            body = json.dumps(
                {
                    "task": "sync_task_run_status",
                    "payload": {
                        "task_name": self.task_name,
                        "run_id": self.run_id,
                    },
                }
            ).encode()

            schedule_time = None
            if delay_seconds > 0:
                run_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
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
            logging.info(
                "TaskExecutionTracker: enqueued sync task '%s' for %s/%s",
                task_name,
                self.task_name,
                self.run_id,
            )
        except Exception as e:
            if "already exists" in str(e).lower() or "ALREADY_EXISTS" in str(e):
                logging.info(
                    "TaskExecutionTracker: sync task already queued for %s/%s — skipping",
                    self.task_name,
                    self.run_id,
                )
            else:
                logging.warning(
                    "TaskExecutionTracker: could not enqueue sync task: %s", e
                )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_task_run_id(self) -> Optional[uuid.UUID]:
        """Return cached task_run_id or fetch it from DB."""
        if self._task_run_id:
            return self._task_run_id
        task_run = (
            self.db_session.query(TaskRun)
            .filter(
                TaskRun.task_name == self.task_name,
                TaskRun.run_id == self.run_id,
            )
            .first()
        )
        if task_run:
            self._task_run_id = task_run.id
        return self._task_run_id

    def _update_entity_status(self, entity_id: Optional[str], status: str) -> None:
        query = self.db_session.query(TaskExecutionLog).filter(
            TaskExecutionLog.task_name == self.task_name,
            TaskExecutionLog.run_id == self.run_id,
        )
        if entity_id is None:
            query = query.filter(TaskExecutionLog.entity_id.is_(None))
        else:
            query = query.filter(TaskExecutionLog.entity_id == entity_id)
        query.update(
            {"status": status, "completed_at": datetime.now(timezone.utc)},
            synchronize_session=False,
        )
        self.db_session.flush()
