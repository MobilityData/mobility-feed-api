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
from unittest.mock import patch

from tasks.seal_of_reliability.context import build_contexts, get_seal_feeds_query
from tasks.seal_of_reliability.criteria import PROBATION_PERIOD, SealCriterionName
from tasks.seal_of_reliability.evaluators import CriterionEvaluator, OfficialEvaluator
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


class _StandInEvaluator(CriterionEvaluator):
    """A criterion with a grace period and probation, for the probation tests below.

    Official is the only real evaluator and has neither, so without a stand-in nothing
    exercises `probation_start` against a database: it would never be persisted, reloaded,
    or seen by the `has_seal` roll-up with a value other than NULL.

    It reads `official` so a test can drive it with the existing `set_official` helper, but
    unlike Official it debounces failures and serves probation afterwards. It borrows the
    `available` enum value, which has no evaluator of its own yet (#1784).
    """

    name = SealCriterionName.AVAILABLE
    grace_period = timedelta(days=14)

    def _evaluate(self, ctx):
        return ctx.official is True, f"stand-in, feed.official is {ctx.official!r}"


# Patched over the registry so the roll-up sees a criterion that can be on probation.
WITH_PROBATION = [OfficialEvaluator(), _StandInEvaluator()]


DARK_FROM = NOW + timedelta(days=2)


class _GoesDarkEvaluator(CriterionEvaluator):
    """A criterion that loses its upstream input partway through, standing in for #1784.

    It returns no verdict from `DARK_FROM` onwards, keyed on the clock rather than on
    `official` so that a test can drive it and Official in opposite directions at the same
    moment. No grace period, so its verdicts land immediately and the tests are about what
    happens once it goes quiet.
    """

    name = SealCriterionName.COMPLIANT
    grace_period = None

    def _evaluate(self, ctx):
        if ctx.now >= DARK_FROM:
            return None, "stand-in has no input this run"
        return ctx.official is True, f"stand-in, feed.official is {ctx.official!r}"


