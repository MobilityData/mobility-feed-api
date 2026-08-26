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

The task resolves its own session from FEEDS_DATABASE_URL rather than taking a `db_url`. That
works unpatched: `Database` is a process-wide singleton, and conftest.py's
`pytest_sessionstart` already locks it onto the test database (via `clean_testing_db`'s
`db_url=default_db_url`) before any test runs, for the whole session. Resetting the
singleton per test and repatching the env around each call — an earlier version of this file
did that — is not only unnecessary but actively dangerous: `Database.__init__` silently
no-ops once `initialized` is set, so a reset that isn't immediately followed by a correct
re-init leaves whichever *unrelated* test happens to touch the database next to lock the
whole rest of the process onto the real `FEEDS_DATABASE_URL` instead.

Each run is given this module's own feed list (REQUESTED), so it evaluates only the seeded
feeds. Assertions are still scoped to this module's PREFIX, and report counts are checked as
invariants and deltas rather than absolutes.
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import flask
from main import tasks_executor
from sqlalchemy import delete, select

from shared.common.seal_criteria import CriterionStatus, SealCriterionName
from tasks.seal_of_reliability.evaluators import EVALUATORS
from tasks.seal_of_reliability.update_seal_of_reliability import get_parameters

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Feed,
    FeedReliabilitySeal,
    Gtfsdataset,
    Gtfsfeed,
    SealCriterion,
)
from test_shared.test_utils.database_utils import default_db_url

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
PREFIX = "seal_e2e_"

OFFICIAL = f"{PREFIX}official"
NOT_OFFICIAL = f"{PREFIX}not_official"
UNKNOWN_OFFICIAL = f"{PREFIX}unknown_official"
DEPRECATED = f"{PREFIX}deprecated"
UNPUBLISHED = f"{PREFIX}unpublished"

# The task always runs against an explicit feed list. These are the eligible seeded feeds.
REQUESTED = [OFFICIAL, NOT_OFFICIAL, UNKNOWN_OFFICIAL]

