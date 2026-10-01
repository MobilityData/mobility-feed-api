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

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from task_execution.task_execution_tracker import (
    TaskExecutionTracker,
    STATUS_IN_PROGRESS,
    STATUS_TRIGGERED,
    STATUS_COMPLETED,
    STATUS_FAILED,
)


def _make_tracker(task_name="test_task", run_id="v1.0"):
    """Return a tracker with a mock DB session."""
    session = MagicMock()
    tracker = TaskExecutionTracker(
        task_name=task_name, run_id=run_id, db_session=session
    )
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
        self.assertEqual(tracker.task_run_id, run_uuid)
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

        self.assertEqual(tracker.task_run_id, run_uuid)

    def test_start_run_resets_status_to_in_progress_on_rerun(self):
        """Re-running the same task_name/run_id must reset status and completed_at on conflict."""
        tracker, session = _make_tracker()
        run_uuid = uuid.uuid4()
        execute_result = MagicMock()
        execute_result.scalar_one.return_value = run_uuid
        session.execute.return_value = execute_result

        tracker.start_run(total_count=5)

        stmt_compiled = str(session.execute.call_args[0][0])
        # The ON CONFLICT DO UPDATE clause must include status and completed_at
        self.assertIn("DO UPDATE SET", stmt_compiled)
        self.assertIn("status", stmt_compiled)
        self.assertIn("completed_at", stmt_compiled)


class TestTaskExecutionTrackerIsTriggered(unittest.TestCase):
    def test_returns_true_when_triggered_row_exists(self):
        tracker, session = _make_tracker()
        existing_row = MagicMock()
        session.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            existing_row
        )

        result = tracker.is_triggered("ds-123")
        self.assertTrue(result)

    def test_returns_false_when_no_row(self):
        tracker, session = _make_tracker()
        session.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            None
        )

        result = tracker.is_triggered("ds-999")
        self.assertFalse(result)

    def test_handles_none_entity_id(self):
        tracker, session = _make_tracker()
        session.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            None
        )

        result = tracker.is_triggered(None)
        self.assertFalse(result)


class TestTaskExecutionTrackerMarkTriggered(unittest.TestCase):
    def test_mark_triggered_inserts_execution_log(self):
        tracker, session = _make_tracker()
        tracker.task_run_id = uuid.uuid4()

        tracker.mark_triggered("ds-1", execution_ref="projects/x/executions/abc")

        session.execute.assert_called_once()
        session.flush.assert_called_once()

    def test_mark_triggered_with_metadata(self):
        tracker, session = _make_tracker()
        tracker.task_run_id = uuid.uuid4()

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

    def test_mark_completed_with_metadata_stores_it(self):
        from task_execution.task_execution_tracker import TaskExecutionLog

        tracker, session = _make_tracker()
        query_mock = MagicMock()
        session.query.return_value.filter.return_value.filter.return_value = query_mock

        tracker.mark_completed("batch-0001", metadata={"seals_granted": 3})

        query_mock.update.assert_called_once()
        update_args = query_mock.update.call_args[0][0]
        self.assertEqual(update_args["status"], STATUS_COMPLETED)
        self.assertEqual(update_args[TaskExecutionLog.metadata_], {"seals_granted": 3})

    def test_mark_completed_without_metadata_omits_it(self):
        from task_execution.task_execution_tracker import TaskExecutionLog

        tracker, session = _make_tracker()
        query_mock = MagicMock()
        session.query.return_value.filter.return_value.filter.return_value = query_mock

        tracker.mark_completed("ds-1")

        update_args = query_mock.update.call_args[0][0]
        self.assertNotIn(TaskExecutionLog.metadata_, update_args)


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

        rows = [
            MagicMock(status=STATUS_TRIGGERED),
            MagicMock(status=STATUS_TRIGGERED),
            MagicMock(status=STATUS_COMPLETED),
            MagicMock(status=STATUS_FAILED),
        ]

        def query_side_effect(*args):
            m = MagicMock()
            m.filter.return_value.first.return_value = task_run
            m.filter.return_value.all.return_value = rows
            return m

        session.query.side_effect = query_side_effect

        summary = tracker.get_summary()
        self.assertEqual(summary["triggered"], 2)
        self.assertEqual(summary["completed"], 1)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["pending"], 1)  # 5 total - 4 processed

    def test_includes_metadata_summary_aggregated_across_entities(self):
        tracker, session = _make_tracker()
        task_run = self._make_task_run(total_count=2)
        rows = [
            MagicMock(
                status=STATUS_COMPLETED, metadata_={"seals_granted": 3, "ids": ["a"]}
            ),
            MagicMock(
                status=STATUS_COMPLETED, metadata_={"seals_granted": 2, "ids": ["b"]}
            ),
        ]

        def query_side_effect(*args):
            m = MagicMock()
            m.filter.return_value.first.return_value = task_run
            m.filter.return_value.all.return_value = rows
            return m

        session.query.side_effect = query_side_effect

        summary = tracker.get_summary()

        self.assertEqual(summary["metadata_summary"]["seals_granted"], 5)
        self.assertEqual(summary["metadata_summary"]["ids"], ["a", "b"])

    def test_no_run_found_has_empty_metadata_summary(self):
        tracker, session = _make_tracker()
        session.query.return_value.filter.return_value.first.return_value = None

        summary = tracker.get_summary()

        self.assertEqual(summary["metadata_summary"], {})