# Official is kept in the registry on purpose: it is passing by the time the stand-in goes
# dark, so if the stand-in's frozen row were dropped from the roll-up the seal would come
# straight back. Without it, the empty-in_service guard would mask that.
GOES_DARK = [OfficialEvaluator(), _GoesDarkEvaluator()]


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

    def test_both_seal_transitions_are_reported_by_feed(self):
        """Counts say how many moved; these say which, for each direction."""
        first = update_seals(dry_run=False, stable_feed_ids=OURS, now=NOW)
        self.assertEqual(
            sorted(first["granted_stable_ids"]), sorted([OFFICIAL, INACTIVE])
        )
        self.assertEqual(first["revoked_stable_ids"], [])

        self.set_official(OFFICIAL, False)
        later = NOW + timedelta(days=1)
        second = update_seals(dry_run=False, stable_feed_ids=OURS, now=later)
        self.assertEqual(second["granted_stable_ids"], [])
        self.assertEqual(second["revoked_stable_ids"], [OFFICIAL])

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

    def test_a_reported_feed_carries_its_seal_state_and_its_criteria(self):
        report = update_seals(dry_run=True, stable_feed_ids=[NOT_OFFICIAL], now=NOW)
        self.assertEqual(len(report["feeds"]), 1)

        feed = report["feeds"][0]
        self.assertEqual(feed["stable_id"], NOT_OFFICIAL)
        self.assertFalse(feed["had_seal"])
        self.assertFalse(feed["has_seal"])
        self.assertEqual(
            [row["criterion"] for row in feed["criteria"]],
            [SealCriterionName.OFFICIAL.value],
        )
        self.assertFalse(feed["criteria"][0]["observed_pass"])
        self.assertTrue(feed["criteria"][0]["reason"])
        self.assertIsNone(feed["criteria"][0]["previously_confirmed_pass"])

    def test_named_feed_is_reported_even_when_nothing_moved(self):
        """An explicit feed list is the debugging path: report it either way."""
        update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=NOW)
        report = update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=NOW)

        feed = report["feeds"][0]
        self.assertTrue(feed["had_seal"])
        self.assertTrue(feed["has_seal"])
        self.assertTrue(feed["criteria"][0]["confirmed_pass"])
        self.assertTrue(feed["criteria"][0]["previously_confirmed_pass"])

    def test_unnamed_run_reports_only_feeds_that_moved(self):
        first = update_seals(dry_run=False, now=NOW)
        reported = {row["stable_id"] for row in first["feeds"]}
        self.assertIn(NOT_OFFICIAL, reported, "its criterion landed on a failure")
        self.assertIn(OFFICIAL, reported, "it was granted the seal")
        self.assertGreaterEqual(first["first_evaluations"], 2)

        steady = update_seals(dry_run=False, now=NOW)
        self.assertEqual(steady["feeds"], [], "nothing moved, so nothing to report")
        self.assertEqual(steady["first_evaluations"], 0)

    def test_a_feed_that_flips_is_reported_with_the_previous_verdict(self):
        update_seals(dry_run=False, now=NOW)
        self.set_official(OFFICIAL, False)
        report = update_seals(dry_run=False, now=NOW)

        moved = [row for row in report["feeds"] if row["stable_id"] == OFFICIAL]
        self.assertEqual(len(moved), 1)
        self.assertTrue(moved[0]["had_seal"])
        self.assertFalse(moved[0]["has_seal"])
        self.assertFalse(moved[0]["criteria"][0]["confirmed_pass"])
        self.assertTrue(moved[0]["criteria"][0]["previously_confirmed_pass"])

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

    def test_a_run_with_no_usable_feed_raises(self):
        """Nothing was evaluated, so a report saying so would be too quiet."""
        with self.assertRaises(ValueError) as caught:
            update_seals(stable_feed_ids=[f"{PREFIX}does_not_exist"], now=NOW)
        self.assertIn("not found", str(caught.exception))

    def test_an_ineligible_feed_says_so_rather_than_not_found(self):
        """A filtered-out feed is in the database, so "not found" would send you hunting."""
        with self.assertRaises(ValueError) as caught:
            update_seals(stable_feed_ids=[DEPRECATED], now=NOW)
        message = str(caught.exception)
        self.assertIn("not eligible", message)
        self.assertIn(DEPRECATED, message)
        self.assertNotIn("not found", message)

    def test_unusable_feeds_are_dropped_rather_than_costing_the_run(self):
        """One stale id must not cost a run over the feeds that are fine."""
        with self.assertLogs(level="WARNING") as logs:
            report = update_seals(
                dry_run=False,
                stable_feed_ids=[OFFICIAL, DEPRECATED, f"{PREFIX}does_not_exist"],
                now=NOW,
            )
        self.assertEqual(report["total_feeds"], 1, "the eligible feed still ran")
        self.assertTrue(self.seal_row(OFFICIAL).has_seal)

        warning = "\n".join(logs.output)
        self.assertIn(DEPRECATED, warning)
        self.assertIn(f"{PREFIX}does_not_exist", warning)

    def test_limit_caps_the_feeds_evaluated(self):
        report = update_seals(dry_run=True, limit=2, now=NOW)
        self.assertLessEqual(report["total_feeds"], 2)

    def test_the_feed_list_is_capped_without_capping_the_run(self):
        """The list is a sample; the two seal tables are the record."""
        report = update_seals(
            dry_run=False, stable_feed_ids=OURS, now=NOW, max_reported_feeds=2
        )
        self.assertEqual(len(report["feeds"]), 2)
        self.assertEqual(report["feeds_omitted"], 2, "4 feeds requested")
        self.assertEqual(report["total_feeds"], 4, "every feed was still evaluated")
        self.assertEqual(len(self.criterion_rows(OFFICIAL)), 1, "and still written")

    def test_feeds_omitted_is_zero_when_nothing_was_dropped(self):
        report = update_seals(dry_run=True, stable_feed_ids=[OFFICIAL], now=NOW)
        self.assertEqual(len(report["feeds"]), 1)
        self.assertEqual(report["feeds_omitted"], 0)


