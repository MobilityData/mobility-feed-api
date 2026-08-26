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

"""Unit tests for the seal backfill Cloud Tasks fan-out (issue #1763).

Mirrors test_seal_orchestrator_fanout.py: the producer/worker orchestration with the DB and
Cloud Tasks boundaries mocked. The march itself is covered against the real database by
test_seal_backfill.py.
"""

import unittest
from datetime import date
from unittest.mock import patch

_FANOUT = "tasks.seal_of_reliability.fanout"
_PLAN = "tasks.seal_of_reliability.backfill.seal_backfill_orchestrator"
_WORKER = "tasks.seal_of_reliability.backfill.seal_backfill_worker"

START = date(2025, 6, 1)
END = date(2026, 6, 1)


class TestBackfillOrchestrator(unittest.TestCase):
    @patch(f"{_FANOUT}.start_run")
    @patch(f"{_FANOUT}.enqueue_task", return_value=True)
    @patch(f"{_PLAN}.iter_eligible_stable_ids")
    @patch(f"{_PLAN}.count_eligible_feeds", return_value=5)
    def test_enqueues_worker_per_batch_plus_monitor(
        self, count_mock, iter_mock, enqueue_mock, start_run_mock
    ):
        from tasks.seal_of_reliability.backfill.seal_backfill_orchestrator import (
            seal_backfill_orchestrator_handler,
        )

        iter_mock.return_value = iter(
            [["mdb-1", "mdb-2"], ["mdb-3", "mdb-4"], ["mdb-5"]]
        )

        result = seal_backfill_orchestrator_handler(
            {
                "dry_run": False,
                "batch_size": 2,
                "start_date": START.isoformat(),
                "end_date": END.isoformat(),
            }
        )

        start_run_mock.assert_called_once()
        in_body = [c.kwargs["in_body_task"] for c in enqueue_mock.call_args_list]
        self.assertEqual(in_body.count("seal_backfill_worker"), 3)
        self.assertEqual(in_body.count("seal_orchestrator_monitor"), 1)
        self.assertEqual(result["total_feeds"], 5)
        self.assertEqual(result["batches"], 3)
        self.assertEqual(result["enqueued"], 3)

    @patch(f"{_FANOUT}.start_run")
    @patch(f"{_FANOUT}.enqueue_task", return_value=True)
    @patch(f"{_PLAN}.iter_eligible_stable_ids")
    @patch(f"{_PLAN}.count_eligible_feeds", return_value=2)
    def test_every_worker_gets_the_same_explicit_window(
        self, count_mock, iter_mock, enqueue_mock, start_run_mock
    ):
        """The whole reason the producer resolves the window.

        Left to each worker to default, two started either side of midnight would march to
        different final days.
        """
        from tasks.seal_of_reliability.backfill.seal_backfill_orchestrator import (
            seal_backfill_orchestrator_handler,
        )

        iter_mock.return_value = iter([["mdb-1"], ["mdb-2"]])
        seal_backfill_orchestrator_handler(
            {
                "dry_run": False,
                "batch_size": 1,
                "start_date": START.isoformat(),
                "end_date": END.isoformat(),
            }
        )

        windows = [
            (c.kwargs["payload"]["start_date"], c.kwargs["payload"]["end_date"])
            for c in enqueue_mock.call_args_list
            if c.kwargs["in_body_task"] == "seal_backfill_worker"
        ]
        self.assertEqual(windows, [(START.isoformat(), END.isoformat())] * 2)

    @patch(f"{_FANOUT}.start_run")
    @patch(f"{_FANOUT}.enqueue_task", return_value=True)
    @patch(f"{_PLAN}.iter_eligible_stable_ids")
    @patch(f"{_PLAN}.count_eligible_feeds", return_value=1)
    def test_the_monitor_is_told_which_tracker_to_settle(
        self, count_mock, iter_mock, enqueue_mock, start_run_mock
    ):
        """The monitor is shared with the nightly run, so the task_name has to travel."""
        from tasks.seal_of_reliability.backfill.seal_backfill_orchestrator import (
            SEAL_BACKFILL_TASK_NAME,
            seal_backfill_orchestrator_handler,
        )

        iter_mock.return_value = iter([["mdb-1"]])
        seal_backfill_orchestrator_handler(
            {"dry_run": False, "end_date": END.isoformat()}
        )

        monitor = next(
            c
            for c in enqueue_mock.call_args_list
            if c.kwargs["in_body_task"] == "seal_orchestrator_monitor"
        )
        self.assertEqual(
            monitor.kwargs["payload"]["task_name"], SEAL_BACKFILL_TASK_NAME
        )

    @patch(f"{_FANOUT}.start_run")
    @patch(f"{_FANOUT}.enqueue_task", return_value=True)
    @patch(f"{_PLAN}.iter_eligible_stable_ids")
    @patch(f"{_PLAN}.count_eligible_feeds", return_value=3)
    def test_only_missing_narrows_the_candidate_set(
        self, count_mock, iter_mock, enqueue_mock, start_run_mock
    ):
        """#1763's scope: feeds with no stored state. It is the eligibility predicate."""
        from tasks.seal_of_reliability.backfill.seal_backfill_orchestrator import (
            seal_backfill_orchestrator_handler,
        )

        iter_mock.return_value = iter([["mdb-1", "mdb-2", "mdb-3"]])
        seal_backfill_orchestrator_handler(
            {"dry_run": False, "end_date": END.isoformat()}
        )

        self.assertTrue(count_mock.call_args.kwargs["exclude_backfilled"])
        self.assertTrue(iter_mock.call_args.kwargs["exclude_backfilled"])

    @patch(f"{_FANOUT}.start_run")
    @patch(f"{_FANOUT}.enqueue_task", return_value=True)
    @patch(f"{_PLAN}.iter_eligible_stable_ids")
    @patch(f"{_PLAN}.count_eligible_feeds", return_value=3)
    def test_only_missing_false_widens_it(
        self, count_mock, iter_mock, enqueue_mock, start_run_mock
    ):
        from tasks.seal_of_reliability.backfill.seal_backfill_orchestrator import (
            seal_backfill_orchestrator_handler,
        )

        iter_mock.return_value = iter([["mdb-1", "mdb-2", "mdb-3"]])
        seal_backfill_orchestrator_handler(
            {"dry_run": False, "end_date": END.isoformat(), "only_missing": False}
        )

        self.assertFalse(count_mock.call_args.kwargs["exclude_backfilled"])

    @patch(f"{_FANOUT}.start_run")
    @patch(f"{_FANOUT}.enqueue_task")
    @patch(f"{_PLAN}.iter_eligible_stable_ids")
    @patch(f"{_PLAN}.count_eligible_feeds", return_value=4)
    def test_dry_run_enqueues_nothing(
        self, count_mock, iter_mock, enqueue_mock, start_run_mock
    ):
        from tasks.seal_of_reliability.backfill.seal_backfill_orchestrator import (
            seal_backfill_orchestrator_handler,
        )

        result = seal_backfill_orchestrator_handler({"end_date": END.isoformat()})

        enqueue_mock.assert_not_called()
        start_run_mock.assert_not_called()
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["enqueued"], 0)
        self.assertEqual(result["total_feeds"], 4)

    @patch(f"{_FANOUT}.mark_enqueue_failed")
    @patch(f"{_FANOUT}.start_run")
    @patch(f"{_FANOUT}.enqueue_task", return_value=False)
    @patch(f"{_PLAN}.iter_eligible_stable_ids")
    @patch(f"{_PLAN}.count_eligible_feeds", return_value=2)
    def test_a_failed_enqueue_fails_its_batch_immediately(
        self, count_mock, iter_mock, enqueue_mock, start_run_mock, failed_mock
    ):
        """Otherwise the batch sits `triggered` until the deadline forces the run failed."""
        from tasks.seal_of_reliability.backfill.seal_backfill_orchestrator import (
            seal_backfill_orchestrator_handler,
        )

        iter_mock.return_value = iter([["mdb-1"], ["mdb-2"]])
        result = seal_backfill_orchestrator_handler(
            {"dry_run": False, "batch_size": 1, "end_date": END.isoformat()}
        )

        self.assertEqual(result["enqueued"], 0)
        self.assertEqual(failed_mock.call_count, 2)

    def test_a_bad_window_fails_at_the_producer(self):
        """One failure at the producer beats the same failure once per batch."""
        from tasks.seal_of_reliability.backfill.seal_backfill_orchestrator import (
            seal_backfill_orchestrator_handler,
        )

        with self.assertRaises(ValueError):
            seal_backfill_orchestrator_handler(
                {
                    "start_date": END.isoformat(),
                    "end_date": START.isoformat(),
                }
            )

    def test_an_unknown_snapshot_mode_fails_at_the_producer(self):
        from tasks.seal_of_reliability.backfill.seal_backfill_orchestrator import (
            seal_backfill_orchestrator_handler,
        )

        with self.assertRaises(ValueError):
            seal_backfill_orchestrator_handler({"snapshot_mode": "occasionally"})


