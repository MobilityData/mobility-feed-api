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

"""`_aggregate_batches` against real TaskExecutionLog rows.

Every test in test_seal_orchestrator_fanout.py patches this function out — it needs a real
session, and those tests drive the monitor with a MagicMock. Mocking it hides both whether it
sums correctly and whether it sums the right keys, so it is covered here instead.

It is what turns each batch's stored report into the run-level one, which after a manual
backfill is the only thing an operator sees.
"""

import unittest

from sqlalchemy import delete

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import TaskExecutionLog
from tasks.seal_of_reliability.backfill.seal_backfill_orchestrator import (
    SEAL_BACKFILL_TASK_NAME,
)
from tasks.seal_of_reliability.orchestrator.seal_orchestrator import (
    SEAL_ORCHESTRATOR_TASK_NAME,
)
from tasks.seal_of_reliability.orchestrator.seal_orchestrator_monitor import (
    MAX_REPORTED_IDS,
    _aggregate_batches,
    _parse_iso,
)
from test_shared.test_utils.database_utils import default_db_url

RUN = "seal-agg-test-run"
OTHER_RUN = "seal-agg-test-other"


def _batch(task_name, run_id, entity_id, metadata):
    return TaskExecutionLog(
        task_name=task_name,
        run_id=run_id,
        entity_id=entity_id,
        status="completed",
        metadata_=metadata,
    )


class AggregationTestCase(unittest.TestCase):
    @with_db_session(db_url=default_db_url)
    def setUp(self, db_session):
        self._cleanup(db_session)

    @with_db_session(db_url=default_db_url)
    def tearDown(self, db_session):
        self._cleanup(db_session)

    @staticmethod
    def _cleanup(db_session):
        db_session.execute(
            delete(TaskExecutionLog).where(
                TaskExecutionLog.run_id.in_([RUN, OTHER_RUN])
            )
        )
        db_session.commit()

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def _seed(entries, db_session=None):
        for entry in entries:
            db_session.add(entry)
        db_session.commit()

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def _aggregate(task_name=SEAL_ORCHESTRATOR_TASK_NAME, run_id=RUN, db_session=None):
        return _aggregate_batches(db_session, run_id, task_name)


