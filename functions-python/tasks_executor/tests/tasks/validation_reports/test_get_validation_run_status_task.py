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
from unittest.mock import MagicMock, patch

from tasks.validation_reports.get_validation_run_status_task import (
    get_validation_run_status_handler,
    get_validation_run_status,
    GTFS_VALIDATION_TASK_NAME,
)

_MODULE = "tasks.validation_reports.get_validation_run_status_task"


class TestGetValidationRunStatusHandler(unittest.TestCase):
    def test_raises_when_validator_version_missing(self):
        with self.assertRaises(ValueError):
            get_validation_run_status_handler({})

    def test_raises_when_validator_version_empty(self):
        with self.assertRaises(ValueError):
            get_validation_run_status_handler({"validator_version": ""})

    @patch(f"{_MODULE}.get_validation_run_status")
    def test_passes_version_to_function(self, mock_fn):
        mock_fn.return_value = {"run_status": "in_progress"}
        get_validation_run_status_handler({"validator_version": "7.0.0"})
        mock_fn.assert_called_once_with(
            validator_version="7.0.0", sync_workflow_status=False
        )

    @patch(f"{_MODULE}.get_validation_run_status")
    def test_passes_sync_flag(self, mock_fn):
        mock_fn.return_value = {"run_status": "in_progress"}
        get_validation_run_status_handler(
            {"validator_version": "7.0.0", "sync_workflow_status": True}
        )
        mock_fn.assert_called_once_with(
            validator_version="7.0.0", sync_workflow_status=True
        )

    @patch(f"{_MODULE}.get_validation_run_status")
    def test_sync_flag_coerced_from_string(self, mock_fn):
        mock_fn.return_value = {}
        get_validation_run_status_handler(
            {"validator_version": "7.0.0", "sync_workflow_status": "true"}
        )
        mock_fn.assert_called_once_with(
            validator_version="7.0.0", sync_workflow_status=True
        )


class TestGetValidationRunStatus(unittest.TestCase):
    def _make_tracker_mock(self, summary=None):
        tracker = MagicMock()
        tracker.get_summary.return_value = summary or {
            "task_name": GTFS_VALIDATION_TASK_NAME,
            "run_id": "7.0.0",
            "run_status": "in_progress",
            "total_count": 100,
            "created_at": None,
            "triggered": 10,
            "completed": 80,
            "failed": 2,
            "pending": 8,
        }
        return tracker

    @patch(f"{_MODULE}.TaskExecutionTracker")
    def test_returns_summary_without_sync(self, tracker_cls):
        tracker = self._make_tracker_mock()
        tracker_cls.return_value = tracker

        session = MagicMock()
        session.query.return_value.filter.return_value.all.return_value = []

        result = get_validation_run_status(
            validator_version="7.0.0",
            sync_workflow_status=False,
            db_session=session,
        )

        self.assertEqual(result["triggered"], 10)
        self.assertEqual(result["completed"], 80)
        self.assertEqual(result["failed"], 2)
        self.assertEqual(result["failed_entity_ids"], [])
        self.assertFalse(result["ready_for_bigquery"])

    @patch(f"{_MODULE}.TaskExecutionTracker")
    def test_ready_for_bigquery_when_all_complete(self, tracker_cls):
        tracker = self._make_tracker_mock(
            summary={
                "task_name": GTFS_VALIDATION_TASK_NAME,
                "run_id": "7.0.0",
                "run_status": "in_progress",
                "total_count": 5,
                "created_at": None,
                "triggered": 0,
                "completed": 5,
                "failed": 0,
                "pending": 0,
            }
        )
        tracker_cls.return_value = tracker
        session = MagicMock()
        session.query.return_value.filter.return_value.all.return_value = []

        result = get_validation_run_status(
            validator_version="7.0.0",
            sync_workflow_status=False,
            db_session=session,
        )

        self.assertTrue(result["ready_for_bigquery"])

    @patch(f"{_MODULE}._sync_workflow_statuses")
    @patch(f"{_MODULE}.TaskExecutionTracker")
    def test_sync_workflow_status_calls_sync(self, tracker_cls, sync_mock):
        tracker = self._make_tracker_mock()
        tracker_cls.return_value = tracker
        session = MagicMock()
        session.query.return_value.filter.return_value.all.return_value = []

        get_validation_run_status(
            validator_version="7.0.0",
            sync_workflow_status=True,
            db_session=session,
        )

        sync_mock.assert_called_once()
        session.commit.assert_called_once()

    @patch(f"{_MODULE}.TaskExecutionTracker")
    def test_failed_entity_ids_included(self, tracker_cls):
        tracker = self._make_tracker_mock()
        tracker_cls.return_value = tracker

        failed_entry_1 = MagicMock()
        failed_entry_1.entity_id = "ds-failed-1"
        failed_entry_2 = MagicMock()
        failed_entry_2.entity_id = "ds-failed-2"

        session = MagicMock()
        session.query.return_value.filter.return_value.all.return_value = [
            failed_entry_1,
            failed_entry_2,
        ]

        result = get_validation_run_status(
            validator_version="7.0.0",
            sync_workflow_status=False,
            db_session=session,
        )

        self.assertEqual(result["failed_entity_ids"], ["ds-failed-1", "ds-failed-2"])


class TestSyncWorkflowStatuses(unittest.TestCase):
    def _make_session_with_entries(self, entries):
        """Return a mock session whose query().filter().all() returns entries."""
        session = MagicMock()
        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.all.return_value = entries
        session.query.return_value = query_mock
        return session

    @patch(f"{_MODULE}.executions_v1.ExecutionsClient")
    def test_skips_when_no_triggered_entries(self, client_cls):
        from tasks.validation_reports.get_validation_run_status_task import (
            _sync_workflow_statuses,
        )
        session = self._make_session_with_entries([])
        tracker = MagicMock()

        _sync_workflow_statuses("7.0.0", session, tracker)

        client_cls.return_value.get_execution.assert_not_called()

    @patch(f"{_MODULE}.executions_v1.ExecutionsClient")
    def test_marks_completed_for_succeeded_execution(self, client_cls):
        from google.cloud.workflows import executions_v1
        from tasks.validation_reports.get_validation_run_status_task import (
            _sync_workflow_statuses,
        )

        entry = MagicMock()
        entry.entity_id = "ds-1"
        entry.execution_ref = "projects/x/executions/abc"

        session = self._make_session_with_entries([entry])

        execution_result = MagicMock()
        execution_result.state = executions_v1.Execution.State.SUCCEEDED
        client_cls.return_value.get_execution.return_value = execution_result

        tracker = MagicMock()
        _sync_workflow_statuses("7.0.0", session, tracker)

        tracker.mark_completed.assert_called_once_with("ds-1")

    @patch(f"{_MODULE}.executions_v1.ExecutionsClient")
    def test_marks_failed_for_failed_execution(self, client_cls):
        from google.cloud.workflows import executions_v1
        from tasks.validation_reports.get_validation_run_status_task import (
            _sync_workflow_statuses,
        )

        entry = MagicMock()
        entry.entity_id = "ds-2"
        entry.execution_ref = "projects/x/executions/xyz"

        session = self._make_session_with_entries([entry])

        execution_result = MagicMock()
        execution_result.state = executions_v1.Execution.State.FAILED
        execution_result.error.payload = "Validator crashed"
        client_cls.return_value.get_execution.return_value = execution_result

        tracker = MagicMock()
        _sync_workflow_statuses("7.0.0", session, tracker)

        tracker.mark_failed.assert_called_once_with("ds-2", error_message="Validator crashed")