@patch("tasks.seal_of_reliability.seal_updater.EVALUATORS", WITH_PROBATION)
class TestProbation(SealDbTestCase):
    """Probation persisted and rolled up, driven by `_StandInEvaluator`.

    Timestamps are written out rather than derived so the assertions do not restate the
    implementation they are checking.
    """

    STREAK_STARTS = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
    CONFIRMED_AT = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)  # 14 days later
    REPAIRED_AT = datetime(2026, 6, 17, 12, 0, tzinfo=timezone.utc)
    PROBATION_FROM = datetime(
        2026, 6, 17, 0, 0, tzinfo=timezone.utc
    )  # the day of repair

    def stand_in(self):
        return self.criterion_rows(OFFICIAL)[SealCriterionName.AVAILABLE.value]

    def run_at(self, moment):
        update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=moment)

    def test_a_clean_run_puts_nothing_on_probation(self):
        self.run_at(NOW)
        self.assertIsNone(self.stand_in().probation_start)
        self.assertTrue(self.seal_row(OFFICIAL).has_seal)

    def test_a_failure_inside_the_grace_period_starts_no_probation(self):
        self.run_at(NOW)
        self.set_official(OFFICIAL, False)
        self.run_at(self.STREAK_STARTS)

        row = self.stand_in()
        self.assertFalse(row.observed_pass)
        self.assertTrue(row.confirmed_pass, "still inside its grace period")
        self.assertIsNone(row.probation_start)

    def test_probation_starts_on_the_day_of_repair(self):
        self.run_at(NOW)
        self.set_official(OFFICIAL, False)
        self.run_at(self.STREAK_STARTS)
        self.run_at(self.CONFIRMED_AT)

        row = self.stand_in()
        self.assertFalse(row.confirmed_pass, "the streak outlasted the grace period")
        self.assertEqual(row.probation_start, self.PROBATION_FROM)

    def test_probation_withholds_the_seal_while_every_criterion_passes(self):
        self.run_at(NOW)
        self.set_official(OFFICIAL, False)
        self.run_at(self.STREAK_STARTS)
        self.run_at(self.CONFIRMED_AT)
        self.set_official(OFFICIAL, True)
        self.run_at(self.REPAIRED_AT)

        rows = self.criterion_rows(OFFICIAL)
        self.assertTrue(rows[SealCriterionName.OFFICIAL.value].confirmed_pass)
        self.assertTrue(rows[SealCriterionName.AVAILABLE.value].confirmed_pass)
        self.assertEqual(
            rows[SealCriterionName.AVAILABLE.value].probation_start,
            self.PROBATION_FROM,
            "recovery clears the status but starts probation",
        )
        self.assertFalse(
            self.seal_row(OFFICIAL).has_seal,
            "both criteria pass, so only the open probation can be withholding it",
        )

    def test_the_seal_returns_once_probation_is_served(self):
        self.run_at(NOW)
        self.set_official(OFFICIAL, False)
        self.run_at(self.STREAK_STARTS)
        self.run_at(self.CONFIRMED_AT)
        self.set_official(OFFICIAL, True)
        self.run_at(self.REPAIRED_AT)

        served_at = self.PROBATION_FROM + PROBATION_PERIOD
        self.run_at(served_at)

        self.assertIsNone(self.stand_in().probation_start)
        seal = self.seal_row(OFFICIAL)
        self.assertTrue(seal.has_seal)
        self.assertEqual(seal.seal_earned_at, served_at)