class TestAggregateBatches(AggregationTestCase):
    def test_sums_across_batches(self):
        self._seed(
            [
                _batch(
                    SEAL_ORCHESTRATOR_TASK_NAME,
                    RUN,
                    "batch-0000",
                    {
                        "total_feeds": 10,
                        "criterion_rows_written": 20,
                        "seals_granted": 2,
                        "seals_revoked": 1,
                        "granted_stable_ids": ["a", "b"],
                        "revoked_stable_ids": ["c"],
                    },
                ),
                _batch(
                    SEAL_ORCHESTRATOR_TASK_NAME,
                    RUN,
                    "batch-0001",
                    {
                        "total_feeds": 5,
                        "criterion_rows_written": 7,
                        "seals_granted": 1,
                        "seals_revoked": 0,
                        "granted_stable_ids": ["d"],
                    },
                ),
            ]
        )

        result = self._aggregate()
        self.assertEqual(result["total_feeds_evaluated"], 15)
        self.assertEqual(result["criterion_rows_written"], 27)
        self.assertEqual(result["seals_granted"], 3)
        self.assertEqual(result["seals_revoked"], 1)
        self.assertEqual(sorted(result["granted_stable_ids"]), ["a", "b", "d"])
        self.assertEqual(result["revoked_stable_ids"], ["c"])
        self.assertEqual(result["ids_omitted"], 0)

    def test_a_backfill_snapshot_count_survives_to_the_run_report(self):
        """The key a backfill batch reports and a nightly one does not.

        It was being dropped at aggregation, so a backfill's snapshot count never reached
        the operator who triggered the run.
        """
        self._seed(
            [
                _batch(
                    SEAL_BACKFILL_TASK_NAME,
                    RUN,
                    "batch-0000",
                    {"total_feeds": 3, "snapshot_rows_written": 18},
                ),
                _batch(
                    SEAL_BACKFILL_TASK_NAME,
                    RUN,
                    "batch-0001",
                    {"total_feeds": 2, "snapshot_rows_written": 12},
                ),
            ]
        )

        result = self._aggregate(task_name=SEAL_BACKFILL_TASK_NAME)
        self.assertEqual(result["snapshot_rows_written"], 30)
        self.assertEqual(result["total_feeds_evaluated"], 5)

    def test_a_nightly_batch_contributes_zero_for_keys_it_never_reports(self):
        """One aggregation serves both fan-outs, so a missing key must not raise."""
        self._seed(
            [
                _batch(
                    SEAL_ORCHESTRATOR_TASK_NAME,
                    RUN,
                    "batch-0000",
                    {"total_feeds": 4, "criterion_rows_written": 4},
                )
            ]
        )

        result = self._aggregate()
        self.assertEqual(result["snapshot_rows_written"], 0)

    def test_it_only_sums_its_own_run(self):
        self._seed(
            [
                _batch(
                    SEAL_ORCHESTRATOR_TASK_NAME, RUN, "batch-0000", {"total_feeds": 4}
                ),
                _batch(
                    SEAL_ORCHESTRATOR_TASK_NAME,
                    OTHER_RUN,
                    "batch-0000",
                    {"total_feeds": 99},
                ),
            ]
        )
        self.assertEqual(self._aggregate()["total_feeds_evaluated"], 4)

    def test_it_only_sums_its_own_task_name(self):
        """The two fan-outs share this function; a backfill run must not absorb a nightly one."""
        self._seed(
            [
                _batch(
                    SEAL_ORCHESTRATOR_TASK_NAME, RUN, "batch-0000", {"total_feeds": 4}
                ),
                _batch(SEAL_BACKFILL_TASK_NAME, RUN, "batch-0001", {"total_feeds": 50}),
            ]
        )
        self.assertEqual(self._aggregate()["total_feeds_evaluated"], 4)
        self.assertEqual(
            self._aggregate(task_name=SEAL_BACKFILL_TASK_NAME)["total_feeds_evaluated"],
            50,
        )

    def test_a_batch_with_no_metadata_is_skipped(self):
        self._seed(
            [
                _batch(
                    SEAL_ORCHESTRATOR_TASK_NAME, RUN, "batch-0000", {"total_feeds": 4}
                ),
                _batch(SEAL_ORCHESTRATOR_TASK_NAME, RUN, "batch-0001", {}),
            ]
        )
        self.assertEqual(self._aggregate()["total_feeds_evaluated"], 4)

    def test_a_run_with_no_batches_aggregates_to_zero(self):
        result = self._aggregate()
        self.assertEqual(result["total_feeds_evaluated"], 0)
        self.assertEqual(result["granted_stable_ids"], [])
        self.assertEqual(result["ids_omitted"], 0)

    def test_the_id_lists_are_capped_and_the_overflow_counted(self):
        """The seal tables hold every transition; this only bounds the response size."""
        granted = [f"mdb-{n}" for n in range(MAX_REPORTED_IDS + 5)]
        self._seed(
            [
                _batch(
                    SEAL_ORCHESTRATOR_TASK_NAME,
                    RUN,
                    "batch-0000",
                    {"granted_stable_ids": granted},
                )
            ]
        )

        result = self._aggregate()
        self.assertEqual(len(result["granted_stable_ids"]), MAX_REPORTED_IDS)
        self.assertEqual(result["ids_omitted"], 5)


class TestParseIso(unittest.TestCase):
    """The deadline check silently loses its guard if this returns None, so pin the branches."""

    def test_absent_is_none(self):
        self.assertIsNone(_parse_iso(None))
        self.assertIsNone(_parse_iso(""))

    def test_unparseable_is_none_rather_than_raising(self):
        self.assertIsNone(_parse_iso("not a timestamp"))

    def test_naive_is_read_as_utc(self):
        parsed = _parse_iso("2026-06-01T12:00:00")
        self.assertEqual(parsed.tzinfo, __import__("datetime").timezone.utc)

    def test_offset_is_preserved(self):
        self.assertIsNotNone(_parse_iso("2026-06-01T12:00:00+02:00").tzinfo)


if __name__ == "__main__":
    unittest.main()
