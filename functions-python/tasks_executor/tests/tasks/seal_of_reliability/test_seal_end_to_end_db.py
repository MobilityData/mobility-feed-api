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
"""End-to-end test of the Seal of Reliability task through the tasks_executor entry point.

Unlike test_seal_updater_db.py, which calls `update_seals` directly, this drives the
function the way Cloud Scheduler does: a JSON payload posted to `tasks_executor`, dispatched
by name through the registry in main.py. That covers the layers the direct tests skip —
payload parsing, defaults, and the task being reachable by its registered name.

The task resolves its own session from FEEDS_DATABASE_URL rather than taking a `db_url`, so
the environment is pointed at the test database for the duration of each test and the
Database singleton is reset around it.

These runs are unnamed, so they evaluate every eligible feed in the test database — which
includes the fixtures seeded by conftest.pytest_sessionstart. Assertions are therefore
scoped to this module's own PREFIX, and the report counts are checked as invariants and
deltas rather than absolutes.
"""

import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import flask
from main import tasks_executor
from sqlalchemy import delete, select

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Feed,
    Feedreliabilityseal,
    Gtfsfeed,
    Sealcriterion,
)
from test_shared.test_utils.database_utils import default_db_url, reset_database_class

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
PREFIX = "seal_e2e_"

OFFICIAL = f"{PREFIX}official"
NOT_OFFICIAL = f"{PREFIX}not_official"
UNKNOWN_OFFICIAL = f"{PREFIX}unknown_official"
DEPRECATED = f"{PREFIX}deprecated"
UNPUBLISHED = f"{PREFIX}unpublished"


def _seed(db_session, feed_id, official=True, status="active", operational="published"):
    db_session.add(
        Gtfsfeed(
            id=feed_id,
            stable_id=feed_id,
            data_type="gtfs",
            status=status,
            operational_status=operational,
            official=official,
            created_at=NOW - timedelta(days=400),
            producer_url=f"https://example.com/{feed_id}.zip",
        )
    )
    db_session.flush()


def _cleanup(db_session):
    """Deleting the parent Feed cascades to gtfsfeed and both seal tables."""
    db_session.execute(delete(Feed).where(Feed.stable_id.like(f"{PREFIX}%")))
    db_session.commit()


