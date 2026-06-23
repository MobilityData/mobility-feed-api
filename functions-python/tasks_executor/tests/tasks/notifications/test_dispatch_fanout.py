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
"""Unit tests for the Cloud Tasks dispatch fan-out.

These cover the orchestration of the three dispatch handlers — planner, worker,
and monitor — with the DB / Cloud Tasks boundaries mocked. The end-to-end
claim-then-send behaviour is covered by ``TestProcessSubscription`` in
``test_dispatch_notifications.py`` against the real users database.
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from shared.helpers.task_execution.task_execution_tracker import TaskInProgressError

# ---------------------------------------------------------------------------
# notifications_dispatch_batch (producer)
# ---------------------------------------------------------------------------

_PLAN = "tasks.notifications.dispatch_batch"


class TestPlanHandler(unittest.TestCase):
    def _subs(self, *ids):
        return [MagicMock(id=i) for i in ids]

    @patch(f"{_PLAN}._start_run")
    @patch(f"{_PLAN}._enqueue", return_value=True)
    @patch(f"{_PLAN}.find_subscriptions")
    def test_enqueues_worker_per_subscription_plus_monitor(
        self, find_mock, enqueue_mock, start_run_mock
    ):
        from tasks.notifications.dispatch_batch import (
            notifications_dispatch_batch_handler,
        )

        find_mock.return_value = self._subs("sub-1", "sub-2")

        result = notifications_dispatch_batch_handler(
            {"cadence": "weekly", "dry_run": False}
        )

        # one run registered
        start_run_mock.assert_called_once()
        # 2 workers + 1 monitor enqueued
        self.assertEqual(enqueue_mock.call_count, 3)
        in_body_tasks = [c.kwargs["in_body_task"] for c in enqueue_mock.call_args_list]
        self.assertEqual(in_body_tasks.count("notifications_dispatch"), 2)
        self.assertEqual(in_body_tasks.count("notifications_dispatch_monitor"), 1)
        self.assertEqual(result["by_cadence"]["weekly"]["enqueued"], 2)

    @patch(f"{_PLAN}._start_run")
    @patch(f"{_PLAN}._enqueue", return_value=True)
    @patch(f"{_PLAN}.find_subscriptions")
    def test_dynamic_task_names_use_prefix(
        self, find_mock, enqueue_mock, start_run_mock
    ):
        from tasks.notifications.dispatch_batch import (
            notifications_dispatch_batch_handler,
        )

        find_mock.return_value = self._subs("sub-1")
        notifications_dispatch_batch_handler({"cadence": "weekly", "dry_run": False})

        names = [c.kwargs["task_name"] for c in enqueue_mock.call_args_list]
        self.assertTrue(all(n.startswith("notifications-dispatch-") for n in names))
        # monitor name is distinct and run-scoped
        self.assertTrue(
            any(n.startswith("notifications-dispatch-monitor-") for n in names)
        )

    @patch(f"{_PLAN}._start_run")
    @patch(f"{_PLAN}._enqueue", return_value=True)
    @patch(f"{_PLAN}.find_subscriptions")
    def test_dry_run_enqueues_nothing(self, find_mock, enqueue_mock, start_run_mock):
        from tasks.notifications.dispatch_batch import (
            notifications_dispatch_batch_handler,
        )

        find_mock.return_value = self._subs("sub-1", "sub-2")
        result = notifications_dispatch_batch_handler(
            {"cadence": "weekly", "dry_run": True}
        )

        enqueue_mock.assert_not_called()
        start_run_mock.assert_not_called()
        self.assertEqual(result["by_cadence"]["weekly"]["enqueued"], 0)

    @patch(f"{_PLAN}._start_run")
    @patch(f"{_PLAN}._enqueue", return_value=True)
    @patch(f"{_PLAN}.find_subscriptions")
    def test_no_subscriptions_enqueues_nothing(
        self, find_mock, enqueue_mock, start_run_mock
    ):
        from tasks.notifications.dispatch_batch import (
            notifications_dispatch_batch_handler,
        )

        find_mock.return_value = []
        notifications_dispatch_batch_handler({"cadence": "weekly", "dry_run": False})

        enqueue_mock.assert_not_called()
        start_run_mock.assert_not_called()


# ---------------------------------------------------------------------------
# notifications_dispatch (worker)
# ---------------------------------------------------------------------------

_WORKER = "tasks.notifications.dispatch_worker"


class TestWorkerHandler(unittest.TestCase):
    def test_requires_subscription_id(self):
        from tasks.notifications.dispatch_worker import (
            notifications_dispatch_handler,
        )

        with self.assertRaises(ValueError):
            notifications_dispatch_handler({"run_id": "r1"})

    @patch(f"{_WORKER}._mark_entry")
    @patch(f"{_WORKER}.process_subscription")
    def test_marks_completed_on_success(self, proc_mock, mark_mock):
        from tasks.notifications.dispatch_worker import (
            notifications_dispatch_handler,
        )

        proc_mock.return_value = {"emails_sent": 2, "events_claimed": 2}
        result = notifications_dispatch_handler(
            {"subscription_id": "sub-1", "run_id": "r1"}
        )

        proc_mock.assert_called_once()
        # marked completed (no error kwarg)
        mark_mock.assert_called_once_with("r1", "sub-1")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["emails_sent"], 2)

    @patch(f"{_WORKER}._mark_entry")
    @patch(f"{_WORKER}.process_subscription")
    def test_infra_error_marks_failed_and_reraises(self, proc_mock, mark_mock):
        from tasks.notifications.dispatch_worker import (
            notifications_dispatch_handler,
        )

        proc_mock.side_effect = RuntimeError("db down")
        with self.assertRaises(RuntimeError):
            notifications_dispatch_handler({"subscription_id": "sub-1", "run_id": "r1"})

        mark_mock.assert_called_once_with("r1", "sub-1", error="db down")


# ---------------------------------------------------------------------------
# notifications_dispatch_monitor (barrier / summary)
# ---------------------------------------------------------------------------

_MONITOR = "tasks.notifications.dispatch_monitor"


class TestMonitorHandler(unittest.TestCase):
    def _tracker(self, summary):
        tracker = MagicMock()
        tracker.get_summary.return_value = summary
        return tracker

    def _summary(
        self,
        triggered,
        completed=0,
        failed=0,
        run_status="in_progress",
        started_minutes_ago=1,
        deadline_seconds=21600,
    ):
        started = datetime.now(timezone.utc) - timedelta(minutes=started_minutes_ago)
        return {
            "run_status": run_status,
            "total_count": triggered + completed + failed,
            "pending": 0,
            "triggered": triggered,
            "completed": completed,
            "failed": failed,
            "params": {
                "cadence": "weekly",
                "run_started_at": started.isoformat(),
                "deadline_seconds": deadline_seconds,
            },
        }

    def test_requires_run_id(self):
        from tasks.notifications.dispatch_monitor import (
            notifications_dispatch_monitor_handler,
        )

        with self.assertRaises(ValueError):
            notifications_dispatch_monitor_handler({})

    @patch(f"{_MONITOR}._emit_summary")
    @patch(f"{_MONITOR}._aggregate_delivery_stats")
    @patch(f"{_MONITOR}.TaskExecutionTracker")
    def test_settled_emits_one_summary(self, tracker_cls, agg_mock, emit_mock):
        from tasks.notifications.dispatch_monitor import _monitor

        tracker = self._tracker(self._summary(triggered=0, completed=3))
        tracker_cls.return_value = tracker
        agg_mock.return_value = {
            "events_found": 5,
            "emails_sent": 4,
            "emails_failed": 1,
            "permanently_failed": 0,
        }

        result = _monitor("weekly-x", db_session=MagicMock())

        emit_mock.assert_called_once()
        tracker.finish_run.assert_called_once()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["subscriptions_processed"], 3)
        self.assertEqual(result["emails_sent"], 4)

    @patch(f"{_MONITOR}._emit_summary")
    @patch(f"{_MONITOR}._aggregate_delivery_stats")
    @patch(f"{_MONITOR}.TaskExecutionTracker")
    def test_in_flight_raises_task_in_progress(self, tracker_cls, agg_mock, emit_mock):
        from tasks.notifications.dispatch_monitor import _monitor

        tracker = self._tracker(self._summary(triggered=2, completed=1))
        tracker_cls.return_value = tracker

        with self.assertRaises(TaskInProgressError):
            _monitor("weekly-x", db_session=MagicMock())

        emit_mock.assert_not_called()
        tracker.finish_run.assert_not_called()

    @patch(f"{_MONITOR}._emit_summary")
    @patch(f"{_MONITOR}._aggregate_delivery_stats")
    @patch(f"{_MONITOR}.TaskExecutionTracker")
    def test_past_deadline_emits_incomplete_summary(
        self, tracker_cls, agg_mock, emit_mock
    ):
        from tasks.notifications.dispatch_monitor import _monitor

        # still 2 in flight, but started long ago beyond the deadline
        tracker = self._tracker(
            self._summary(
                triggered=2,
                completed=1,
                started_minutes_ago=600,
                deadline_seconds=60,
            )
        )
        tracker_cls.return_value = tracker
        agg_mock.return_value = {
            "events_found": 1,
            "emails_sent": 1,
            "emails_failed": 0,
            "permanently_failed": 0,
        }

        result = _monitor("weekly-x", db_session=MagicMock())

        emit_mock.assert_called_once()
        tracker.finish_run.assert_called_once()
        self.assertEqual(result["incomplete_workers"], 2)

    @patch(f"{_MONITOR}._emit_summary")
    @patch(f"{_MONITOR}._aggregate_delivery_stats")
    @patch(f"{_MONITOR}.TaskExecutionTracker")
    def test_already_complete_is_noop(self, tracker_cls, agg_mock, emit_mock):
        from tasks.notifications.dispatch_monitor import _monitor

        tracker = self._tracker(
            self._summary(triggered=0, completed=3, run_status="completed")
        )
        tracker_cls.return_value = tracker

        result = _monitor("weekly-x", db_session=MagicMock())

        emit_mock.assert_not_called()
        tracker.finish_run.assert_not_called()
        self.assertEqual(result["status"], "already_complete")

    @patch(f"{_MONITOR}._emit_summary")
    @patch(f"{_MONITOR}._aggregate_delivery_stats")
    @patch(f"{_MONITOR}.TaskExecutionTracker")
    def test_unknown_run_is_noop(self, tracker_cls, agg_mock, emit_mock):
        from tasks.notifications.dispatch_monitor import _monitor

        tracker = self._tracker(
            {
                "run_status": None,
                "total_count": None,
                "pending": 0,
                "triggered": 0,
                "completed": 0,
                "failed": 0,
                "params": None,
            }
        )
        tracker_cls.return_value = tracker

        result = _monitor("weekly-x", db_session=MagicMock())

        emit_mock.assert_not_called()
        self.assertEqual(result["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
