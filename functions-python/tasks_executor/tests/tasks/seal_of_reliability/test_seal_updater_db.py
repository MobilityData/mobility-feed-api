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
"""Integration tests for the seal context loader and orchestrator, against the test DB."""

import unittest
from datetime import datetime, timedelta, timezone

from tasks.seal_of_reliability.context import build_contexts, get_seal_feeds_query
from tasks.seal_of_reliability.criteria import SealCriterionName
from tasks.seal_of_reliability.seal_updater import update_seals
from sqlalchemy import delete, select

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Feed,
    Feedreliabilityseal,
    Gtfsfeed,
    Sealcriterion,
)
from test_shared.test_utils.database_utils import default_db_url

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
PREFIX = "seal_test_"

OFFICIAL = f"{PREFIX}official"
NOT_OFFICIAL = f"{PREFIX}not_official"
UNKNOWN_OFFICIAL = f"{PREFIX}unknown_official"
DEPRECATED = f"{PREFIX}deprecated"
UNPUBLISHED = f"{PREFIX}unpublished"
INACTIVE = f"{PREFIX}inactive"

# The eligible feeds this module seeds. Runs that assert exact counts must be scoped to
# these: an unnamed run also covers the fixtures seeded by conftest.pytest_sessionstart and
# any seal rows another test left behind, so the totals would not be deterministic.
OURS = [OFFICIAL, NOT_OFFICIAL, UNKNOWN_OFFICIAL, INACTIVE]


def _seed_feed(
    db_session,
    feed_id: str,
    official=True,
    status="active",
    operational_status="published",
):
    """Insert one GTFS feed."""
    db_session.add(
        Gtfsfeed(
            id=feed_id,
            stable_id=feed_id,
            data_type="gtfs",
            status=status,
            operational_status=operational_status,
            official=official,
            created_at=NOW - timedelta(days=400),
            producer_url=f"https://example.com/{feed_id}.zip",
        )
    )
    db_session.flush()


def _set_official(db_session, feed_id: str, official):
    db_session.execute(
        Feed.__table__.update()
        .where(Feed.__table__.c.id == feed_id)
        .values(official=official)
    )
    db_session.commit()


def _cleanup(db_session):
    """Remove every row this module created.

    Deleting from `feed` rather than `gtfsfeed` is deliberate: Gtfsfeed is a joined-table
    subclass of Feed, so deleting the subclass leaves the parent row behind and the next
    insert collides on feed_pkey. Deleting the parent cascades to gtfsfeed and to both seal
    tables, all of which are ON DELETE CASCADE.
    """
    db_session.execute(delete(Feed).where(Feed.stable_id.like(f"{PREFIX}%")))
    db_session.commit()


class SealDbTestCase(unittest.TestCase):
    """Seeds the feeds below before each test and removes them afterwards."""

    @with_db_session(db_url=default_db_url)
    def setUp(self, db_session):
        _cleanup(db_session)
        _seed_feed(db_session, OFFICIAL)
        _seed_feed(db_session, NOT_OFFICIAL, official=False)
        _seed_feed(db_session, UNKNOWN_OFFICIAL, official=None)
        _seed_feed(db_session, DEPRECATED, status="deprecated")
        _seed_feed(db_session, UNPUBLISHED, operational_status="unpublished")
        _seed_feed(db_session, INACTIVE, status="inactive")
        db_session.commit()

    @with_db_session(db_url=default_db_url)
    def tearDown(self, db_session):
        _cleanup(db_session)

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def criterion_rows(feed_id, db_session):
        table = Sealcriterion.__table__
        return {
            row.criterion: row
            for row in db_session.execute(
                select(table).where(table.c.feed_id == feed_id)
            ).all()
        }

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def seal_row(feed_id, db_session):
        table = Feedreliabilityseal.__table__
        return db_session.execute(
            select(table).where(table.c.feed_id == feed_id)
        ).first()

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def set_official(feed_id, official, db_session):
        _set_official(db_session, feed_id, official)


