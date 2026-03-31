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

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

from shared.helpers.task_execution.task_execution_tracker import (
    TaskExecutionTracker,
    STATUS_IN_PROGRESS,
    STATUS_TRIGGERED,
    STATUS_COMPLETED,
    STATUS_FAILED,
)


def _make_tracker(task_name="test_task", run_id="v1.0"):
    """Return a tracker with a mock DB session."""
    session = MagicMock()
    tracker = TaskExecutionTracker(task_name=task_name, run_id=run_id, db_session=session)
    return tracker, session


class TestTaskExecutionTrackerStartRun(unittest.TestCase):
    def test_start_run_upserts_task_run(self):
        tracker, session = _make_tracker()
        run_uuid = uuid.uuid4()
        execute_result = MagicMock()
        execute_result.scalar_one.return_value = run_uuid
        session.execute.return_value = execute_result

        result = tracker.start_run(total_count=100, params={"env": "staging"})

        self.assertEqual(result, run_uuid)
        self.assertEqual(tracker._task_run_id, run_uuid)
        session.execute.assert_called_once()
        session.flush.assert_called_once()

    def test_start_run_caches_task_run_id(self):
        tracker, session = _make_tracker()
        run_uuid = uuid.uuid4()
        execute_result = MagicMock()
        execute_result.scalar_one.return_value = run_uuid
        session.execute.return_value = execute_result

        tracker.start_run(total_count=10)
        tracker.start_run(total_count=20)  # second call

        self.assertEqual(tracker._task_run_id, run_uuid)


class TestTaskExecutionTrackerIsTriggered(unittest.TestCase):
    def test_returns_true_when_triggered_row_exists(self):
        tracker, session = _make_tracker()
        existing_row = MagicMock()
        session.query.return_value.filter.return_value.filter.return_value.first.return_value = existing_row

        result = tracker.is_triggered("ds-123")
        self.assertTrue(result)

    def test_returns_false_when_no_row(self):
        tracker, session = _make_tracker()
        session.query.return_value.filter.return_value.filter.return_value.first.return_value = None

        result = tracker.is_triggered("ds-999")
        self.assertFalse(result)

    def test_handles_none_entity_id(self):
        tracker, session = _make_tracker()
        session.query.return_value.filter.return_value.filter.return_value.first.return_value = None

        result = tracker.is_triggered(None)
        self.assertFalse(result)


class TestTaskExecutionTrackerMarkTriggered(unittest.TestCase):
    def test_mark_triggered_inserts_execution_log(self):
        tracker, session = _make_tracker()
        tracker._task_run_id = uuid.uuid4()

        tracker.mark_triggered("ds-1", execution_ref="projects/x/executions/abc")

        session.execute.assert_called_once()
        session.flush.assert_called_once()

    def test_mark_triggered_with_metadata(self):
        tracker, session = _make_tracker()
        tracker._task_run_id = uuid.uuid4()

        tracker.mark_triggered("ds-1", metadata={"feed_id": "f-1"})

        session.execute.assert_called_once()


class TestTaskExecutionTrackerMarkCompleted(unittest.TestCase):
    def test_mark_completed_updates_status(self):
        tracker, session = _make_tracker()
        query_mock = MagicMock()
        session.query.return_value.filter.return_value.filter.return_value = query_mock

        tracker.mark_completed("ds-1")

        query_mock.update.assert_called_once()
        update_args = query_mock.update.call_args[0][0]
        self.assertEqual(update_args["status"], STATUS_COMPLETED)
        self.assertIn("completed_at", update_args)


class TestTaskExecutionTrackerMarkFailed(unittest.TestCase):
    def test_mark_failed_sets_error_message(self):
        tracker, session = _make_tracker()
        query_mock = MagicMock()
        session.query.return_value.filter.return_value.filter.return_value = query_mock

        tracker.mark_failed("ds-1", error_message="Workflow timed out")

        query_mock.update.assert_called_once()
        update_args = query_mock.update.call_args[0][0]
        self.assertEqual(update_args["status"], STATUS_FAILED)
        self.assertEqual(update_args["error_message"], "Workflow timed out")


class TestTaskExecutionTrackerGetSummary(unittest.TestCase):
    def _make_task_run(self, status=STATUS_IN_PROGRESS, total_count=10):
        run = MagicMock()
        run.status = status
        run.total_count = total_count
        run.created_at = datetime.now(timezone.utc)
        return run

    def test_returns_none_summary_when_no_run(self):
        tracker, session = _make_tracker()
        session.query.return_value.filter.return_value.first.return_value = None
        session.query.return_value.filter.return_value.all.return_value = []

        summary = tracker.get_summary()

        self.assertIsNone(summary["run_status"])
        self.assertEqual(summary["triggered"], 0)
        self.assertEqual(summary["completed"], 0)

    def test_counts_by_status(self):
        tracker, session = _make_tracker()
        task_run = self._make_task_run(total_count=5)

        def query_side_effect(model):
            m = MagicMock()
            m.filter.return_value.first.return_value = task_run
            rows = [
                MagicMock(status=STATUS_TRIGGERED),
                MagicMock(status=STATUS_TRIGGERED),
                MagicMock(status=STATUS_COMPLETED),
                MagicMock(status=STATUS_FAILED),
            ]
            m.filter.return_value.all.return_value = rows
            return m

        session.query.side_effect = query_side_effect

        summary = tracker.get_summary()
        self.assertEqual(summary["triggered"], 2)
        self.assertEqual(summary["completed"], 1)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["pending"], 1)  # 5 total - 4 processed


class TestGetValidationRunStatus(unittest.TestCase):
    @patch("tasks.validation_reports.get_validation_run_status_task.TaskExecutionTracker")
    @patch("tasks.validation_reports.get_validation_run_status_task.with_db_session")
    def test_requires_validator_version(self, *_):
        from tasks.validation_reports.get_validation_run_status_task import (
            get_validation_run_status_handler,
        )
        with self.assertRaises(ValueError):
            get_validation_run_status_handler({})

    @patch("tasks.validation_reports.get_validation_run_status_task.TaskExecutionTracker")
    def test_handler_passes_version_to_function(self, tracker_cls):
        from tasks.validation_reports.get_validation_run_status_task import (
            get_validation_run_status_handler,
            get_validation_run_status,
        )
        with patch(
            "tasks.validation_reports.get_validation_run_status_task.get_validation_run_status"
        ) as mock_fn:
            mock_fn.return_value = {"run_status": "in_progress"}
            get_validation_run_status_handler({"validator_version": "7.0.0"})
            mock_fn.assert_called_once_with(
                validator_version="7.0.0", sync_workflow_status=False
            )