class TestAggregateMetadata(unittest.TestCase):
    """Direct tests of the generic per-entity metadata aggregation."""

    def test_sums_numbers_and_concatenates_lists(self):
        from task_execution.task_execution_tracker import TaskExecutionTracker

        result = TaskExecutionTracker._aggregate_metadata(
            [
                {"total": 10, "ids": ["a", "b"]},
                {"total": 5, "ids": ["c"]},
            ],
            list_cap=200,
        )
        self.assertEqual(result["total"], 15)
        self.assertEqual(result["ids"], ["a", "b", "c"])

    def test_caps_concatenated_lists_and_reports_omitted(self):
        from task_execution.task_execution_tracker import TaskExecutionTracker

        result = TaskExecutionTracker._aggregate_metadata(
            [{"ids": ["a", "b", "c"]}], list_cap=2
        )
        self.assertEqual(result["ids"], ["a", "b"])
        self.assertEqual(result["ids_omitted"], 1)

    def test_skips_non_dict_and_none_metadata(self):
        from task_execution.task_execution_tracker import TaskExecutionTracker

        result = TaskExecutionTracker._aggregate_metadata(
            [None, {"total": 4}, MagicMock()], list_cap=200
        )
        self.assertEqual(result, {"total": 4})

    def test_drops_dict_and_list_of_dict_fields(self):
        """Non-scalar fields (a nested dict, or a list of dicts) aren't summable or
        concatenable in a generic way, so they're left out rather than guessed at."""
        from task_execution.task_execution_tracker import TaskExecutionTracker

        result = TaskExecutionTracker._aggregate_metadata(
            [
                {
                    "total": 1,
                    "nested": {"a": 1},
                    "feeds": [{"stable_id": "mdb-1"}],
                }
            ],
            list_cap=200,
        )
        self.assertEqual(result, {"total": 1})

    def test_drops_bool_fields(self):
        """bool is an int subclass; summing True/False as a count would be misleading."""
        from task_execution.task_execution_tracker import TaskExecutionTracker

        result = TaskExecutionTracker._aggregate_metadata(
            [{"dry_run": False, "total": 1}], list_cap=200
        )
        self.assertEqual(result, {"total": 1})

    def test_drops_key_seen_with_inconsistent_types(self):
        """A key that's a number in one entity and a list in another is ambiguous —
        dropped entirely rather than silently aggregating only part of it."""
        from task_execution.task_execution_tracker import TaskExecutionTracker

        result = TaskExecutionTracker._aggregate_metadata(
            [{"x": 1}, {"x": ["a"]}, {"total": 9}], list_cap=200
        )
        self.assertNotIn("x", result)
        self.assertEqual(result["total"], 9)


# ----------------------------------------------------------------------------
# Exclusive claims
#
# Against a real Postgres, deliberately: the guarantee `try_acquire` provides is a
# Postgres one - a conditional upsert re-evaluated against the committed row under a
# row lock - and a mocked session would assert the shape of the statement while
# proving nothing about the exclusion it exists for.
# ----------------------------------------------------------------------------

import threading  # noqa: E402

import sqlalchemy  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from task_execution.task_execution_tracker import DEFAULT_LEASE_SECONDS  # noqa: E402
from shared.database_gen.sqlacodegen_models import TaskExecutionLog  # noqa: E402

TEST_DB_URL = "postgresql://postgres:postgres@localhost:54320/MobilityDatabaseTest"
CLAIM_TASK = "test_try_acquire"


def _engine_or_skip():
    try:
        engine = sqlalchemy.create_engine(TEST_DB_URL)
        with engine.connect():
            pass
        return engine
    except Exception as error:  # pragma: no cover - depends on the local environment
        raise unittest.SkipTest(f"test database unavailable: {error}")