class TestEligibilityQuery(SealDbTestCase):
    @with_db_session(db_url=default_db_url)
    def test_excludes_deprecated_and_unpublished_but_keeps_inactive(self, db_session):
        found = {
            feed.stable_id
            for feed in get_seal_feeds_query(db_session).all()
            if feed.stable_id and feed.stable_id.startswith(PREFIX)
        }
        self.assertIn(OFFICIAL, found)
        self.assertIn(INACTIVE, found, "inactive feeds must be evaluated, not frozen")
        self.assertNotIn(DEPRECATED, found)
        self.assertNotIn(UNPUBLISHED, found)

    @with_db_session(db_url=default_db_url)
    def test_stable_feed_ids_narrows_the_same_query(self, db_session):
        feeds = get_seal_feeds_query(db_session, stable_feed_ids=[OFFICIAL]).all()
        self.assertEqual([feed.stable_id for feed in feeds], [OFFICIAL])


class TestBuildContexts(SealDbTestCase):
    @with_db_session(db_url=default_db_url)
    def test_loads_the_fields_the_evaluators_need(self, db_session):
        feeds = get_seal_feeds_query(db_session, stable_feed_ids=[OFFICIAL]).all()
        ctx = build_contexts(db_session, feeds, NOW)[feeds[0].id]
        self.assertEqual(ctx.stable_id, OFFICIAL)
        self.assertTrue(ctx.official)
        self.assertEqual(ctx.now, NOW)

    @with_db_session(db_url=default_db_url)
    def test_builds_one_context_per_feed(self, db_session):
        feeds = get_seal_feeds_query(
            db_session, stable_feed_ids=[OFFICIAL, NOT_OFFICIAL]
        ).all()
        contexts = build_contexts(db_session, feeds, NOW)
        self.assertEqual(len(contexts), 2)
        self.assertEqual({ctx.official for ctx in contexts.values()}, {True, False})