class TestBackfillWorker(unittest.TestCase):
    @patch(f"{_WORKER}._mark_entry")
    @patch(f"{_WORKER}.backfill_seals", return_value={"total_feeds": 2})
    def test_marks_the_batch_completed(self, backfill_mock, mark_mock):
        from tasks.seal_of_reliability.backfill.seal_backfill_worker import (
            seal_backfill_worker_handler,
        )

        result = seal_backfill_worker_handler(
            {
                "run_id": "r1",
                "batch_id": "batch-0000",
                "stable_feed_ids": ["mdb-1", "mdb-2"],
                "start_date": START.isoformat(),
                "end_date": END.isoformat(),
            }
        )

        self.assertEqual(result["status"], "ok")
        self.assertFalse(backfill_mock.call_args.kwargs["dry_run"])
        self.assertEqual(backfill_mock.call_args.kwargs["start_date"], START)
        self.assertEqual(backfill_mock.call_args.kwargs["end_date"], END)
        mark_mock.assert_called_once()
        self.assertEqual(mark_mock.call_args.kwargs["result"], {"total_feeds": 2})

    @patch(f"{_WORKER}._mark_entry")
    @patch(f"{_WORKER}.backfill_seals", side_effect=RuntimeError("db down"))
    def test_marks_the_batch_failed_and_re_raises(self, backfill_mock, mark_mock):
        """Re-raised so Cloud Tasks retries; the tracker entry records the reason."""
        from tasks.seal_of_reliability.backfill.seal_backfill_worker import (
            seal_backfill_worker_handler,
        )

        with self.assertRaises(RuntimeError):
            seal_backfill_worker_handler(
                {
                    "run_id": "r1",
                    "batch_id": "batch-0000",
                    "stable_feed_ids": ["mdb-1"],
                    "start_date": START.isoformat(),
                    "end_date": END.isoformat(),
                }
            )
        self.assertIn("db down", mark_mock.call_args.kwargs["error"])

    def test_a_worker_never_defaults_the_window(self):
        """The run's window belongs to the run, not to when a batch happened to execute."""
        from tasks.seal_of_reliability.backfill.seal_backfill_worker import (
            seal_backfill_worker_handler,
        )

        with self.assertRaises(ValueError) as caught:
            seal_backfill_worker_handler(
                {
                    "run_id": "r1",
                    "batch_id": "batch-0000",
                    "stable_feed_ids": ["mdb-1"],
                    "start_date": START.isoformat(),
                }
            )
        self.assertIn("end_date", str(caught.exception))

    def test_required_fields_are_checked(self):
        from tasks.seal_of_reliability.backfill.seal_backfill_worker import (
            seal_backfill_worker_handler,
        )

        for payload in (
            {"batch_id": "b", "stable_feed_ids": ["mdb-1"]},
            {"run_id": "r", "stable_feed_ids": ["mdb-1"]},
            {"run_id": "r", "batch_id": "b", "stable_feed_ids": []},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    seal_backfill_worker_handler(payload)


class TestSharedMonitor(unittest.TestCase):
    def test_it_defaults_to_the_nightly_tracker(self):
        from tasks.seal_of_reliability.orchestrator.seal_orchestrator import (
            SEAL_ORCHESTRATOR_TASK_NAME,
        )
        from tasks.seal_of_reliability.orchestrator import seal_orchestrator_monitor

        with patch.object(seal_orchestrator_monitor, "_monitor") as monitor_mock:
            seal_orchestrator_monitor.seal_orchestrator_monitor_handler(
                {"run_id": "r1"}
            )
        self.assertEqual(monitor_mock.call_args.args[1], SEAL_ORCHESTRATOR_TASK_NAME)

    def test_it_settles_the_backfill_tracker_when_told_to(self):
        from tasks.seal_of_reliability.backfill.seal_backfill_orchestrator import (
            SEAL_BACKFILL_TASK_NAME,
        )
        from tasks.seal_of_reliability.orchestrator import seal_orchestrator_monitor

        with patch.object(seal_orchestrator_monitor, "_monitor") as monitor_mock:
            seal_orchestrator_monitor.seal_orchestrator_monitor_handler(
                {"run_id": "r1", "task_name": SEAL_BACKFILL_TASK_NAME}
            )
        self.assertEqual(monitor_mock.call_args.args[1], SEAL_BACKFILL_TASK_NAME)


class TestBatchSizeDefault(unittest.TestCase):
    def test_backfill_batches_are_smaller_than_nightly_ones(self):
        """A batch marches a year per feed, so its cost scales with days as well as feeds."""
        from tasks.seal_of_reliability.backfill import seal_backfill_orchestrator
        from tasks.seal_of_reliability.orchestrator import seal_orchestrator

        self.assertLess(
            seal_backfill_orchestrator.DEFAULT_BATCH_SIZE,
            seal_orchestrator.DEFAULT_BATCH_SIZE,
        )
        self.assertGreater(
            seal_backfill_orchestrator.DEFAULT_DEADLINE_SECONDS,
            seal_orchestrator.DEFAULT_DEADLINE_SECONDS,
        )


if __name__ == "__main__":
    unittest.main()
