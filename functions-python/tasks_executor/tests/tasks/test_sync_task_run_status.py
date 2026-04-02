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

from shared.helpers.task_execution.task_execution_tracker import TaskInProgressError

_MODULE = "tasks.sync_task_run_status"


class TestSyncTaskRunStatusHandler(unittest.TestCase):
    def test_requires_task_name(self):
        from tasks.sync_task_run_status import sync_task_run_status_handler

        with self.assertRaises(ValueError):
            sync_task_run_status_handler({"run_id": "7.0.0"})

    def test_requires_run_id(self):
        from tasks.sync_task_run_status import sync_task_run_status_handler

        with self.assertRaises(ValueError):
            sync_task_run_status_handler({"task_name": "gtfs_validation"})

    @patch(f"{_MODULE}.sync_task_run_status")
    def test_passes_params(self, mock_fn):
        from tasks.sync_task_run_status import sync_task_run_status_handler

        mock_fn.return_value = {"run_status": "completed"}
        sync_task_run_status_handler(
            {"task_name": "gtfs_validation", "run_id": "7.0.0"}
        )
        mock_fn.assert_called_once_with(task_name="gtfs_validation", run_id="7.0.0")


class TestSyncTaskRunStatus(unittest.TestCase):
    def _make_tracker_mock(self, summary):
        tracker = MagicMock()
        tracker.get_summary.return_value = summary
        return tracker

    def _make_session_mock(self):
        session = MagicMock()
        session.query.return_value.filter.return_value.all.return_value = []
        return session

    @patch(f"{_MODULE}._sync_workflow_statuses")
    @patch(f"{_MODULE}.TaskExecutionTracker")
    def test_marks_completed_when_all_settled(self, tracker_cls, sync_mock):
        from tasks.sync_task_run_status import sync_task_run_status

        tracker = self._make_tracker_mock(
            {
                "run_status": "in_progress",
                "total_count": 5,
                "pending": 0,
                "triggered": 0,
                "completed": 5,
                "failed": 0,
                "params": {"total_candidates": 5},
            }
        )
        tracker_cls.return_value = tracker
        session = self._make_session_mock()

        result = sync_task_run_status(
            task_name="gtfs_validation", run_id="7.0.0", db_session=session
        )

        tracker.finish_run.assert_called_once()
        tracker.schedule_status_sync.assert_not_called()
        self.assertTrue(result["ready_for_bigquery"])
        self.assertTrue(result["dispatch_complete"])

    @patch(f"{_MODULE}._sync_workflow_statuses")
    @patch(f"{_MODULE}.TaskExecutionTracker")
    def test_raises_task_in_progress_when_triggered_remain(self, tracker_cls, sync_mock):
        from tasks.sync_task_run_status import sync_task_run_status

        tracker = self._make_tracker_mock(
            {
                "run_status": "in_progress",
                "total_count": 100,
                "pending": 0,
                "triggered": 40,
                "completed": 60,
                "failed": 0,
                "params": {"total_candidates": 100},
            }
        )
        tracker_cls.return_value = tracker
        session = self._make_session_mock()

        with self.assertRaises(TaskInProgressError):
            sync_task_run_status(
                task_name="gtfs_validation", run_id="7.0.0", db_session=session
            )

        tracker.finish_run.assert_not_called()
        tracker.schedule_status_sync.assert_not_called()

    @patch(f"{_MODULE}._sync_workflow_statuses")
    @patch(f"{_MODULE}.TaskExecutionTracker")
    def test_raises_task_in_progress_when_dispatch_incomplete(self, tracker_cls, sync_mock):
        from tasks.sync_task_run_status import sync_task_run_status

        tracker = self._make_tracker_mock(
            {
                "run_status": "in_progress",
                "total_count": 100,
                "pending": 30,
                "triggered": 0,
                "completed": 70,
                "failed": 0,
                "params": None,
            }
        )
        tracker_cls.return_value = tracker
        session = self._make_session_mock()

        with self.assertRaises(TaskInProgressError):
            sync_task_run_status(
                task_name="gtfs_validation", run_id="7.0.0", db_session=session
            )

    @patch(f"{_MODULE}._sync_workflow_statuses")
    @patch(f"{_MODULE}.TaskExecutionTracker")
    def test_raises_task_in_progress_when_failures_exist(self, tracker_cls, sync_mock):
        from tasks.sync_task_run_status import sync_task_run_status

        tracker = self._make_tracker_mock(
            {
                "run_status": "in_progress",
                "total_count": 5,
                "pending": 0,
                "triggered": 0,
                "completed": 3,
                "failed": 2,
                "params": None,
            }
        )
        tracker_cls.return_value = tracker
        session = self._make_session_mock()
        session.query.return_value.filter.return_value.all.return_value = [
            MagicMock(entity_id="ds-1"),
            MagicMock(entity_id="ds-2"),
        ]

        with self.assertRaises(TaskInProgressError):
            sync_task_run_status(
                task_name="gtfs_validation", run_id="7.0.0", db_session=session
            )


if __name__ == "__main__":
    unittest.main()
