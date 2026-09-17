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
"""The four states, and the rule that a build is never started twice.

Mock-style: a `db_session` passed explicitly bypasses the `with_db_session` decorator,
so these run without a database. What matters here is the mapping from a tracking row
to the state a viewer renders, which is pure logic.
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from feeds_operations.impl import parquet_api_impl
from feeds_operations.impl.parquet_api_impl import ParquetApiImpl

FEED = "mdb-1210"
DATASET = "mdb-1210-202402121801"
BASE_URL = f"https://files.example.org/{FEED}/{DATASET}/parquet"
GENERATED_AT = datetime(2026, 9, 16, 14, 22, 31, tzinfo=timezone.utc)


def _entities():
    feed, dataset = MagicMock(), MagicMock()
    feed.stable_id = FEED
    dataset.stable_id = DATASET
    dataset.feed = feed
    feed.latest_dataset = dataset
    return feed, dataset


def _row(status, metadata=None, error_message=None, completed_at=None):
    row = MagicMock()
    row.status = status
    row.metadata_ = metadata
    row.error_message = error_message
    row.completed_at = completed_at
    return row


class ParquetStateTestCase(unittest.TestCase):
    """Shared plumbing: a resolved feed/dataset and a stubbed tracker."""

    def setUp(self):
        self.feed, self.dataset = _entities()
        self.tracker = MagicMock()
        self.tracker.get_entity.return_value = None

        self._resolve_patch = patch.object(
            parquet_api_impl, "_resolve", return_value=(self.feed, self.dataset)
        )
        self._tracker_patch = patch.object(
            parquet_api_impl, "TaskExecutionTracker", return_value=self.tracker
        )
        self._enqueue_patch = patch.object(
            parquet_api_impl, "create_http_parquet_builder_task"
        )
        self._resolve_patch.start()
        self._tracker_patch.start()
        self.enqueue = self._enqueue_patch.start()
        self.addCleanup(self._resolve_patch.stop)
        self.addCleanup(self._tracker_patch.stop)
        self.addCleanup(self._enqueue_patch.stop)

        self.api = ParquetApiImpl()

    def status(self):
        return self.api.handle_status(dataset_stable_id=DATASET, db_session=MagicMock())

    def generate(self, force=False):
        return self.api.handle_generate(
            dataset_stable_id=DATASET, force=force, db_session=MagicMock()
        )


class TestStatus(ParquetStateTestCase):
    def test_untracked_dataset_is_absent_not_an_error(self):
        """`absent` is the ordinary first answer; a 404 here would read as a failure."""
        state = self.status()

        self.assertEqual(state.status, "absent")
        self.assertEqual(state.feed_stable_id, FEED)
        self.assertEqual(state.dataset_stable_id, DATASET)
        self.assertIsNone(state.base_url)

    def test_in_progress_reports_the_phase_it_reached(self):
        self.tracker.get_entity.return_value = _row(
            "in_progress",
            metadata={
                "phase": "convert",
                "done": 12,
                "total": 32,
                "detail": "stop_times",
            },
        )

        state = self.status()

        self.assertEqual(state.status, "preparing")
        self.assertEqual(
            (state.phase, state.done, state.total, state.detail),
            ("convert", 12, 32, "stop_times"),
        )

    def test_a_claim_with_no_reading_yet_still_reports_preparing(self):
        self.tracker.get_entity.return_value = _row("in_progress", metadata=None)

        state = self.status()

        self.assertEqual(state.status, "preparing")
        self.assertEqual(state.phase, "start")

    def test_completed_reports_where_the_files_are(self):
        self.tracker.get_entity.return_value = _row(
            "completed",
            metadata={
                "base_url": BASE_URL,
                "tables": [{"name": "stops", "rows": 4821, "bytes": 148213}],
            },
            completed_at=GENERATED_AT,
        )

        state = self.status()

        self.assertEqual(state.status, "ready")
        self.assertEqual(state.base_url, BASE_URL)
        self.assertEqual([t.name for t in state.tables], ["stops"])
        self.assertEqual(state.tables[0].rows, 4821)
        self.assertEqual(state.generated_at, GENERATED_AT)

    def test_failed_reports_the_reason_verbatim(self):
        """The viewer shows this to an operator, so a generic string would waste it."""
        self.tracker.get_entity.return_value = _row(
            "failed", error_message="Conversion ran out of memory"
        )

        state = self.status()

        self.assertEqual(state.status, "failed")
        self.assertEqual(state.message, "Conversion ran out of memory")

    def test_failed_without_a_reason_still_says_something(self):
        self.tracker.get_entity.return_value = _row("failed", error_message=None)

        self.assertEqual(self.status().message, "The conversion failed.")

    def test_status_never_enqueues(self):
        """A client polls this twice a second."""
        self.status()

        self.enqueue.assert_not_called()


class TestGenerate(ParquetStateTestCase):
    def test_absent_enqueues_and_reports_preparing_immediately(self):
        state = self.generate()

        self.enqueue.assert_called_once_with(FEED, DATASET, force=False)
        # Not `absent` again: a client polling at 500ms would otherwise ask twice.
        self.assertEqual(state.status, "preparing")
        self.assertEqual(state.phase, "start")

    def test_the_enqueue_is_recorded_so_the_next_poll_sees_it(self):
        """Otherwise the gap before the worker starts reads as `absent` all over again."""
        self.generate()

        self.tracker.mark_triggered.assert_called_once()
        self.assertEqual(self.tracker.mark_triggered.call_args.args[0], DATASET)

    def test_nothing_is_recorded_when_the_enqueue_fails(self):
        self.enqueue.side_effect = RuntimeError("queue unreachable")

        with self.assertRaises(HTTPException):
            self.generate()

        self.tracker.mark_triggered.assert_not_called()

    def test_a_running_build_is_reported_not_duplicated(self):
        self.tracker.get_entity.return_value = _row(
            "in_progress",
            metadata={"phase": "convert", "done": 1, "total": 3, "detail": "stops"},
        )

        state = self.generate()

        self.enqueue.assert_not_called()
        self.assertEqual(state.status, "preparing")
        self.assertEqual(state.phase, "convert")

    def test_force_cannot_interrupt_a_running_build(self):
        self.tracker.get_entity.return_value = _row("in_progress", metadata={})

        state = self.generate(force=True)

        self.enqueue.assert_not_called()
        self.assertEqual(state.status, "preparing")

    def test_ready_is_returned_without_rebuilding(self):
        self.tracker.get_entity.return_value = _row(
            "completed", metadata={"base_url": BASE_URL, "tables": []}
        )

        state = self.generate()

        self.enqueue.assert_not_called()
        self.assertEqual(state.status, "ready")

    def test_force_rebuilds_a_ready_dataset(self):
        self.tracker.get_entity.return_value = _row(
            "completed", metadata={"base_url": BASE_URL, "tables": []}
        )

        self.generate(force=True)

        self.enqueue.assert_called_once_with(FEED, DATASET, force=True)

    def test_a_failed_dataset_is_retried(self):
        self.tracker.get_entity.return_value = _row("failed", error_message="boom")

        state = self.generate()

        self.enqueue.assert_called_once_with(FEED, DATASET, force=False)
        self.assertEqual(state.status, "preparing")

    def test_an_enqueue_failure_is_a_500_not_a_silent_success(self):
        self.enqueue.side_effect = RuntimeError("queue unreachable")

        with self.assertRaises(HTTPException) as caught:
            self.generate()

        self.assertEqual(caught.exception.status_code, 500)


class TestResolution(unittest.TestCase):
    """404 means the feed or dataset does not exist - never that it is unconverted."""

    def test_unknown_dataset_is_404(self):
        session = MagicMock()
        session.query.return_value.filter.return_value.one_or_none.return_value = None

        with self.assertRaises(HTTPException) as caught:
            parquet_api_impl._resolve(session, None, "nope")

        self.assertEqual(caught.exception.status_code, 404)

    def test_unknown_feed_is_404(self):
        session = MagicMock()
        session.query.return_value.filter.return_value.one_or_none.return_value = None

        with self.assertRaises(HTTPException) as caught:
            parquet_api_impl._resolve(session, "nope", None)

        self.assertEqual(caught.exception.status_code, 404)

    def test_a_feed_with_no_dataset_is_404(self):
        feed = MagicMock()
        feed.stable_id = FEED
        feed.latest_dataset = None
        session = MagicMock()
        session.query.return_value.filter.return_value.one_or_none.return_value = feed

        with self.assertRaises(HTTPException) as caught:
            parquet_api_impl._resolve(session, FEED, None)

        self.assertEqual(caught.exception.status_code, 404)
        self.assertIn("no dataset", caught.exception.detail)

    def test_a_feed_resolves_to_its_latest_dataset(self):
        feed, dataset = _entities()
        session = MagicMock()
        session.query.return_value.filter.return_value.one_or_none.return_value = feed

        resolved_feed, resolved_dataset = parquet_api_impl._resolve(session, FEED, None)

        self.assertIs(resolved_feed, feed)
        self.assertIs(resolved_dataset, dataset)


class TestForceFlag(unittest.TestCase):
    def test_absent_body_is_not_a_force(self):
        self.assertFalse(parquet_api_impl._force(None))

    def test_explicit_force(self):
        request = MagicMock()
        request.force = True
        self.assertTrue(parquet_api_impl._force(request))

    def test_null_force_is_not_a_force(self):
        request = MagicMock()
        request.force = None
        self.assertFalse(parquet_api_impl._force(request))


if __name__ == "__main__":
    unittest.main()