class TestSealTaskEndToEnd(unittest.TestCase):
    """Seed, run through the entry point, inspect, modify, run again, inspect."""

    @with_db_session(db_url=default_db_url)
    def setUp(self, db_session):
        _cleanup(db_session)
        _seed(db_session, OFFICIAL)
        _seed(db_session, NOT_OFFICIAL, official=False)
        _seed(db_session, UNKNOWN_OFFICIAL, official=None)
        _seed(db_session, DEPRECATED, status="deprecated")
        _seed(db_session, UNPUBLISHED, operational="unpublished")
        db_session.commit()
        self.app = flask.Flask(__name__)

    @with_db_session(db_url=default_db_url)
    def tearDown(self, db_session):
        _cleanup(db_session)
        reset_database_class()

    def run_task(self, payload: dict) -> dict:
        """Invoke tasks_executor with a hand-built request, as Cloud Scheduler would.

        FEEDS_DATABASE_URL is pointed at the test database because the handler resolves its
        own session; without this the task would run against the local development DB.
        """
        request = MagicMock(spec=flask.Request)
        request.get_json.return_value = {
            "task": "update_seal_of_reliability",
            "payload": payload,
        }
        request.headers = {}

        reset_database_class()
        with patch.dict(os.environ, {"FEEDS_DATABASE_URL": default_db_url}):
            with self.app.app_context():
                response = tasks_executor(request)
        reset_database_class()

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    @staticmethod
    def ours(report: dict) -> list:
        """The report's feed entries for this module's feeds only.

        Unnamed runs also cover the conftest fixtures, so filtering keeps these assertions
        independent of what else lives in the test database.
        """
        return [row for row in report["feeds"] if row["stable_id"].startswith(PREFIX)]

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def seal_state(db_session):
        """stable_id -> (has_seal, earned_at set?, lost_at set?) for the seeded feeds."""
        seal = Feedreliabilityseal.__table__
        rows = db_session.execute(
            select(
                Feed.stable_id,
                seal.c.has_seal,
                seal.c.seal_earned_at,
                seal.c.seal_lost_at,
            )
            .join(seal, seal.c.feed_id == Feed.id)
            .where(Feed.stable_id.like(f"{PREFIX}%"))
        ).all()
        return {
            row.stable_id: (
                row.has_seal,
                row.seal_earned_at is not None,
                row.seal_lost_at is not None,
            )
            for row in rows
        }

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def criterion_state(db_session):
        """stable_id -> the sealcriterion row, for the seeded feeds."""
        criterion = Sealcriterion.__table__
        rows = db_session.execute(
            select(Feed.stable_id, criterion)
            .join(criterion, criterion.c.feed_id == Feed.id)
            .where(Feed.stable_id.like(f"{PREFIX}%"))
        ).all()
        return {row.stable_id: row for row in rows}

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def set_official(stable_id, official, db_session):
        db_session.execute(
            Feed.__table__.update()
            .where(Feed.__table__.c.stable_id == stable_id)
            .values(official=official)
        )
        db_session.commit()

    def test_dry_run_through_the_entry_point_writes_nothing(self):
        report = self.run_task({"dry_run": True, "now": NOW.isoformat()})
        self.assertTrue(report["dry_run"])
        self.assertGreaterEqual(report["total_feeds"], 3)
        self.assertEqual(report["criterion_rows_written"], 0)
        self.assertEqual(self.seal_state(), {}, "nothing written for our feeds")
        self.assertEqual(self.criterion_state(), {})

    def test_dry_run_is_the_default_when_the_payload_omits_it(self):
        """The safety default has to survive the payload layer, not just the function."""
        report = self.run_task({"now": NOW.isoformat()})
        self.assertTrue(report["dry_run"])
        self.assertEqual(self.seal_state(), {})

    def test_two_runs_with_a_change_in_between(self):
        # --- first run: writes the initial state
        first = self.run_task({"dry_run": False, "now": NOW.isoformat()})
        self.assertFalse(first["dry_run"])
        self.assertGreaterEqual(first["criterion_rows_written"], 3)
        self.assertEqual(first["seals_revoked"], 0, "nothing was held beforehand")
        self.assertEqual(
            {row["stable_id"] for row in self.ours(first)},
            {OFFICIAL, NOT_OFFICIAL, UNKNOWN_OFFICIAL},
            "the two failures moved a criterion; the official feed gained the seal",
        )

        # --- inspect the database
        self.assertEqual(
            self.seal_state(),
            {
                OFFICIAL: (True, True, False),
                NOT_OFFICIAL: (False, False, False),
                UNKNOWN_OFFICIAL: (False, False, False),
            },
            "only the official feed earned it; the others were never granted or lost",
        )
        criteria = self.criterion_state()
        self.assertNotIn(DEPRECATED, criteria)
        self.assertNotIn(UNPUBLISHED, criteria)
        self.assertTrue(criteria[OFFICIAL].confirmed_pass)
        self.assertIsNone(criteria[OFFICIAL].first_observed_failure_at)
        self.assertFalse(criteria[NOT_OFFICIAL].confirmed_pass)
        self.assertEqual(criteria[NOT_OFFICIAL].first_observed_failure_at, NOW)

        # --- modify the database: revoke one, recover another
        self.set_official(OFFICIAL, False)
        self.set_official(NOT_OFFICIAL, True)

        # --- second run
        later = NOW + timedelta(days=1)
        second = self.run_task({"dry_run": False, "now": later.isoformat()})
        self.assertEqual(second["first_evaluations"], 0, "every feed already had a row")
        self.assertEqual(second["seals_granted"], 1)
        self.assertEqual(second["seals_revoked"], 1)
        self.assertIn(OFFICIAL, second["revoked_stable_ids"])
        self.assertEqual(
            second["seals_before_run"]
            + second["seals_granted"]
            - second["seals_revoked"],
            second["seals_after_run"],
            "before + granted - revoked == after",
        )

        moved = {row["stable_id"]: row for row in self.ours(second)}
        self.assertEqual(set(moved), {OFFICIAL, NOT_OFFICIAL}, "only these two moved")

        self.assertTrue(moved[OFFICIAL]["had_seal"])
        self.assertFalse(moved[OFFICIAL]["has_seal"])
        self.assertFalse(moved[OFFICIAL]["criteria"][0]["confirmed_pass"])
        self.assertTrue(moved[OFFICIAL]["criteria"][0]["previously_confirmed_pass"])

        self.assertFalse(moved[NOT_OFFICIAL]["had_seal"])
        self.assertTrue(moved[NOT_OFFICIAL]["has_seal"])
        self.assertTrue(moved[NOT_OFFICIAL]["criteria"][0]["confirmed_pass"])
        self.assertFalse(
            moved[NOT_OFFICIAL]["criteria"][0]["previously_confirmed_pass"]
        )

        # --- inspect again: both transitions are recorded, history is preserved
        self.assertEqual(
            self.seal_state(),
            {
                OFFICIAL: (False, True, True),
                NOT_OFFICIAL: (True, True, False),
                UNKNOWN_OFFICIAL: (False, False, False),
            },
            "the revoked feed keeps its earned_at; the recovered one gains earned_at",
        )
        criteria = self.criterion_state()
        self.assertEqual(criteria[OFFICIAL].first_observed_failure_at, later)
        self.assertIsNone(
            criteria[NOT_OFFICIAL].first_observed_failure_at, "the streak ended"
        )
        self.assertEqual(
            criteria[NOT_OFFICIAL].last_observed_failure_at,
            NOW,
            "history is never cleared, so the old failure time survives recovery",
        )

    def test_third_run_with_no_change_is_a_no_op(self):
        self.run_task({"dry_run": False, "now": NOW.isoformat()})
        before = self.criterion_state()

        later = NOW + timedelta(days=2)
        report = self.run_task({"dry_run": False, "now": later.isoformat()})
        self.assertEqual(self.ours(report), [], "none of our feeds moved")
        self.assertEqual(report["first_evaluations"], 0)
        self.assertEqual(report["seals_before_run"], report["seals_after_run"])

        after = self.criterion_state()
        for stable_id, row in after.items():
            with self.subTest(stable_id=stable_id):
                self.assertEqual(
                    row.first_observed_failure_at,
                    before[stable_id].first_observed_failure_at,
                    "a re-evaluation must not restart a failure streak",
                )
                self.assertEqual(row.evaluated_at, later, "but it is re-evaluated")

    def test_unknown_task_name_is_rejected(self):
        request = MagicMock(spec=flask.Request)
        request.get_json.return_value = {"task": "no_such_seal_task", "payload": {}}
        request.headers = {}
        with self.app.app_context():
            response = tasks_executor(request)
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
