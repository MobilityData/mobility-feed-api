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

"""Unit tests for the seal orchestrator Cloud Tasks fan-out (issue #1800).

Mirrors test_dispatch_fanout.py: covers the producer/worker/monitor orchestration
with the DB / Cloud Tasks boundaries mocked. The real `update_seals` evaluation
behaviour is covered by test_seal_updater_db.py / test_seal_end_to_end_db.py against
the real feeds database.
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from shared.helpers.task_execution.task_execution_tracker import TaskInProgressError

# ---------------------------------------------------------------------------
# seal_orchestrator (producer)
# ---------------------------------------------------------------------------

_PLAN = "tasks.seal_of_reliability.seal_orchestrator"


class TestSealOrchestratorHandler(unittest.TestCase):
    def _feeds(self, *stable_ids):
        return [MagicMock(stable_id=stable_id) for stable_id in stable_ids]

    @patch(f"{_PLAN}._start_run")
    @patch(f"{_PLAN}._enqueue", return_value=True)
    @patch(f"{_PLAN}.get_seal_feeds_query")
    def test_enqueues_worker_per_batch_plus_monitor(
        self, query_mock, enqueue_mock, start_run_mock
    ):
        from tasks.seal_of_reliability.seal_orchestrator import (
            seal_orchestrator_handler,
        )

        query_mock.return_value.order_by.return_value.all.return_value = self._feeds(
            "mdb-1", "mdb-2", "mdb-3", "mdb-4", "mdb-5"
        )

        result = seal_orchestrator_handler({"dry_run": False, "batch_size": 2})

        # 3 batches of at most 2 feeds each (2, 2, 1)
        start_run_mock.assert_called_once()
        self.assertEqual(enqueue_mock.call_count, 4)  # 3 workers + 1 monitor
        in_body_tasks = [c.kwargs["in_body_task"] for c in enqueue_mock.call_args_list]
        self.assertEqual(in_body_tasks.count("seal_orchestrator_worker"), 3)
        self.assertEqual(in_body_tasks.count("seal_orchestrator_monitor"), 1)
        self.assertEqual(result["total_feeds"], 5)
        self.assertEqual(result["batches"], 3)
        self.assertEqual(result["enqueued"], 3)
        self.assertFalse(result["dry_run"])

    @patch(f"{_PLAN}._start_run")
    @patch(f"{_PLAN}._enqueue", return_value=True)
    @patch(f"{_PLAN}.get_seal_feeds_query")
    def test_dynamic_task_names_use_prefix(
        self, query_mock, enqueue_mock, start_run_mock
    ):
        from tasks.seal_of_reliability.seal_orchestrator import (
            seal_orchestrator_handler,
        )

        query_mock.return_value.order_by.return_value.all.return_value = self._feeds(
            "mdb-1"
        )
        seal_orchestrator_handler({"dry_run": False, "batch_size": 250})

        names = [c.kwargs["task_name"] for c in enqueue_mock.call_args_list]
        self.assertTrue(all(n.startswith("seal-orchestrator-") for n in names))
        self.assertTrue(any(n.startswith("seal-orchestrator-monitor-") for n in names))

    @patch(f"{_PLAN}._start_run")
    @patch(f"{_PLAN}._enqueue", return_value=True)
    @patch(f"{_PLAN}.get_seal_feeds_query")
    def test_dry_run_enqueues_nothing(self, query_mock, enqueue_mock, start_run_mock):
        from tasks.seal_of_reliability.seal_orchestrator import (
            seal_orchestrator_handler,
        )

        query_mock.return_value.order_by.return_value.all.return_value = self._feeds(
            "mdb-1", "mdb-2"
        )
        result = seal_orchestrator_handler({"dry_run": True, "batch_size": 1})

        enqueue_mock.assert_not_called()
        start_run_mock.assert_not_called()
        self.assertEqual(result["enqueued"], 0)
        self.assertEqual(result["batches"], 2)

    @patch(f"{_PLAN}._start_run")
    @patch(f"{_PLAN}._enqueue", return_value=True)
    @patch(f"{_PLAN}.get_seal_feeds_query")
    def test_no_eligible_feeds_enqueues_nothing(
        self, query_mock, enqueue_mock, start_run_mock
    ):
        from tasks.seal_of_reliability.seal_orchestrator import (
            seal_orchestrator_handler,
        )

        query_mock.return_value.order_by.return_value.all.return_value = []
        result = seal_orchestrator_handler({"dry_run": False})

        enqueue_mock.assert_not_called()
        start_run_mock.assert_not_called()
        self.assertEqual(result["enqueued"], 0)
        self.assertEqual(result["batches"], 0)

    @patch(f"{_PLAN}._mark_enqueue_failed")
    @patch(f"{_PLAN}._start_run")
    @patch(f"{_PLAN}._enqueue")
    @patch(f"{_PLAN}.get_seal_feeds_query")
    def test_failed_enqueue_marks_batch_failed_immediately(
        self, query_mock, enqueue_mock, start_run_mock, mark_failed_mock
    ):
        from tasks.seal_of_reliability.seal_orchestrator import (
            seal_orchestrator_handler,
        )

        query_mock.return_value.order_by.return_value.all.return_value = self._feeds(
            "mdb-1"
        )
        enqueue_mock.side_effect = [False, True]

        seal_orchestrator_handler({"dry_run": False, "batch_size": 1})

        mark_failed_mock.assert_called_once()
        call_args = mark_failed_mock.call_args[0]
        self.assertTrue(call_args[0].startswith("seal-"))
        self.assertEqual(call_args[1], "batch-0000")


# ---------------------------------------------------------------------------
# seal_orchestrator_worker
# ---------------------------------------------------------------------------

_WORKER = "tasks.seal_of_reliability.seal_orchestrator_worker"


class TestSealOrchestratorWorkerHandler(unittest.TestCase):
    def test_requires_run_id_and_batch_id(self):
        from tasks.seal_of_reliability.seal_orchestrator_worker import (
            seal_orchestrator_worker_handler,
        )

        with self.assertRaises(ValueError):
            seal_orchestrator_worker_handler(
                {"batch_id": "batch-0000", "stable_feed_ids": ["mdb-1"]}
            )
        with self.assertRaises(ValueError):
            seal_orchestrator_worker_handler(
                {"run_id": "r1", "stable_feed_ids": ["mdb-1"]}
            )

    def test_requires_non_empty_stable_feed_ids(self):
        from tasks.seal_of_reliability.seal_orchestrator_worker import (
            seal_orchestrator_worker_handler,
        )

        with self.assertRaises(ValueError):
            seal_orchestrator_worker_handler(
                {"run_id": "r1", "batch_id": "batch-0000", "stable_feed_ids": []}
            )

    @patch(f"{_WORKER}._mark_entry")
    @patch(f"{_WORKER}.update_seals")
    def test_marks_completed_with_result_metadata_on_success(
        self, update_mock, mark_mock
    ):
        from tasks.seal_of_reliability.seal_orchestrator_worker import (
            seal_orchestrator_worker_handler,
        )

        update_mock.return_value = {"total_feeds": 2, "seals_granted": 1}
        result = seal_orchestrator_worker_handler(
            {
                "run_id": "r1",
                "batch_id": "batch-0000",
                "stable_feed_ids": ["mdb-1", "mdb-2"],
            }
        )

        update_mock.assert_called_once()
        self.assertEqual(
            update_mock.call_args.kwargs["stable_feed_ids"], ["mdb-1", "mdb-2"]
        )
        self.assertFalse(update_mock.call_args.kwargs["dry_run"])
        mark_mock.assert_called_once_with(
            "r1", "batch-0000", result={"total_feeds": 2, "seals_granted": 1}
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["seals_granted"], 1)

    @patch(f"{_WORKER}._mark_entry")
    @patch(f"{_WORKER}.update_seals")
    def test_infra_error_marks_failed_and_reraises(self, update_mock, mark_mock):
        from tasks.seal_of_reliability.seal_orchestrator_worker import (
            seal_orchestrator_worker_handler,
        )

        update_mock.side_effect = RuntimeError("db down")
        with self.assertRaises(RuntimeError):
            seal_orchestrator_worker_handler(
                {"run_id": "r1", "batch_id": "batch-0000", "stable_feed_ids": ["mdb-1"]}
            )

        mark_mock.assert_called_once_with("r1", "batch-0000", error="db down")

    @patch(f"{_WORKER}._mark_entry")
    @patch(f"{_WORKER}.update_seals")
    def test_now_and_criteria_are_forwarded(self, update_mock, mark_mock):
        from tasks.seal_of_reliability.seal_orchestrator_worker import (
            seal_orchestrator_worker_handler,
        )

        update_mock.return_value = {"total_feeds": 1}
        seal_orchestrator_worker_handler(
            {
                "run_id": "r1",
                "batch_id": "batch-0000",
                "stable_feed_ids": ["mdb-1"],
                "criteria": ["official"],
                "now": "2026-01-01T00:00:00+00:00",
            }
        )

        kwargs = update_mock.call_args.kwargs
        self.assertEqual(kwargs["criteria"], ["official"])
        self.assertEqual(kwargs["now"], datetime(2026, 1, 1, tzinfo=timezone.utc))


# ---------------------------------------------------------------------------
# seal_orchestrator_monitor (barrier / summary)
# ---------------------------------------------------------------------------

_MONITOR = "tasks.seal_of_reliability.seal_orchestrator_monitor"


class TestSealOrchestratorMonitorHandler(unittest.TestCase):
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
        deadline_seconds=3600,
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
                "run_started_at": started.isoformat(),
                "deadline_seconds": deadline_seconds,
            },
        }

    def test_requires_run_id(self):
        from tasks.seal_of_reliability.seal_orchestrator_monitor import (
            seal_orchestrator_monitor_handler,
        )

        with self.assertRaises(ValueError):
            seal_orchestrator_monitor_handler({})

    @patch(f"{_MONITOR}._aggregate_batches")
    @patch(f"{_MONITOR}.TaskExecutionTracker")
    def test_settled_success_marks_completed(self, tracker_cls, agg_mock):
        from tasks.seal_of_reliability.seal_orchestrator_monitor import _monitor

        tracker = self._tracker(self._summary(triggered=0, completed=3))
        tracker_cls.return_value = tracker
        agg_mock.return_value = {
            "total_feeds_evaluated": 750,
            "criterion_rows_written": 750,
            "seals_granted": 5,
            "seals_revoked": 1,
            "granted_stable_ids": ["mdb-1"],
            "revoked_stable_ids": ["mdb-2"],
            "ids_omitted": 0,
        }

        result = _monitor("seal-x", db_session=MagicMock())

        tracker.finish_run.assert_called_once_with(status="completed")
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["batches_completed"], 3)
        self.assertEqual(result["seals_granted"], 5)

    @patch(f"{_MONITOR}._aggregate_batches")
    @patch(f"{_MONITOR}.TaskExecutionTracker")
    def test_in_flight_raises_task_in_progress(self, tracker_cls, agg_mock):
        from tasks.seal_of_reliability.seal_orchestrator_monitor import _monitor

        tracker = self._tracker(self._summary(triggered=2, completed=1))
        tracker_cls.return_value = tracker

        with self.assertRaises(TaskInProgressError):
            _monitor("seal-x", db_session=MagicMock())

        agg_mock.assert_not_called()
        tracker.finish_run.assert_not_called()

    @patch(f"{_MONITOR}._aggregate_batches")
    @patch(f"{_MONITOR}.TaskExecutionTracker")
    def test_any_failed_batch_marks_run_failed(self, tracker_cls, agg_mock):
        from tasks.seal_of_reliability.seal_orchestrator_monitor import _monitor

        # drained (triggered=0) but one batch failed
        tracker = self._tracker(self._summary(triggered=0, completed=2, failed=1))
        tracker_cls.return_value = tracker
        agg_mock.return_value = {
            "total_feeds_evaluated": 500,
            "criterion_rows_written": 500,
            "seals_granted": 0,
            "seals_revoked": 0,
            "granted_stable_ids": [],
            "revoked_stable_ids": [],
            "ids_omitted": 0,
        }

        result = _monitor("seal-x", db_session=MagicMock())

        tracker.finish_run.assert_called_once_with(status="failed")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["batches_failed"], 1)

    @patch(f"{_MONITOR}._aggregate_batches")
    @patch(f"{_MONITOR}.TaskExecutionTracker")
    def test_past_deadline_settles_as_failed_with_incomplete_count(
        self, tracker_cls, agg_mock
    ):
        from tasks.seal_of_reliability.seal_orchestrator_monitor import _monitor

        # still 2 in flight, but started long ago beyond the deadline — this is the
        # scenario a dead worker must not be able to hang the monitor forever on.
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
            "total_feeds_evaluated": 250,
            "criterion_rows_written": 250,
            "seals_granted": 0,
            "seals_revoked": 0,
            "granted_stable_ids": [],
            "revoked_stable_ids": [],
            "ids_omitted": 0,
        }

        result = _monitor("seal-x", db_session=MagicMock())

        tracker.finish_run.assert_called_once_with(status="failed")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["batches_incomplete"], 2)

    @patch(f"{_MONITOR}._aggregate_batches")
    @patch(f"{_MONITOR}.TaskExecutionTracker")
    def test_already_complete_is_noop(self, tracker_cls, agg_mock):
        from tasks.seal_of_reliability.seal_orchestrator_monitor import _monitor

        tracker = self._tracker(
            self._summary(triggered=0, completed=3, run_status="completed")
        )
        tracker_cls.return_value = tracker

        result = _monitor("seal-x", db_session=MagicMock())

        agg_mock.assert_not_called()
        tracker.finish_run.assert_not_called()
        self.assertEqual(result["status"], "already_complete")

    @patch(f"{_MONITOR}._aggregate_batches")
    @patch(f"{_MONITOR}.TaskExecutionTracker")
    def test_already_failed_is_noop(self, tracker_cls, agg_mock):
        from tasks.seal_of_reliability.seal_orchestrator_monitor import _monitor

        tracker = self._tracker(
            self._summary(triggered=0, completed=2, failed=1, run_status="failed")
        )
        tracker_cls.return_value = tracker

        result = _monitor("seal-x", db_session=MagicMock())

        agg_mock.assert_not_called()
        tracker.finish_run.assert_not_called()
        self.assertEqual(result["status"], "already_complete")

    @patch(f"{_MONITOR}._aggregate_batches")
    @patch(f"{_MONITOR}.TaskExecutionTracker")
    def test_unknown_run_is_noop(self, tracker_cls, agg_mock):
        from tasks.seal_of_reliability.seal_orchestrator_monitor import _monitor

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

        result = _monitor("seal-x", db_session=MagicMock())

        agg_mock.assert_not_called()
        self.assertEqual(result["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
