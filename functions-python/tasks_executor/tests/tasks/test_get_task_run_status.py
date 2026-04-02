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

_MODULE = "tasks.get_task_run_status"


class TestGetTaskRunStatusHandler(unittest.TestCase):
    def test_requires_task_name(self):
        from tasks.get_task_run_status import get_task_run_status_handler

        with self.assertRaises(ValueError):
            get_task_run_status_handler({"run_id": "7.0.0"})

    def test_requires_run_id(self):
        from tasks.get_task_run_status import get_task_run_status_handler

        with self.assertRaises(ValueError):
            get_task_run_status_handler({"task_name": "gtfs_validation"})

    @patch(f"{_MODULE}.get_task_run_status")
    def test_passes_params(self, mock_fn):
        from tasks.get_task_run_status import get_task_run_status_handler

        mock_fn.return_value = {"run_status": "completed"}
        get_task_run_status_handler({"task_name": "gtfs_validation", "run_id": "7.0.0"})
        mock_fn.assert_called_once_with(task_name="gtfs_validation", run_id="7.0.0")


class TestGetTaskRunStatus(unittest.TestCase):
    def _make_summary(self, overrides=None):
        base = {
            "task_name": "gtfs_validation",
            "run_id": "7.0.0",
            "run_status": "in_progress",
            "total_count": 100,
            "triggered": 10,
            "completed": 80,
            "failed": 0,
            "pending": 10,
            "created_at": None,
            "params": None,
        }
        if overrides:
            base.update(overrides)
        return base

    def _make_session_mock(self):
        return MagicMock()

    @patch(f"{_MODULE}.TaskExecutionTracker")
    def test_returns_summary_with_dispatch_complete_false(self, tracker_cls):
        from tasks.get_task_run_status import get_task_run_status

        tracker = MagicMock()
        tracker.get_summary.return_value = self._make_summary({"pending": 10})
        tracker_cls.return_value = tracker
        session = self._make_session_mock()

        result = get_task_run_status(
            task_name="gtfs_validation", run_id="7.0.0", db_session=session
        )

        self.assertFalse(result["dispatch_complete"])
        self.assertEqual(result["pending"], 10)
        tracker.finish_run.assert_not_called()

    @patch(f"{_MODULE}.TaskExecutionTracker")
    def test_returns_summary_with_dispatch_complete_true(self, tracker_cls):
        from tasks.get_task_run_status import get_task_run_status

        tracker = MagicMock()
        tracker.get_summary.return_value = self._make_summary(
            {"pending": 0, "triggered": 0, "completed": 100}
        )
        tracker_cls.return_value = tracker
        session = self._make_session_mock()

        result = get_task_run_status(
            task_name="gtfs_validation", run_id="7.0.0", db_session=session
        )

        self.assertTrue(result["dispatch_complete"])
        self.assertEqual(result["completed"], 100)
        tracker.finish_run.assert_not_called()

    @patch(f"{_MODULE}.TaskExecutionTracker")
    def test_does_not_modify_statuses(self, tracker_cls):
        from tasks.get_task_run_status import get_task_run_status

        tracker = MagicMock()
        tracker.get_summary.return_value = self._make_summary()
        tracker_cls.return_value = tracker
        session = self._make_session_mock()

        get_task_run_status(
            task_name="gtfs_validation", run_id="7.0.0", db_session=session
        )

        tracker.mark_completed.assert_not_called()
        tracker.mark_failed.assert_not_called()
        tracker.mark_triggered.assert_not_called()
        tracker.finish_run.assert_not_called()
        tracker.schedule_status_sync.assert_not_called()

    @patch(f"{_MODULE}.TaskExecutionTracker")
    def test_returns_none_run_status_when_not_found(self, tracker_cls):
        from tasks.get_task_run_status import get_task_run_status

        tracker = MagicMock()
        tracker.get_summary.return_value = {
            "task_name": "gtfs_validation",
            "run_id": "9.9.9",
            "run_status": None,
            "total_count": None,
            "triggered": 0,
            "completed": 0,
            "failed": 0,
            "pending": 0,
            "created_at": None,
            "params": None,
        }
        tracker_cls.return_value = tracker
        session = self._make_session_mock()

        result = get_task_run_status(
            task_name="gtfs_validation", run_id="9.9.9", db_session=session
        )

        self.assertIsNone(result["run_status"])
        self.assertTrue(result["dispatch_complete"])


if __name__ == "__main__":
    unittest.main()