class TestTryAcquire(unittest.TestCase):
    """One worker at a time, and a claim that cannot be lost forever."""

    @classmethod
    def setUpClass(cls):
        cls.engine = _engine_or_skip()
        cls.Session = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.entity = f"dataset-{uuid.uuid4()}"
        self.run_id = f"v{uuid.uuid4()}"
        self.session = self.Session()
        self.tracker = self._tracker(self.session)
        self.tracker.start_run()
        self.session.commit()

    def tearDown(self):
        self.session.query(TaskExecutionLog).filter(
            TaskExecutionLog.task_name == CLAIM_TASK,
            TaskExecutionLog.run_id == self.run_id,
        ).delete(synchronize_session=False)
        self.session.commit()
        self.session.close()

    def _tracker(self, session):
        return TaskExecutionTracker(
            task_name=CLAIM_TASK, run_id=self.run_id, db_session=session
        )

    def _row(self):
        return self.tracker.get_entity(self.entity)

    def _set_status(self, status, triggered_at=None):
        values = {"status": status}
        if triggered_at is not None:
            values["triggered_at"] = triggered_at
        self.session.query(TaskExecutionLog).filter(
            TaskExecutionLog.task_name == CLAIM_TASK,
            TaskExecutionLog.run_id == self.run_id,
            TaskExecutionLog.entity_id == self.entity,
        ).update(values, synchronize_session=False)
        self.session.commit()

    def test_claims_an_untracked_entity(self):
        self.assertTrue(self.tracker.try_acquire(self.entity))
        self.session.commit()
        self.assertEqual(self._row().status, STATUS_IN_PROGRESS)

    def test_refuses_a_second_claim_while_held(self):
        self.assertTrue(self.tracker.try_acquire(self.entity))
        self.session.commit()

        other = self.Session()
        try:
            self.assertFalse(self._tracker(other).try_acquire(self.entity))
            other.commit()
        finally:
            other.close()

    def test_takes_over_from_a_merely_triggered_row(self):
        """The API records the enqueue; the worker that runs it must still claim."""
        self.tracker.mark_triggered(self.entity)
        self.session.commit()

        self.assertTrue(self.tracker.try_acquire(self.entity))

    def test_reclaims_a_failed_entity(self):
        self.tracker.try_acquire(self.entity)
        self.tracker.mark_failed(self.entity, error_message="boom")
        self.session.commit()

        self.assertTrue(self.tracker.try_acquire(self.entity))
        self.session.commit()
        self.assertIsNone(
            self._row().error_message, "a retry starts without the old error"
        )

    def test_never_reclaims_a_completed_entity(self):
        self.tracker.try_acquire(self.entity)
        self.tracker.mark_completed(self.entity, metadata={"base_url": "x"})
        self.session.commit()

        self.assertFalse(self.tracker.try_acquire(self.entity))

    def test_release_for_retry_reopens_a_completed_entity(self):
        self.tracker.try_acquire(self.entity)
        self.tracker.mark_completed(self.entity)
        self.session.commit()

        self.assertTrue(self.tracker.release_for_retry(self.entity))
        self.assertTrue(self.tracker.try_acquire(self.entity))

    def test_release_for_retry_cannot_steal_a_running_claim(self):
        self.tracker.try_acquire(self.entity)
        self.session.commit()

        self.assertFalse(self.tracker.release_for_retry(self.entity))
        self.session.commit()
        self.assertEqual(self._row().status, STATUS_IN_PROGRESS)

    def test_reclaims_a_claim_whose_lease_expired(self):
        """A worker killed mid-run cannot release its own claim."""
        self.tracker.try_acquire(self.entity)
        self.session.commit()
        self._set_status(
            STATUS_IN_PROGRESS,
            triggered_at=datetime.now(timezone.utc)
            - timedelta(seconds=DEFAULT_LEASE_SECONDS + 60),
        )

        self.assertTrue(self.tracker.try_acquire(self.entity))

    def test_a_heartbeat_keeps_a_long_build_from_losing_its_claim(self):
        self.tracker.try_acquire(self.entity)
        self.session.commit()
        self._set_status(
            STATUS_IN_PROGRESS,
            triggered_at=datetime.now(timezone.utc)
            - timedelta(seconds=DEFAULT_LEASE_SECONDS + 60),
        )

        self.tracker.heartbeat(self.entity, metadata={"phase": "convert"})
        self.session.commit()

        self.assertFalse(
            self.tracker.try_acquire(self.entity),
            "a heartbeat must renew the lease, not merely record progress",
        )
        self.assertEqual(self._row().metadata_, {"phase": "convert"})

    def test_exactly_one_of_two_racing_workers_wins(self):
        """The case the whole mechanism exists for."""
        results = []
        barrier = threading.Barrier(2)

        def claim():
            session = self.Session()
            try:
                barrier.wait(timeout=10)
                won = self._tracker(session).try_acquire(self.entity)
                session.commit()
                results.append(won)
            except Exception as error:  # pragma: no cover - surfaced via the assert
                results.append(error)
            finally:
                session.close()

        threads = [threading.Thread(target=claim) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)

        self.assertEqual(
            results.count(True), 1, f"exactly one worker may win, got {results}"
        )
        self.assertEqual(results.count(False), 1, f"got {results}")