class TestUpdateSeals(SealDbTestCase):
    def test_dry_run_writes_nothing(self):
        report = update_seals(dry_run=True, stable_feed_ids=[OFFICIAL], now=NOW)
        self.assertTrue(report["dry_run"])
        self.assertEqual(report["total_feeds"], 1)
        self.assertEqual(report["criterion_rows_written"], 0)
        self.assertEqual(self.criterion_rows(OFFICIAL), {})
        self.assertIsNone(self.seal_row(OFFICIAL))

    def test_dry_run_counts_are_prospective(self):
        """Nothing is held yet, so `after` describes what a real run would store."""
        report = update_seals(dry_run=True, stable_feed_ids=OURS, now=NOW)
        self.assertEqual(report["seals_before_run"], 0)
        self.assertEqual(report["seals_after_run"], 2, "the two official feeds")
        self.assertEqual(report["seals_granted"], 2)
        self.assertEqual(report["seals_revoked"], 0)
        self.assertIsNone(self.seal_row(OFFICIAL), "still a dry run")

    def test_seal_counts_balance(self):
        """before + granted - revoked == after, across a grant then a revocation."""
        first = update_seals(dry_run=False, stable_feed_ids=OURS, now=NOW)
        self.assertEqual(first["seals_before_run"], 0)
        self.assertEqual(first["seals_after_run"], 2)

        self.set_official(OFFICIAL, False)
        second = update_seals(dry_run=False, stable_feed_ids=OURS, now=NOW)
        self.assertEqual(second["seals_before_run"], 2, "two were held going in")
        self.assertEqual(second["seals_revoked"], 1)
        self.assertEqual(second["seals_granted"], 0)
        self.assertEqual(second["seals_after_run"], 1)
        self.assertEqual(
            second["seals_before_run"]
            + second["seals_granted"]
            - second["seals_revoked"],
            second["seals_after_run"],
        )

    def test_dry_run_reports_rows_for_a_named_feed(self):
        report = update_seals(dry_run=True, stable_feed_ids=[NOT_OFFICIAL], now=NOW)
        self.assertEqual(
            [row["criterion"] for row in report["evaluations"]],
            [SealCriterionName.OFFICIAL.value],
        )
        self.assertFalse(report["evaluations"][0]["observed_pass"])
        self.assertTrue(report["evaluations"][0]["reason"])
        self.assertIsNone(report["evaluations"][0]["previously_confirmed_pass"])

    def test_named_feed_reports_a_row_even_when_nothing_moved(self):
        """An explicit feed list is the debugging path: report all of its criteria."""
        update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=NOW)
        report = update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=NOW)
        self.assertEqual(len(report["evaluations"]), 1)
        self.assertTrue(report["evaluations"][0]["confirmed_pass"])
        self.assertTrue(report["evaluations"][0]["previously_confirmed_pass"])

    def test_unnamed_run_reports_only_criteria_that_moved(self):
        """A passing feed evaluated twice contributes no entry the second time."""
        first = update_seals(dry_run=False, now=NOW)
        self.assertTrue(
            any(row["stable_id"] == NOT_OFFICIAL for row in first["evaluations"]),
            "a first evaluation that lands on a failure is reported",
        )
        self.assertFalse(
            any(row["stable_id"] == OFFICIAL for row in first["evaluations"]),
            "a first evaluation that passes is covered by first_evaluations",
        )
        self.assertGreaterEqual(first["first_evaluations"], 2)

        steady = update_seals(dry_run=False, now=NOW)
        self.assertEqual(
            steady["evaluations"], [], "nothing moved, so nothing to report"
        )
        self.assertEqual(steady["first_evaluations"], 0)

    def test_a_criterion_that_flips_is_reported_with_its_previous_value(self):
        update_seals(dry_run=False, now=NOW)
        self.set_official(OFFICIAL, False)
        report = update_seals(dry_run=False, now=NOW)

        moved = [row for row in report["evaluations"] if row["stable_id"] == OFFICIAL]
        self.assertEqual(len(moved), 1)
        self.assertFalse(moved[0]["confirmed_pass"])
        self.assertTrue(moved[0]["previously_confirmed_pass"])

    def test_official_feed_earns_the_seal(self):
        update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=NOW)
        row = self.criterion_rows(OFFICIAL)[SealCriterionName.OFFICIAL.value]
        self.assertTrue(row.observed_pass)
        self.assertTrue(row.confirmed_pass)
        self.assertEqual(row.evaluated_at, NOW)
        self.assertIsNone(row.first_observed_failure_at)
        self.assertIsNone(row.probation_start, "a clean first run opens no probation")

        seal = self.seal_row(OFFICIAL)
        self.assertTrue(seal.has_seal)
        self.assertEqual(seal.seal_earned_at, NOW)
        self.assertIsNone(seal.seal_lost_at)

    def test_failing_official_denies_the_seal_immediately(self):
        """Official has no grace period, so one failure is confirmed at once."""
        update_seals(dry_run=False, stable_feed_ids=[NOT_OFFICIAL], now=NOW)
        row = self.criterion_rows(NOT_OFFICIAL)[SealCriterionName.OFFICIAL.value]
        self.assertFalse(row.observed_pass)
        self.assertFalse(row.confirmed_pass)
        self.assertEqual(row.first_observed_failure_at, NOW)
        self.assertEqual(row.last_confirmed_failure_at, NOW)
        self.assertFalse(self.seal_row(NOT_OFFICIAL).has_seal)

    def test_a_feed_that_never_qualifies_still_gets_a_seal_row(self):
        """`created_at` on that row is what a tracking-age criterion measures against."""
        update_seals(dry_run=False, stable_feed_ids=[NOT_OFFICIAL], now=NOW)
        seal = self.seal_row(NOT_OFFICIAL)
        self.assertIsNotNone(seal, "a row is written whether or not the feed qualifies")
        self.assertFalse(seal.has_seal)
        self.assertIsNone(seal.seal_lost_at, "nothing was held, so nothing was lost")

    def test_unknown_official_flag_denies_the_seal(self):
        update_seals(dry_run=False, stable_feed_ids=[UNKNOWN_OFFICIAL], now=NOW)
        self.assertFalse(self.seal_row(UNKNOWN_OFFICIAL).has_seal)

    def test_rerun_is_idempotent(self):
        update_seals(dry_run=False, stable_feed_ids=[NOT_OFFICIAL], now=NOW)
        first = self.criterion_rows(NOT_OFFICIAL)[SealCriterionName.OFFICIAL.value]
        update_seals(dry_run=False, stable_feed_ids=[NOT_OFFICIAL], now=NOW)
        second = self.criterion_rows(NOT_OFFICIAL)[SealCriterionName.OFFICIAL.value]
        self.assertEqual(
            first.first_observed_failure_at, second.first_observed_failure_at
        )
        self.assertEqual(
            first.last_confirmed_failure_at, second.last_confirmed_failure_at
        )

    def test_losing_official_status_revokes_the_seal(self):
        update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=NOW)
        self.assertTrue(self.seal_row(OFFICIAL).has_seal)

        self.set_official(OFFICIAL, False)
        later = NOW + timedelta(days=1)
        update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=later)
        seal = self.seal_row(OFFICIAL)
        self.assertFalse(seal.has_seal)
        self.assertEqual(seal.seal_lost_at, later)
        self.assertEqual(seal.seal_earned_at, NOW, "the earlier grant is preserved")

    def test_regaining_official_status_clears_the_criterion(self):
        """Official has no probation, so recovery restores the seal the same day."""
        update_seals(dry_run=False, stable_feed_ids=[NOT_OFFICIAL], now=NOW)
        self.assertFalse(self.seal_row(NOT_OFFICIAL).has_seal)

        self.set_official(NOT_OFFICIAL, True)
        later = NOW + timedelta(days=1)
        update_seals(dry_run=False, stable_feed_ids=[NOT_OFFICIAL], now=later)
        row = self.criterion_rows(NOT_OFFICIAL)[SealCriterionName.OFFICIAL.value]
        self.assertTrue(row.confirmed_pass)
        self.assertIsNone(row.first_observed_failure_at, "the streak is cleared")
        self.assertIsNone(row.probation_start, "Official serves no probation")
        self.assertEqual(
            row.last_confirmed_failure_at, NOW, "the failure is still on record"
        )
        seal = self.seal_row(NOT_OFFICIAL)
        self.assertTrue(seal.has_seal)
        self.assertEqual(seal.seal_earned_at, later)

    def test_partial_criteria_run_skips_the_roll_up(self):
        """Named explicitly, `official` is still the whole registry, so not partial."""
        report = update_seals(
            dry_run=False,
            stable_feed_ids=[OFFICIAL],
            criteria=[SealCriterionName.OFFICIAL.value],
            now=NOW,
        )
        self.assertFalse(report["partial_run"])
        self.assertTrue(self.seal_row(OFFICIAL).has_seal)

    def test_unknown_criterion_raises(self):
        with self.assertRaises(ValueError):
            update_seals(criteria=["not_a_criterion"], now=NOW)

    def test_criterion_without_an_evaluator_raises(self):
        """`stable` is a valid DB enum value but has no evaluator yet (#1784)."""
        with self.assertRaises(ValueError):
            update_seals(criteria=[SealCriterionName.STABLE.value], now=NOW)

    def test_unknown_stable_feed_id_raises(self):
        with self.assertRaises(ValueError):
            update_seals(stable_feed_ids=[f"{PREFIX}does_not_exist"], now=NOW)

    def test_limit_caps_the_feeds_evaluated(self):
        report = update_seals(dry_run=True, limit=2, now=NOW)
        self.assertLessEqual(report["total_feeds"], 2)


if __name__ == "__main__":
    unittest.main()