# Every seeded feed gets a dataset covering the next 400 days, so Fresh passes and `official`
# stays the only criterion that separates the feeds. Stable needs nothing seeded: it reads
# `feed.created_at`, which `_seed` already backdates by 400 days.
COVERAGE_END = NOW + timedelta(days=400)


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
            seasonal=False,
        )
    )
    db_session.flush()

    # Fresh's input. Seeded rather than produced by the run so the criterion passes and
    # `official` stays the only variable.
    dataset_id = f"{feed_id}_dataset"
    db_session.add(
        Gtfsdataset(
            id=dataset_id,
            feed_id=feed_id,
            stable_id=dataset_id,
            downloaded_at=NOW - timedelta(days=1),
            service_date_range_start=NOW - timedelta(days=30),
            service_date_range_end=COVERAGE_END,
        )
    )
    db_session.flush()
    db_session.execute(
        Gtfsfeed.__table__.update()
        .where(Gtfsfeed.__table__.c.id == feed_id)
        .values(latest_dataset_id=dataset_id)
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

    def run_task(self, payload: dict) -> dict:
        """Invoke tasks_executor with a hand-built request, as Cloud Scheduler would.

        No env patching or singleton reset needed: the Database singleton is already locked
        onto the test database for the whole session (see the module docstring).
        """
        # The task requires a feed list; default to the seeded feeds unless a test set one,
        # so each test's payload can stay focused on the dimension it exercises.
        payload = {"stable_feed_ids": REQUESTED, **payload}
        request = MagicMock(spec=flask.Request)
        request.get_json.return_value = {
            "task": "update_seal_of_reliability",
            "payload": payload,
        }
        request.headers = {}

        with self.app.app_context():
            response = tasks_executor(request)

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    @staticmethod
    def ours(report: dict) -> list:
        """The report's feed entries for this module's feeds."""
        return [row for row in report["feeds"] if row["stable_id"].startswith(PREFIX)]

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def seal_state(db_session):
        """stable_id -> (has_seal, earned_at set?, lost_at set?) for the seeded feeds."""
        seal = FeedReliabilitySeal.__table__
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
        """(stable_id, criterion) -> the seal_criterion row, for the seeded feeds.

        Keyed by the criterion too, not just the feed: the registry holds several
        evaluators, so a feed has one row per criterion.
        """
        criterion = SealCriterion.__table__
        rows = db_session.execute(
            select(Feed.stable_id, criterion)
            .join(criterion, criterion.c.feed_id == Feed.id)
            .where(Feed.stable_id.like(f"{PREFIX}%"))
        ).all()
        return {(row.stable_id, row.criterion): row for row in rows}

    @classmethod
    def official_state(cls):
        """stable_id -> the `official` seal_criterion row, the one these tests drive."""
        return {
            stable_id: row
            for (stable_id, criterion), row in cls.criterion_state().items()
            if criterion == SealCriterionName.OFFICIAL.value
        }

    @staticmethod
    def official_criterion(feed_report: dict) -> dict:
        """The `official` entry of a report's per-feed criteria list."""
        return next(
            row
            for row in feed_report["criteria"]
            if row["criterion"] == SealCriterionName.OFFICIAL.value
        )

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
        self.assertGreaterEqual(first["criterion_rows_written"], 3 * len(EVALUATORS))
        self.assertEqual(first["seals_revoked"], 0, "nothing was held beforehand")
        self.assertEqual(
            {row["stable_id"] for row in self.ours(first)},
            {OFFICIAL, NOT_OFFICIAL, UNKNOWN_OFFICIAL},
            "every requested eligible feed is reported",
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
        criteria = self.official_state()
        self.assertNotIn(DEPRECATED, criteria, "ineligible feeds are never evaluated")
        self.assertNotIn(UNPUBLISHED, criteria)
        self.assertEqual(
            criteria[OFFICIAL].confirmed_status, CriterionStatus.PASS.value
        )
        self.assertIsNone(criteria[OFFICIAL].first_observed_failure_at)
        self.assertEqual(
            criteria[NOT_OFFICIAL].confirmed_status, CriterionStatus.FAIL.value
        )
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
        self.assertEqual(
            set(moved),
            {OFFICIAL, NOT_OFFICIAL, UNKNOWN_OFFICIAL},
            "every requested feed is reported; OFFICIAL and NOT_OFFICIAL are the ones "
            "whose seal actually changed",
        )

        self.assertTrue(moved[OFFICIAL]["had_seal"])
        self.assertFalse(moved[OFFICIAL]["has_seal"])
        self.assertEqual(
            self.official_criterion(moved[OFFICIAL])["confirmed_status"],
            CriterionStatus.FAIL.value,
        )
        self.assertEqual(
            self.official_criterion(moved[OFFICIAL])["previously_confirmed_status"],
            CriterionStatus.PASS.value,
        )

        self.assertFalse(moved[NOT_OFFICIAL]["had_seal"])
        self.assertTrue(moved[NOT_OFFICIAL]["has_seal"])
        self.assertEqual(
            self.official_criterion(moved[NOT_OFFICIAL])["confirmed_status"],
            CriterionStatus.PASS.value,
        )
        self.assertEqual(
            self.official_criterion(moved[NOT_OFFICIAL])["previously_confirmed_status"],
            CriterionStatus.FAIL.value,
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
        criteria = self.official_state()
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
        # The feeds are still reported (every requested feed is), but nothing moved:
        # no new verdicts and no seal transitions.
        self.assertEqual(report["first_evaluations"], 0)
        self.assertEqual(report["seals_granted"], 0)
        self.assertEqual(report["seals_revoked"], 0)
        self.assertEqual(report["seals_before_run"], report["seals_after_run"])

        after = self.criterion_state()
        for (stable_id, criterion), row in after.items():
            with self.subTest(stable_id=stable_id, criterion=criterion):
                self.assertEqual(
                    row.first_observed_failure_at,
                    before[(stable_id, criterion)].first_observed_failure_at,
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


class TestNowParsing(unittest.TestCase):
    """`now` must reach the state machine tz-aware, or comparisons against the tz-aware
    timestamptz columns raise TypeError for any criterion with a grace or probation period.
    """

    def test_naive_now_is_treated_as_utc(self):
        for value in ("2026-08-01", "2026-08-01T00:00:00"):
            with self.subTest(now=value):
                parsed = get_parameters({"now": value})[5]
                self.assertEqual(parsed, datetime(2026, 8, 1, tzinfo=timezone.utc))
                self.assertIsNotNone(parsed.tzinfo)

    def test_offset_now_is_normalized_to_utc(self):
        parsed = get_parameters({"now": "2026-08-01T00:00:00-05:00"})[5]
        self.assertEqual(parsed, datetime(2026, 8, 1, 5, 0, tzinfo=timezone.utc))

    def test_absent_now_is_none(self):
        self.assertIsNone(get_parameters({})[5])


if __name__ == "__main__":
    unittest.main()