class TestCriterionBroughtIntoServiceLate(SealDbTestCase):
    """A criterion whose evaluator arrives after the feed already has rows.

    This is the `available` case from #1761: its source only starts collecting on some date,
    so until then it has no row at all and the roll-up has to carry on without it. Each test
    runs once with Official alone, then again with the stand-in registered.
    """

    LATER = NOW + timedelta(days=1)

    def run_at(self, moment, evaluators):
        with patch("tasks.seal_of_reliability.seal_updater.EVALUATORS", evaluators):
            update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=moment)

    def test_a_criterion_with_no_row_does_not_deny_the_seal(self):
        """The waiver itself: an unevaluated criterion is skipped, not counted as failing."""
        self.run_at(NOW, [OfficialEvaluator()])

        self.assertEqual(
            set(self.criterion_rows(OFFICIAL)),
            {SealCriterionName.OFFICIAL.value},
            "the stand-in has no row yet",
        )
        self.assertTrue(self.seal_row(OFFICIAL).has_seal)

    def test_a_passing_newcomer_joins_without_disturbing_the_seal(self):
        self.run_at(NOW, [OfficialEvaluator()])
        earned_at = self.seal_row(OFFICIAL).seal_earned_at

        self.run_at(self.LATER, WITH_PROBATION)

        row = self.criterion_rows(OFFICIAL)[SealCriterionName.AVAILABLE.value]
        self.assertTrue(row.confirmed_pass)
        self.assertIsNone(row.probation_start, "a first verdict is not a recovery")
        seal = self.seal_row(OFFICIAL)
        self.assertTrue(seal.has_seal)
        self.assertEqual(
            seal.seal_earned_at,
            earned_at,
            "the seal was never withdrawn and re-granted",
        )
        self.assertIsNone(seal.seal_lost_at)

    def test_a_newcomer_whose_first_verdict_fails_gets_no_grace_period(self):
        """`first_evaluation` denies the grace period: nothing has been earned to hold.

        The stand-in does have a 14-day grace period, and it is deliberately not applied
        here — otherwise this feed would keep its seal for a fortnight on a criterion we
        have never once seen pass. So the failure is a confirmed failure on day one.
        """
        self.run_at(NOW, [OfficialEvaluator()])
        self.assertTrue(self.seal_row(OFFICIAL).has_seal)

        self.set_official(OFFICIAL, False)
        self.run_at(self.LATER, WITH_PROBATION)

        row = self.criterion_rows(OFFICIAL)[SealCriterionName.AVAILABLE.value]
        self.assertFalse(row.observed_pass)
        self.assertFalse(
            row.confirmed_pass, "a confirmed failure on its very first verdict"
        )
        self.assertEqual(row.first_observed_failure_at, self.LATER)
        self.assertEqual(row.last_confirmed_failure_at, self.LATER)

        seal = self.seal_row(OFFICIAL)
        self.assertFalse(seal.has_seal)
        self.assertEqual(seal.seal_lost_at, self.LATER)


@patch("tasks.seal_of_reliability.seal_updater.EVALUATORS", GOES_DARK)
class TestCriterionThatStopsBeingEvaluable(SealDbTestCase):
    """A criterion that produced a verdict once and then loses its input.

    The roll-up skips criteria that have *never* produced a verdict, so the safety of that
    rule rests entirely on a criterion never falling back into that state once it has one.
    """

    FAILED_AT = NOW + timedelta(days=1)

    def stand_in(self):
        return self.criterion_rows(OFFICIAL).get(SealCriterionName.COMPLIANT.value)

    def run_at(self, moment):
        update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=moment)

    def test_going_dark_freezes_the_verdict_and_keeps_the_seal_withheld(self):
        # Both criteria pass, then both fail and the seal goes.
        self.run_at(NOW)
        self.assertTrue(self.seal_row(OFFICIAL).has_seal)

        self.set_official(OFFICIAL, False)
        self.run_at(self.FAILED_AT)
        self.assertFalse(self.seal_row(OFFICIAL).has_seal)

        # Official recovers, but the stand-in has lost its input. Its stored failure must
        # stand and keep withholding the seal.
        self.set_official(OFFICIAL, True)
        self.run_at(DARK_FROM)

        rows = self.criterion_rows(OFFICIAL)
        self.assertTrue(
            rows[SealCriterionName.OFFICIAL.value].confirmed_pass,
            "the only other criterion is passing again",
        )
        frozen = rows[SealCriterionName.COMPLIANT.value]
        self.assertFalse(frozen.observed_pass, "the last verdict stands")
        self.assertFalse(frozen.confirmed_pass)
        self.assertEqual(
            frozen.evaluated_at, self.FAILED_AT, "not re-stamped without a verdict"
        )
        self.assertFalse(
            self.seal_row(OFFICIAL).has_seal,
            "going dark must not hand the seal back",
        )

    def test_going_dark_before_any_verdict_writes_no_row(self):
        """The other half: with no verdict ever, there is nothing to hold in service."""
        self.run_at(DARK_FROM)

        self.assertIsNone(self.stand_in(), "no row is written without a verdict")
        self.assertTrue(
            self.seal_row(OFFICIAL).has_seal,
            "and the criterion is skipped rather than denying the seal",
        )


if __name__ == "__main__":
    unittest.main()
