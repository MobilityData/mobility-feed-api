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
from dataclasses import fields
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from shared.common.seal_criteria import (
    AVAILABILITY_LOOKBACK,
    PROBATION_PERIOD,
    PROBATION_EXEMPT_CRITERIA,
    CriterionStatus,
    SealCriterionName,
    SealStatus,
    roll_up_seal_status,
)
from tasks.seal_of_reliability.context import (
    build_contexts,
    count_eligible_feeds,
    is_seal_eligible,
    iter_eligible_stable_ids,
)
from tasks.seal_of_reliability.evaluators import (
    EVALUATORS,
    CriterionEvaluator,
    OfficialEvaluator,
)
from tasks.seal_of_reliability.seal_updater import update_seals
from tasks.seal_of_reliability.state_machine import SealCriterionState
from sqlalchemy import delete, select

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Feed,
    FeedReliabilitySeal,
    GtfsFeedAvailabilityCheck,
    Gtfsdataset,
    Gtfsfeed,
    SealCriterion,
    SealCriterionSnapshot,
    Validationreport,
    t_validationreportgtfsdataset,
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
# An official feed old enough in the database for Stable to pass (every seeded feed is
# backdated 400 days), used by the tests that run the real registry rather than a patched one.
TRACKED = f"{PREFIX}tracked"

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
    `available` enum value and is patched over the whole registry, so the real
    AvailableEvaluator never runs alongside it.
    """

    name = SealCriterionName.AVAILABLE
    grace_period = timedelta(days=14)

    def _evaluate(self, ctx):
        status = CriterionStatus.PASS if ctx.official is True else CriterionStatus.FAIL
        return status, f"stand-in, feed.official is {ctx.official!r}"


# Patched over the registry so the roll-up sees a criterion that can be on probation.
WITH_PROBATION = [OfficialEvaluator(), _StandInEvaluator()]

# Official on its own. The classes below that assert seal outcomes are about the roll-up,
# the report and the snapshot table rather than about any particular criterion, and Official
# is the one that reaches a verdict from nothing but the feed row. Stable and Fresh need a
# seal row and a dataset to say anything, and both are exercised against real data in
# TestFullRegistry.
ONLY_OFFICIAL = [OfficialEvaluator()]


DARK_FROM = NOW + timedelta(days=2)


class _GoesDarkEvaluator(CriterionEvaluator):
    """A criterion that loses its upstream input partway through.

    It returns no verdict from `DARK_FROM` onwards, keyed on the clock rather than on
    `official` so that a test can drive it and Official in opposite directions at the same
    moment. No grace period, so its verdicts land immediately and the tests are about what
    happens once it goes quiet.
    """

    name = SealCriterionName.COMPLIANT
    grace_period = None

    def _evaluate(self, ctx):
        if ctx.now >= DARK_FROM:
            return CriterionStatus.UNKNOWN, "stand-in has no input this run"
        status = CriterionStatus.PASS if ctx.official is True else CriterionStatus.FAIL
        return status, f"stand-in, feed.official is {ctx.official!r}"


# Official is kept in the registry on purpose: it is passing by the time the stand-in goes
# dark, so if the stand-in's frozen row were dropped from the roll-up the seal would come
# straight back. Without it, the empty-in_service guard would mask that.
GOES_DARK = [OfficialEvaluator(), _GoesDarkEvaluator()]


EXCLUDED_FROM = NOW + timedelta(days=2)


class _StopsApplyingEvaluator(CriterionEvaluator):
    """A criterion that stops applying to the feed partway through, standing in for #1782.

    Fresh / continuous coverage does not apply to a seasonal feed, and a feed can be marked
    seasonal at any time. Keyed on the clock rather than on `official` so a test can drive it
    and Official in opposite directions at the same moment. No grace period, so its verdicts
    land immediately and the tests are about what happens once it withdraws.

    It borrows `fresh_continuous`, which has no evaluator of its own yet, rather than
    `fresh_coverage`, whose real evaluator now covers the same seasonal case against real
    data in `TestFullRegistry`.
    """

    name = SealCriterionName.FRESH_CONTINUOUS
    grace_period = None

    def _evaluate(self, ctx):
        if ctx.now >= EXCLUDED_FROM:
            return CriterionStatus.NOT_APPLICABLE, "the feed is seasonal"
        status = CriterionStatus.PASS if ctx.official is True else CriterionStatus.FAIL
        return status, f"stand-in, feed.official is {ctx.official!r}"


STOPS_APPLYING = [OfficialEvaluator(), _StopsApplyingEvaluator()]


class _NeverAnswersEvaluator(CriterionEvaluator):
    """A criterion whose input never arrives, so it never produces a verdict.

    Stands in for a criterion whose data source has not started collecting yet. Its
    `confirmed_status` therefore stays NEVER_EVALUATED for good, which is the input the
    feed-level UNKNOWN roll-up is about.
    """

    name = SealCriterionName.AVAILABLE
    grace_period = None

    def _evaluate(self, ctx):
        return CriterionStatus.UNKNOWN, "stand-in never has an input"


NEVER_ANSWERS = [_NeverAnswersEvaluator()]
OFFICIAL_AND_NEVER_ANSWERS = [OfficialEvaluator(), _NeverAnswersEvaluator()]


def _seed_feed(
    db_session,
    feed_id: str,
    official=True,
    status="active",
    operational_status="published",
    seasonal=False,
    is_producer_url_unstable=None,
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
            seasonal=seasonal,
            is_producer_url_unstable=is_producer_url_unstable,
            created_at=NOW - timedelta(days=400),
            producer_url=f"https://example.com/{feed_id}.zip",
        )
    )
    db_session.flush()


def _seed_dataset(
    db_session, feed_id: str, coverage_end, downloaded_at=None, suffix=""
):
    """Give the feed a dataset covering up to `coverage_end` (None = never extracted).

    `latest_dataset_id` is pointed at it too, so a test that only seeds one dataset matches
    what the catalog looks like. The criterion resolves the latest dataset from
    `downloaded_at` rather than from that pointer, which is what the two-dataset tests below
    exercise.
    """
    dataset_id = f"{feed_id}_dataset{suffix}"
    db_session.add(
        Gtfsdataset(
            id=dataset_id,
            feed_id=feed_id,
            stable_id=dataset_id,
            downloaded_at=downloaded_at or NOW - timedelta(days=1),
            service_date_range_start=NOW - timedelta(days=30),
            service_date_range_end=coverage_end,
        )
    )
    db_session.flush()
    db_session.execute(
        Gtfsfeed.__table__.update()
        .where(Gtfsfeed.__table__.c.id == feed_id)
        .values(latest_dataset_id=dataset_id)
    )
    db_session.commit()


def _seed_availability_check(db_session, feed_id: str, success, checked_at=None):
    """One `gtfs_feed_availability_check` row for the feed."""
    db_session.add(
        GtfsFeedAvailabilityCheck(
            feed_id=feed_id,
            checked_at=checked_at or NOW,
            request_url=f"https://example.com/{feed_id}.zip",
            request_type="http_head",
            status_code=200 if success else 503,
            success=success,
        )
    )
    db_session.commit()


def _seed_validation_report(
    db_session, dataset_id: str, total_error, validated_at=None, suffix=""
):
    """A validation report for the dataset, linked through validationreportgtfsdataset."""
    report_id = f"{dataset_id}_report{suffix}"
    db_session.add(
        Validationreport(
            id=report_id,
            validator_version=f"1.0.0{suffix}",
            validated_at=validated_at or NOW - timedelta(hours=1),
            total_error=total_error,
        )
    )
    db_session.flush()
    db_session.execute(
        t_validationreportgtfsdataset.insert().values(
            dataset_id=dataset_id, validation_report_id=report_id
        )
    )
    db_session.commit()


def _set_seasonal(db_session, feed_id: str, seasonal):
    db_session.execute(
        Feed.__table__.update()
        .where(Feed.__table__.c.id == feed_id)
        .values(seasonal=seasonal)
    )
    db_session.commit()


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
    # validationreport is not reachable by cascade from feed: deleting the feed cascades to
    # gtfsdataset and to the validationreportgtfsdataset join row, but leaves the report
    # itself orphaned, and the next test collides on its primary key.
    db_session.execute(
        delete(Validationreport).where(Validationreport.id.like(f"{PREFIX}%"))
    )
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
        _seed_feed(db_session, TRACKED)
        db_session.commit()

    @with_db_session(db_url=default_db_url)
    def tearDown(self, db_session):
        _cleanup(db_session)

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def criterion_rows(feed_id, db_session):
        table = SealCriterion.__table__
        return {
            row.criterion: row
            for row in db_session.execute(
                select(table).where(table.c.feed_id == feed_id)
            ).all()
        }

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def snapshot_rows(feed_id, criterion, db_session):
        """Every recorded day of one criterion, oldest first (issue #1809)."""
        table = SealCriterionSnapshot.__table__
        return db_session.execute(
            select(table)
            .where(table.c.feed_id == feed_id, table.c.criterion == criterion)
            .order_by(table.c.snapshot_date)
        ).all()

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def seal_row(feed_id, db_session):
        table = FeedReliabilitySeal.__table__
        return db_session.execute(
            select(table).where(table.c.feed_id == feed_id)
        ).first()

    def derived_seal_status(self, feed_id):
        """The feed's seal status, derived from the persisted rows the way the read API does.

        Nothing stores it, so an assertion has to re-derive it - and doing so from the rows the run
        wrote checks what the API will actually see.
        """
        return roll_up_seal_status(
            (
                CriterionStatus(row.confirmed_status),
                row.probation_start is not None
                and row.criterion not in PROBATION_EXEMPT_CRITERIA,
            )
            for row in self.criterion_rows(feed_id).values()
        ).value

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def set_official(feed_id, official, db_session):
        _set_official(db_session, feed_id, official)

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def set_seasonal(feed_id, seasonal, db_session):
        _set_seasonal(db_session, feed_id, seasonal)

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def set_producer_url_unstable(feed_id, unstable, db_session):
        db_session.execute(
            Feed.__table__.update()
            .where(Feed.__table__.c.id == feed_id)
            .values(is_producer_url_unstable=unstable)
        )
        db_session.commit()

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def seed_dataset(
        feed_id, coverage_end, downloaded_at=None, suffix="", db_session=None
    ):
        _seed_dataset(db_session, feed_id, coverage_end, downloaded_at, suffix)

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def seed_availability_check(feed_id, success, checked_at=None, db_session=None):
        _seed_availability_check(db_session, feed_id, success, checked_at)

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def seed_validation_report(
        dataset_id, total_error, validated_at=None, suffix="", db_session=None
    ):
        _seed_validation_report(
            db_session, dataset_id, total_error, validated_at, suffix
        )

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def set_feed_created_at(feed_id, created_at, db_session):
        db_session.execute(
            Feed.__table__.update()
            .where(Feed.__table__.c.id == feed_id)
            .values(created_at=created_at)
        )
        db_session.commit()


def _feeds_by_stable_id(db_session, *stable_ids):
    """Plain by-id load — mirrors what `update_seals` does before checking eligibility."""
    feeds = (
        db_session.query(Gtfsfeed)
        .filter(Gtfsfeed.stable_id.in_(list(stable_ids)))
        .all()
    )
    return {feed.stable_id: feed for feed in feeds}


class TestEligibilityQuery(SealDbTestCase):
    @with_db_session(db_url=default_db_url)
    def test_excludes_deprecated_and_unpublished_but_keeps_inactive(self, db_session):
        found = {
            stable_id
            for batch in iter_eligible_stable_ids(
                db_session,
                batch_size=10,
                stable_feed_ids=[OFFICIAL, INACTIVE, DEPRECATED, UNPUBLISHED],
            )
            for stable_id in batch
        }
        self.assertIn(OFFICIAL, found)
        self.assertIn(INACTIVE, found, "inactive feeds must be evaluated, not frozen")
        self.assertNotIn(DEPRECATED, found)
        self.assertNotIn(UNPUBLISHED, found)

    @with_db_session(db_url=default_db_url)
    def test_stable_feed_ids_narrows_the_same_query(self, db_session):
        self.assertEqual(
            count_eligible_feeds(db_session, stable_feed_ids=[OFFICIAL]), 1
        )
        batches = list(
            iter_eligible_stable_ids(
                db_session, batch_size=10, stable_feed_ids=[OFFICIAL]
            )
        )
        self.assertEqual(batches, [[OFFICIAL]])

    def test_batch_size_must_be_positive(self):
        """The raise happens before any DB access, so a MagicMock db_session suffices.

        iter_eligible_stable_ids is a generator, so the call itself doesn't raise until
        iterated — hence the list(...) wrapper here.
        """
        with self.assertRaises(ValueError):
            list(iter_eligible_stable_ids(MagicMock(), batch_size=0))
        with self.assertRaises(ValueError):
            list(iter_eligible_stable_ids(MagicMock(), batch_size=-5))


class TestIsSealEligible(SealDbTestCase):
    @with_db_session(db_url=default_db_url)
    def test_matches_the_db_level_predicate(self, db_session):
        feeds = _feeds_by_stable_id(
            db_session, OFFICIAL, INACTIVE, DEPRECATED, UNPUBLISHED
        )
        self.assertTrue(is_seal_eligible(feeds[OFFICIAL]))
        self.assertTrue(
            is_seal_eligible(feeds[INACTIVE]), "inactive feeds must stay eligible"
        )
        self.assertFalse(is_seal_eligible(feeds[DEPRECATED]))
        self.assertFalse(is_seal_eligible(feeds[UNPUBLISHED]))


class TestBuildContexts(SealDbTestCase):
    @with_db_session(db_url=default_db_url)
    def test_loads_the_fields_the_evaluators_need(self, db_session):
        feeds = list(_feeds_by_stable_id(db_session, OFFICIAL).values())
        ctx = build_contexts(db_session, feeds, NOW)[feeds[0].id]
        self.assertEqual(ctx.stable_id, OFFICIAL)
        self.assertTrue(ctx.official)
        self.assertEqual(ctx.now, NOW)
        self.assertFalse(ctx.seasonal)
        self.assertIsNone(ctx.is_producer_url_unstable)

    @with_db_session(db_url=default_db_url)
    def test_stables_clock_is_the_feed_row_and_needs_no_query(self, db_session):
        feeds = list(_feeds_by_stable_id(db_session, OFFICIAL).values())
        ctx = build_contexts(db_session, feeds, NOW)[feeds[0].id]
        self.assertEqual(ctx.feed_created_at, NOW - timedelta(days=400))

    @with_db_session(db_url=default_db_url)
    def test_a_feed_with_no_dataset_says_so(self, db_session):
        """The bulk load misses, and the context says so rather than guessing a value."""
        feeds = list(_feeds_by_stable_id(db_session, OFFICIAL).values())
        ctx = build_contexts(db_session, feeds, NOW)[feeds[0].id]
        self.assertIsNone(ctx.latest_dataset)

    @with_db_session(db_url=default_db_url)
    def test_the_latest_dataset_coverage_is_loaded(self, db_session):
        _seed_dataset(db_session, TRACKED, coverage_end=NOW + timedelta(days=90))
        feeds = list(_feeds_by_stable_id(db_session, TRACKED).values())
        ctx = build_contexts(db_session, feeds, NOW)[feeds[0].id]
        self.assertEqual(ctx.latest_dataset.dataset_id, f"{TRACKED}_dataset")
        self.assertEqual(
            ctx.latest_dataset.service_date_range_end, NOW + timedelta(days=90)
        )

    @with_db_session(db_url=default_db_url)
    def test_a_dataset_with_no_coverage_end_is_not_a_missing_dataset(self, db_session):
        """The two UNKNOWN cases must stay distinguishable at the context layer."""
        _seed_dataset(db_session, TRACKED, coverage_end=None)
        feeds = list(_feeds_by_stable_id(db_session, TRACKED).values())
        ctx = build_contexts(db_session, feeds, NOW)[feeds[0].id]
        self.assertIsNotNone(ctx.latest_dataset, "the dataset is there ...")
        self.assertIsNone(
            ctx.latest_dataset.service_date_range_end, "... its coverage end is not"
        )

    @with_db_session(db_url=default_db_url)
    def test_the_latest_dataset_is_resolved_as_of_now(self, db_session):
        """A replay must not see a dataset published after the day it is evaluating.

        `gtfsfeed.latest_dataset_id` points at the newest dataset that exists today, so
        reading it would report the feed as fresh on a day when the data covering that day
        had not been published yet.
        """
        _seed_dataset(
            db_session,
            TRACKED,
            coverage_end=NOW + timedelta(days=5),
            downloaded_at=NOW - timedelta(days=10),
            suffix="_old",
        )
        _seed_dataset(
            db_session,
            TRACKED,
            coverage_end=NOW + timedelta(days=400),
            downloaded_at=NOW + timedelta(days=10),
            suffix="_new",
        )
        feeds = list(_feeds_by_stable_id(db_session, TRACKED).values())

        as_of_now = build_contexts(db_session, feeds, NOW)[feeds[0].id]
        self.assertEqual(
            as_of_now.latest_dataset.service_date_range_end,
            NOW + timedelta(days=5),
            "the newer dataset had not been downloaded yet",
        )

        later = NOW + timedelta(days=20)
        as_of_later = build_contexts(db_session, feeds, later)[feeds[0].id]
        self.assertEqual(
            as_of_later.latest_dataset.service_date_range_end,
            NOW + timedelta(days=400),
            "by then it had",
        )

    @with_db_session(db_url=default_db_url)
    def test_a_check_inside_the_rolling_window_counts(self, db_session):
        _seed_availability_check(db_session, TRACKED, True, NOW - timedelta(hours=6))
        feeds = list(_feeds_by_stable_id(db_session, TRACKED).values())
        ctx = build_contexts(db_session, feeds, NOW)[feeds[0].id]
        self.assertTrue(ctx.availability_check.success)

    @with_db_session(db_url=default_db_url)
    def test_the_window_is_exactly_the_lookback(self, db_session):
        """A check just inside the window counts; the same check an hour older does not."""
        _seed_availability_check(
            db_session,
            TRACKED,
            True,
            NOW - AVAILABILITY_LOOKBACK + timedelta(minutes=1),
        )
        feeds = list(_feeds_by_stable_id(db_session, TRACKED).values())
        self.assertIsNotNone(
            build_contexts(db_session, feeds, NOW)[feeds[0].id].availability_check
        )
        self.assertIsNone(
            build_contexts(db_session, feeds, NOW + timedelta(hours=1))[
                feeds[0].id
            ].availability_check
        )

    @with_db_session(db_url=default_db_url)
    def test_a_check_older_than_the_fallback_window_is_ignored(self, db_session):
        _seed_availability_check(db_session, TRACKED, True, NOW - timedelta(days=3))
        feeds = list(_feeds_by_stable_id(db_session, TRACKED).values())
        ctx = build_contexts(db_session, feeds, NOW)[feeds[0].id]
        self.assertIsNone(ctx.availability_check)

    @with_db_session(db_url=default_db_url)
    def test_a_check_after_now_is_not_visible_yet(self, db_session):
        """Same replay rule as everywhere else: a run never reads its own future."""
        _seed_availability_check(db_session, TRACKED, True, NOW + timedelta(hours=1))
        feeds = list(_feeds_by_stable_id(db_session, TRACKED).values())
        self.assertIsNone(
            build_contexts(db_session, feeds, NOW)[feeds[0].id].availability_check
        )

    @with_db_session(db_url=default_db_url)
    def test_the_latest_check_in_the_window_decides(self, db_session):
        """Not "any success": the most recent answer describes the feed now."""
        _seed_availability_check(db_session, TRACKED, True, NOW - timedelta(hours=5))
        _seed_availability_check(db_session, TRACKED, False, NOW - timedelta(hours=1))
        feeds = list(_feeds_by_stable_id(db_session, TRACKED).values())
        ctx = build_contexts(db_session, feeds, NOW)[feeds[0].id]
        self.assertFalse(ctx.availability_check.success)
        self.assertEqual(ctx.availability_check.checked_at, NOW - timedelta(hours=1))

    @with_db_session(db_url=default_db_url)
    def test_a_failed_check_is_a_verdict_not_a_missing_one(self, db_session):
        """A check that ran and failed and no check at all are different answers."""
        _seed_availability_check(db_session, TRACKED, False, NOW)
        feeds = list(_feeds_by_stable_id(db_session, TRACKED).values())
        ctx = build_contexts(db_session, feeds, NOW)[feeds[0].id]
        self.assertIsNotNone(ctx.availability_check)
        self.assertFalse(ctx.availability_check.success)

    @with_db_session(db_url=default_db_url)
    def test_the_latest_validation_report_is_loaded(self, db_session):
        _seed_dataset(db_session, TRACKED, coverage_end=NOW + timedelta(days=90))
        _seed_validation_report(db_session, f"{TRACKED}_dataset", total_error=3)
        feeds = list(_feeds_by_stable_id(db_session, TRACKED).values())
        ctx = build_contexts(db_session, feeds, NOW)[feeds[0].id]
        self.assertEqual(ctx.latest_validation_report.total_error, 3)

    @with_db_session(db_url=default_db_url)
    def test_a_feed_with_no_report_carries_none(self, db_session):
        _seed_dataset(db_session, TRACKED, coverage_end=NOW + timedelta(days=90))
        feeds = list(_feeds_by_stable_id(db_session, TRACKED).values())
        ctx = build_contexts(db_session, feeds, NOW)[feeds[0].id]
        self.assertIsNotNone(ctx.latest_dataset, "the dataset is there ...")
        self.assertIsNone(ctx.latest_validation_report, "... a report is not")

    @with_db_session(db_url=default_db_url)
    def test_a_report_on_a_superseded_dataset_is_not_loaded(self, db_session):
        """The report is the latest dataset's, so an older dataset's report is not it.

        Validation lags publication, so the newest dataset may have no report yet. That is
        left as "no report" rather than backfilled from the dataset before it: the criterion
        is about the data being served now.
        """
        _seed_dataset(
            db_session,
            TRACKED,
            coverage_end=NOW + timedelta(days=90),
            downloaded_at=NOW - timedelta(days=5),
            suffix="_older",
        )
        _seed_validation_report(
            db_session, f"{TRACKED}_dataset_older", total_error=0, suffix="_older"
        )
        _seed_dataset(
            db_session,
            TRACKED,
            coverage_end=NOW + timedelta(days=90),
            downloaded_at=NOW - timedelta(hours=2),
            suffix="_newest",
        )
        feeds = list(_feeds_by_stable_id(db_session, TRACKED).values())
        ctx = build_contexts(db_session, feeds, NOW)[feeds[0].id]

        self.assertEqual(ctx.latest_dataset.dataset_id, f"{TRACKED}_dataset_newest")
        self.assertIsNone(
            ctx.latest_validation_report,
            "the older dataset's report does not describe what is being served",
        )

    @with_db_session(db_url=default_db_url)
    def test_the_validation_report_is_resolved_as_of_now(self, db_session):
        """Same replay rule as the dataset: a later re-validation must not leak backwards."""
        _seed_dataset(db_session, TRACKED, coverage_end=NOW + timedelta(days=90))
        dataset_id = f"{TRACKED}_dataset"
        _seed_validation_report(
            db_session,
            dataset_id,
            5,
            validated_at=NOW - timedelta(days=2),
            suffix="_old",
        )
        _seed_validation_report(
            db_session,
            dataset_id,
            0,
            validated_at=NOW + timedelta(days=2),
            suffix="_new",
        )
        feeds = list(_feeds_by_stable_id(db_session, TRACKED).values())

        as_of_now = build_contexts(db_session, feeds, NOW)[feeds[0].id]
        self.assertEqual(
            as_of_now.latest_validation_report.total_error,
            5,
            "the re-validation had not happened yet",
        )

        later = NOW + timedelta(days=3)
        as_of_later = build_contexts(db_session, feeds, later)[feeds[0].id]
        self.assertEqual(as_of_later.latest_validation_report.total_error, 0)

    @with_db_session(db_url=default_db_url)
    def test_a_report_with_no_validated_at_is_excluded(self, db_session):
        """It cannot be placed in time, so it is dropped rather than guessed at."""
        _seed_dataset(db_session, TRACKED, coverage_end=NOW + timedelta(days=90))
        _seed_validation_report(db_session, f"{TRACKED}_dataset", total_error=0)
        db_session.execute(
            Validationreport.__table__.update().values(validated_at=None)
        )
        db_session.commit()
        feeds = list(_feeds_by_stable_id(db_session, TRACKED).values())
        ctx = build_contexts(db_session, feeds, NOW)[feeds[0].id]
        self.assertIsNone(ctx.latest_validation_report)

    @with_db_session(db_url=default_db_url)
    def test_a_dataset_with_no_downloaded_at_cannot_be_placed_in_time(self, db_session):
        """It is excluded rather than guessed at: we cannot say whether it existed yet."""
        _seed_dataset(db_session, TRACKED, coverage_end=NOW + timedelta(days=90))
        db_session.execute(
            Gtfsdataset.__table__.update()
            .where(Gtfsdataset.__table__.c.feed_id == TRACKED)
            .values(downloaded_at=None)
        )
        db_session.commit()
        feeds = list(_feeds_by_stable_id(db_session, TRACKED).values())
        ctx = build_contexts(db_session, feeds, NOW)[feeds[0].id]
        self.assertIsNone(ctx.latest_dataset)

    @with_db_session(db_url=default_db_url)
    def test_builds_one_context_per_feed(self, db_session):
        feeds = list(_feeds_by_stable_id(db_session, OFFICIAL, NOT_OFFICIAL).values())
        contexts = build_contexts(db_session, feeds, NOW)
        self.assertEqual(len(contexts), 2)
        self.assertEqual({ctx.official for ctx in contexts.values()}, {True, False})


@patch("tasks.seal_of_reliability.seal_updater.EVALUATORS", ONLY_OFFICIAL)
class TestUpdateSeals(SealDbTestCase):
    """The report, the roll-up and the two seal transitions, driven by Official alone."""

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
        self.assertEqual(
            feed["criteria"][0]["observed_status"], CriterionStatus.FAIL.value
        )
        self.assertTrue(feed["criteria"][0]["reason"])
        self.assertIsNone(feed["criteria"][0]["previously_confirmed_status"])

    def test_named_feed_is_reported_even_when_nothing_moved(self):
        """An explicit feed list is the debugging path: report it either way."""
        update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=NOW)
        report = update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=NOW)

        feed = report["feeds"][0]
        self.assertTrue(feed["had_seal"])
        self.assertTrue(feed["has_seal"])
        self.assertEqual(
            feed["criteria"][0]["confirmed_status"], CriterionStatus.PASS.value
        )
        self.assertEqual(
            feed["criteria"][0]["previously_confirmed_status"],
            CriterionStatus.PASS.value,
        )

    def test_every_requested_feed_is_reported(self):
        """There is no run-the-catalogue mode: the report covers exactly the feeds asked for."""
        report = update_seals(dry_run=False, stable_feed_ids=OURS, now=NOW)
        reported = {row["stable_id"] for row in report["feeds"]}
        self.assertEqual(reported, set(OURS))

    def test_a_feed_that_flips_is_reported_with_the_previous_verdict(self):
        update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=NOW)
        self.set_official(OFFICIAL, False)
        report = update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=NOW)

        moved = [row for row in report["feeds"] if row["stable_id"] == OFFICIAL]
        self.assertEqual(len(moved), 1)
        self.assertTrue(moved[0]["had_seal"])
        self.assertFalse(moved[0]["has_seal"])
        self.assertEqual(
            moved[0]["criteria"][0]["confirmed_status"], CriterionStatus.FAIL.value
        )
        self.assertEqual(
            moved[0]["criteria"][0]["previously_confirmed_status"],
            CriterionStatus.PASS.value,
        )

    def test_official_feed_earns_the_seal(self):
        update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=NOW)
        row = self.criterion_rows(OFFICIAL)[SealCriterionName.OFFICIAL.value]
        self.assertEqual(row.observed_status, CriterionStatus.PASS.value)
        self.assertEqual(row.confirmed_status, CriterionStatus.PASS.value)
        self.assertEqual(row.evaluated_at, NOW)
        self.assertEqual(row.last_verdict_at, NOW)
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
        self.assertEqual(row.observed_status, CriterionStatus.FAIL.value)
        self.assertEqual(row.confirmed_status, CriterionStatus.FAIL.value)
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
        self.assertEqual(row.confirmed_status, CriterionStatus.PASS.value)
        self.assertIsNone(row.first_observed_failure_at, "the streak is cleared")
        self.assertIsNone(row.probation_start, "Official serves no probation")
        self.assertEqual(
            row.last_confirmed_failure_at, NOW, "the failure is still on record"
        )
        seal = self.seal_row(NOT_OFFICIAL)
        self.assertTrue(seal.has_seal)
        self.assertEqual(seal.seal_earned_at, later)

    def test_partial_criteria_run_skips_the_roll_up(self):
        """Naming every criterion in the registry is not a partial run.

        Under this class's patch the registry is Official alone; `TestCriteriaSelection`
        covers the same distinction against the real, larger registry.
        """
        report = update_seals(
            dry_run=False,
            stable_feed_ids=[OFFICIAL],
            criteria=[SealCriterionName.OFFICIAL.value],
            now=NOW,
        )
        self.assertFalse(report["partial_run"])
        self.assertTrue(self.seal_row(OFFICIAL).has_seal)

    def test_a_feed_list_is_required(self):
        """There is no run-the-whole-catalogue mode; the list must be given and non-empty."""
        for feeds in (None, []):
            with self.subTest(stable_feed_ids=feeds):
                with self.assertRaises(ValueError) as caught:
                    update_seals(dry_run=True, stable_feed_ids=feeds, now=NOW)
                self.assertIn("stable_feed_ids", str(caught.exception))

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
        report = update_seals(dry_run=True, stable_feed_ids=OURS, limit=2, now=NOW)
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


class TestSealStatusRollUp(SealDbTestCase):
    """The four-way feed-level outcome, and the boolean that hangs off it.

    `has_seal` answers only "does the feed hold the seal", so all three non-granting values
    read as false through it. `seal_status` is what tells them apart, and the distinction that
    matters is between a feed that was judged and did not qualify and one that could not be
    judged at all.
    """

    @patch("tasks.seal_of_reliability.seal_updater.EVALUATORS", ONLY_OFFICIAL)
    def test_every_criterion_passing_grants_the_seal(self):
        update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=NOW)

        seal = self.seal_row(OFFICIAL)
        self.assertEqual(self.derived_seal_status(OFFICIAL), SealStatus.GRANTED.value)
        self.assertTrue(seal.has_seal)

    @patch("tasks.seal_of_reliability.seal_updater.EVALUATORS", ONLY_OFFICIAL)
    def test_a_judged_feed_that_does_not_qualify_is_not_granted(self):
        """Not the same as unknown: every criterion answered, and the answer was no."""
        update_seals(dry_run=False, stable_feed_ids=[NOT_OFFICIAL], now=NOW)

        seal = self.seal_row(NOT_OFFICIAL)
        self.assertEqual(
            self.derived_seal_status(NOT_OFFICIAL), SealStatus.NOT_GRANTED.value
        )
        self.assertFalse(seal.has_seal)

    @patch("tasks.seal_of_reliability.seal_updater.EVALUATORS", NEVER_ANSWERS)
    def test_no_criterion_ever_judged_is_never_evaluated(self):
        """A row is written - the attempt happened - but nothing has been decided."""
        update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=NOW)

        seal = self.seal_row(OFFICIAL)
        self.assertEqual(
            self.derived_seal_status(OFFICIAL), SealStatus.NEVER_EVALUATED.value
        )
        self.assertFalse(seal.has_seal)

    @patch(
        "tasks.seal_of_reliability.seal_updater.EVALUATORS", OFFICIAL_AND_NEVER_ANSWERS
    )
    def test_one_criterion_without_a_verdict_makes_the_whole_seal_unknown(self):
        """Official passes, but the other criterion has never been judged.

        The feed may well qualify - which is exactly why this is not NOT_GRANTED - but it
        cannot be granted the seal on evidence covering only half its criteria.
        """
        update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=NOW)

        rows = self.criterion_rows(OFFICIAL)
        self.assertEqual(
            rows[SealCriterionName.OFFICIAL.value].confirmed_status,
            CriterionStatus.PASS.value,
        )
        seal = self.seal_row(OFFICIAL)
        self.assertEqual(self.derived_seal_status(OFFICIAL), SealStatus.UNKNOWN.value)
        self.assertFalse(seal.has_seal)

    @patch(
        "tasks.seal_of_reliability.seal_updater.EVALUATORS", OFFICIAL_AND_NEVER_ANSWERS
    )
    def test_a_transient_outage_does_not_make_a_judged_seal_unknown(self):
        """The distinction the roll-up rests on: no verdict *ever*, not no verdict today.

        The first run is driven by the real registry, so both criteria reach a verdict. The
        second patches one of them dark; it keeps its stored pass, and the seal stays granted.
        """
        with patch(
            "tasks.seal_of_reliability.seal_updater.EVALUATORS",
            [OfficialEvaluator(), _StandInEvaluator()],
        ):
            update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=NOW)
        self.assertEqual(self.derived_seal_status(OFFICIAL), SealStatus.GRANTED.value)

        later = NOW + timedelta(days=1)
        update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=later)

        row = self.criterion_rows(OFFICIAL)[SealCriterionName.AVAILABLE.value]
        self.assertEqual(row.observed_status, CriterionStatus.UNKNOWN.value)
        self.assertEqual(row.confirmed_status, CriterionStatus.PASS.value)
        seal = self.seal_row(OFFICIAL)
        self.assertEqual(self.derived_seal_status(OFFICIAL), SealStatus.GRANTED.value)
        self.assertTrue(seal.has_seal)

    @patch("tasks.seal_of_reliability.seal_updater.EVALUATORS", ONLY_OFFICIAL)
    def test_the_report_counts_and_names_the_outcomes(self):
        """The two decided values, from `official` alone across the seeded feeds."""
        report = update_seals(dry_run=True, stable_feed_ids=OURS, now=NOW)

        counts = report["seal_status_counts"]
        self.assertEqual(set(counts), {status.value for status in SealStatus})
        self.assertEqual(
            sum(counts.values()),
            report["total_feeds"],
            "every feed lands in exactly one",
        )
        self.assertEqual(
            {row["stable_id"]: row["seal_status"] for row in report["feeds"]},
            {
                OFFICIAL: SealStatus.GRANTED.value,
                INACTIVE: SealStatus.GRANTED.value,
                NOT_OFFICIAL: SealStatus.NOT_GRANTED.value,
                # `official IS NULL` is a verdict for Official, not an absent one.
                UNKNOWN_OFFICIAL: SealStatus.NOT_GRANTED.value,
            },
        )
        self.assertEqual(counts[SealStatus.GRANTED.value], 2)

    @patch(
        "tasks.seal_of_reliability.seal_updater.EVALUATORS", OFFICIAL_AND_NEVER_ANSWERS
    )
    def test_an_unjudged_criterion_outranks_a_failing_one(self):
        """A feed failing Official is still UNKNOWN, not NOT_GRANTED, while a criterion has
        never been judged.

        Deliberate: the roll-up reports whether the feed could be judged before it reports
        the verdict, so `unknown` always means the same thing - the evaluation is incomplete -
        rather than meaning it only when nothing else had an opinion.
        """
        update_seals(dry_run=False, stable_feed_ids=[NOT_OFFICIAL], now=NOW)

        rows = self.criterion_rows(NOT_OFFICIAL)
        self.assertEqual(
            rows[SealCriterionName.OFFICIAL.value].confirmed_status,
            CriterionStatus.FAIL.value,
        )
        seal = self.seal_row(NOT_OFFICIAL)
        self.assertEqual(
            self.derived_seal_status(NOT_OFFICIAL), SealStatus.UNKNOWN.value
        )
        self.assertFalse(seal.has_seal)


@patch("tasks.seal_of_reliability.seal_updater.EVALUATORS", ONLY_OFFICIAL)
class TestCriterionSnapshot(SealDbTestCase):
    """seal_criterion_snapshot, the per-day record of each criterion (issue #1809).

    Official is enough to drive all of this: what is under test is which day a run records,
    what it leaves alone, and that the record matches the state — not the verdict itself.
    """

    CRITERION = SealCriterionName.OFFICIAL.value

    def snapshots(self):
        return self.snapshot_rows(OFFICIAL, self.CRITERION)

    def test_a_run_records_the_day_it_evaluated(self):
        update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=NOW)
        rows = self.snapshots()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].snapshot_date, NOW.date())
        self.assertEqual(rows[0].observed_status, CriterionStatus.PASS.value)

    def test_the_report_names_the_day_recorded(self):
        report = update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=NOW)
        self.assertEqual(report["snapshot_date"], NOW.date().isoformat())

    def test_a_dry_run_records_nothing(self):
        update_seals(dry_run=True, stable_feed_ids=[OFFICIAL], now=NOW)
        self.assertEqual(self.snapshots(), [])

    def test_each_run_records_its_own_day(self):
        days = [NOW, NOW + timedelta(days=1), NOW + timedelta(days=2)]
        for moment in days:
            update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=moment)

        self.assertEqual(
            [row.snapshot_date for row in self.snapshots()],
            [moment.date() for moment in days],
        )

    def test_rerunning_a_day_overwrites_its_row(self):
        """The day is the key, so how many times the job ran that day leaves no trace."""
        update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=NOW)
        self.set_official(OFFICIAL, False)
        update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=NOW)

        rows = self.snapshots()
        self.assertEqual(len(rows), 1, "one row for the day, not one per run")
        self.assertEqual(
            rows[0].observed_status,
            CriterionStatus.FAIL.value,
            "and it holds what the last run of that day wrote",
        )

    def test_a_later_run_leaves_earlier_days_alone(self):
        update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=NOW)
        self.set_official(OFFICIAL, False)
        update_seals(
            dry_run=False, stable_feed_ids=[OFFICIAL], now=NOW + timedelta(days=1)
        )

        first, second = self.snapshots()
        self.assertEqual(first.snapshot_date, NOW.date())
        self.assertEqual(
            first.confirmed_status,
            CriterionStatus.PASS.value,
            "day one still records the pass it saw; the record is not restated",
        )
        self.assertEqual(second.confirmed_status, CriterionStatus.FAIL.value)

    def test_the_latest_row_matches_the_current_state(self):
        """Both tables are written from the same state, so they cannot disagree."""
        update_seals(dry_run=False, stable_feed_ids=[NOT_OFFICIAL], now=NOW)

        current = self.criterion_rows(NOT_OFFICIAL)[self.CRITERION]
        recorded = self.snapshot_rows(NOT_OFFICIAL, self.CRITERION)[-1]
        for column in (
            "observed_status",
            "confirmed_status",
            "last_verdict_at",
            "first_observed_failure_at",
            "last_observed_failure_at",
            "last_confirmed_failure_at",
            "probation_start",
        ):
            self.assertEqual(
                getattr(recorded, column),
                getattr(current, column),
                f"{column} differs between seal_criterion and seal_criterion_snapshot",
            )

    def test_the_log_covers_every_field_the_state_carries(self):
        """A field added to the state machine must be recorded, or a replay cannot resume.

        Guards the derivation in `SNAPSHOT_STATE_COLUMNS`: it is built from the table, so a new
        state field that nobody added a column for would be dropped silently.
        """
        recorded = {column.name for column in SealCriterionSnapshot.__table__.columns}
        carried = {
            field.name
            for field in fields(SealCriterionState)
            # The key, and the one field the state machine writes but never reads back.
            if field.name not in ("feed_id", "criterion", "evaluated_at")
        }
        self.assertEqual(carried - recorded, set())


class TestFullRegistry(SealDbTestCase):
    """Official, Stable and Fresh together, against real rows and the real registry.

    The classes above patch the registry down to Official because they are about the
    report, the roll-up and the snapshot table rather than about any one criterion. These
    tests are the other half: the three implemented criteria, driven by the columns they
    actually read.
    """

    FAR_FUTURE = NOW + timedelta(days=90)

    def criteria_of(self, feed_id=TRACKED):
        return {
            criterion: row.confirmed_status
            for criterion, row in self.criterion_rows(feed_id).items()
        }

    def test_every_criterion_is_written_for_every_feed(self):
        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=NOW)
        self.assertEqual(
            set(self.criterion_rows(TRACKED)),
            {evaluator.name.value for evaluator in EVALUATORS},
        )

    def satisfy_everything(self):
        """Seed the inputs every implemented criterion needs, all passing."""
        self.seed_dataset(TRACKED, self.FAR_FUTURE)
        self.seed_availability_check(TRACKED, success=True)
        self.seed_validation_report(f"{TRACKED}_dataset", total_error=0)

    def test_a_feed_meeting_every_criterion_earns_the_seal(self):
        self.satisfy_everything()

        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=NOW)

        self.assertEqual(
            self.criteria_of(),
            {
                evaluator.name.value: CriterionStatus.PASS.value
                for evaluator in EVALUATORS
            },
        )
        self.assertTrue(self.seal_row(TRACKED).has_seal)

    def test_criteria_with_no_data_leave_the_seal_unknown(self):
        """Available and Compliant have never had a verdict, so the seal cannot be decided.

        They do not *deny* the seal - the feed may well qualify - but with two of five
        criteria unjudged, saying it does not qualify would be as wrong as saying it does.
        """
        self.seed_dataset(TRACKED, self.FAR_FUTURE)

        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=NOW)

        rows = self.criterion_rows(TRACKED)
        for criterion in (
            SealCriterionName.AVAILABLE.value,
            SealCriterionName.COMPLIANT.value,
        ):
            with self.subTest(criterion=criterion):
                self.assertEqual(
                    rows[criterion].observed_status, CriterionStatus.UNKNOWN.value
                )
                self.assertEqual(
                    rows[criterion].confirmed_status,
                    CriterionStatus.NEVER_EVALUATED.value,
                )
        seal = self.seal_row(TRACKED)
        self.assertEqual(self.derived_seal_status(TRACKED), SealStatus.UNKNOWN.value)
        self.assertFalse(seal.has_seal, "unknown is not a grant")

    def test_a_failed_availability_check_denies_the_seal(self):
        self.satisfy_everything()
        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=NOW)
        self.assertTrue(self.seal_row(TRACKED).has_seal)

        # Next day: the only check that ran failed.
        later = NOW + timedelta(days=1)
        self.seed_availability_check(TRACKED, success=False, checked_at=later)
        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=later)

        row = self.criterion_rows(TRACKED)[SealCriterionName.AVAILABLE.value]
        self.assertEqual(row.observed_status, CriterionStatus.FAIL.value)
        self.assertEqual(
            row.confirmed_status,
            CriterionStatus.PASS.value,
            "Available has a 14-day grace period and had already passed",
        )
        self.assertTrue(self.seal_row(TRACKED).has_seal, "still held, under grace")

    def test_a_recovery_later_in_the_window_wins(self):
        """Several checks in one window: the most recent one is the verdict."""
        self.satisfy_everything()
        later = NOW + timedelta(days=1)
        self.seed_availability_check(TRACKED, success=False, checked_at=later)
        self.seed_availability_check(
            TRACKED, success=True, checked_at=later + timedelta(hours=2)
        )

        update_seals(
            dry_run=False,
            stable_feed_ids=[TRACKED],
            now=later + timedelta(hours=3),
        )

        row = self.criterion_rows(TRACKED)[SealCriterionName.AVAILABLE.value]
        self.assertEqual(row.observed_status, CriterionStatus.PASS.value)

    def test_a_check_still_answers_a_second_run_inside_the_window(self):
        """The window is a rolling 24h, not "checks this run has not seen yet"."""
        self.satisfy_everything()
        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=NOW)

        # Six hours later, no new check: the earlier one is still inside the window.
        later = NOW + timedelta(hours=6)
        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=later)

        row = self.criterion_rows(TRACKED)[SealCriterionName.AVAILABLE.value]
        self.assertEqual(row.observed_status, CriterionStatus.PASS.value)
        self.assertTrue(self.seal_row(TRACKED).has_seal)

    def test_the_criterion_goes_quiet_once_the_check_ages_out(self):
        """A day with no check at all is UNKNOWN, which freezes the last verdict."""
        self.satisfy_everything()
        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=NOW)

        stale = NOW + AVAILABILITY_LOOKBACK + timedelta(hours=1)
        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=stale)

        row = self.criterion_rows(TRACKED)[SealCriterionName.AVAILABLE.value]
        self.assertEqual(row.observed_status, CriterionStatus.UNKNOWN.value)
        self.assertEqual(
            row.confirmed_status,
            CriterionStatus.PASS.value,
            "UNKNOWN freezes the criterion at its last verdict rather than failing it",
        )
        self.assertTrue(self.seal_row(TRACKED).has_seal)

    def test_a_late_availability_job_is_picked_up_by_the_next_run(self):
        """The reason for the window: a check the seal run missed is not lost.

        The seal runs, sees nothing; the availability job lands afterwards; the next seal run
        still reads that check instead of it falling into a closed calendar day.
        """
        self.seed_dataset(TRACKED, self.FAR_FUTURE)
        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=NOW)
        self.assertEqual(
            self.criterion_rows(TRACKED)[
                SealCriterionName.AVAILABLE.value
            ].observed_status,
            CriterionStatus.UNKNOWN.value,
        )

        self.seed_availability_check(
            TRACKED, success=True, checked_at=NOW + timedelta(hours=1)
        )
        later = NOW + timedelta(hours=2)
        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=later)

        row = self.criterion_rows(TRACKED)[SealCriterionName.AVAILABLE.value]
        self.assertEqual(row.observed_status, CriterionStatus.PASS.value)
        self.assertEqual(row.confirmed_status, CriterionStatus.PASS.value)

    def test_validation_errors_deny_the_seal(self):
        self.seed_dataset(TRACKED, self.FAR_FUTURE)
        self.seed_availability_check(TRACKED, success=True)
        self.seed_validation_report(f"{TRACKED}_dataset", total_error=7)

        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=NOW)

        row = self.criterion_rows(TRACKED)[SealCriterionName.COMPLIANT.value]
        self.assertEqual(row.observed_status, CriterionStatus.FAIL.value)
        self.assertEqual(
            row.confirmed_status,
            CriterionStatus.FAIL.value,
            "a first verdict gets no grace period",
        )
        self.assertFalse(self.seal_row(TRACKED).has_seal)

    def test_a_dataset_with_no_report_is_unknown_not_compliant(self):
        """A missing report is not a clean bill of health."""
        self.seed_dataset(TRACKED, self.FAR_FUTURE)

        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=NOW)

        row = self.criterion_rows(TRACKED)[SealCriterionName.COMPLIANT.value]
        self.assertEqual(row.observed_status, CriterionStatus.UNKNOWN.value)
        self.assertIsNone(row.last_verdict_at)

    def test_a_feed_publishing_faster_than_validation_keeps_its_last_verdict(self):
        """Daily publishing plus lagging validation, which is the common case.

        Each new dataset arrives unvalidated, so Compliant observes UNKNOWN on the days in
        between. That freezes the criterion at the verdict it last earned instead of failing
        it, so the feed keeps the seal while the validator catches up.
        """
        self.seed_availability_check(TRACKED, success=True)
        self.seed_dataset(
            TRACKED,
            self.FAR_FUTURE,
            downloaded_at=NOW - timedelta(days=2),
            suffix="_validated",
        )
        self.seed_validation_report(
            f"{TRACKED}_dataset_validated", total_error=0, suffix="_validated"
        )

        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=NOW)
        self.assertEqual(
            self.criterion_rows(TRACKED)[
                SealCriterionName.COMPLIANT.value
            ].observed_status,
            CriterionStatus.PASS.value,
        )
        self.assertTrue(self.seal_row(TRACKED).has_seal)

        # Published since, and not validated yet.
        later = NOW + timedelta(hours=6)
        self.seed_dataset(
            TRACKED,
            self.FAR_FUTURE,
            downloaded_at=NOW + timedelta(hours=1),
            suffix="_fresh",
        )
        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=later)

        row = self.criterion_rows(TRACKED)[SealCriterionName.COMPLIANT.value]
        self.assertEqual(row.observed_status, CriterionStatus.UNKNOWN.value)
        self.assertEqual(
            row.confirmed_status,
            CriterionStatus.PASS.value,
            "the verdict on the dataset we did validate still stands",
        )
        seal = self.seal_row(TRACKED)
        self.assertEqual(self.derived_seal_status(TRACKED), SealStatus.GRANTED.value)
        self.assertTrue(seal.has_seal)

    def test_compliant_reads_the_latest_report_of_the_latest_dataset(self):
        """Several validator versions run against one dataset; the newest one decides."""
        self.seed_dataset(TRACKED, self.FAR_FUTURE)
        self.seed_availability_check(TRACKED, success=True)
        dataset_id = f"{TRACKED}_dataset"
        self.seed_validation_report(
            dataset_id,
            total_error=9,
            validated_at=NOW - timedelta(days=3),
            suffix="_old",
        )
        self.seed_validation_report(
            dataset_id,
            total_error=0,
            validated_at=NOW - timedelta(hours=1),
            suffix="_new",
        )

        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=NOW)

        row = self.criterion_rows(TRACKED)[SealCriterionName.COMPLIANT.value]
        self.assertEqual(row.observed_status, CriterionStatus.PASS.value)
        self.assertTrue(self.seal_row(TRACKED).has_seal)

    def test_a_feed_new_to_the_database_cannot_hold_the_seal_yet(self):
        """Stable reads the feed's own age, so a freshly added feed fails it."""
        self.set_feed_created_at(TRACKED, NOW - timedelta(days=30))
        self.seed_dataset(TRACKED, self.FAR_FUTURE)

        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=NOW)

        self.assertEqual(
            self.criteria_of()[SealCriterionName.STABLE.value],
            CriterionStatus.FAIL.value,
        )
        self.assertFalse(self.seal_row(TRACKED).has_seal)

    def test_the_seal_arrives_once_the_feed_is_old_enough(self):
        """The same feed, evaluated the day it was added and 181 days later.

        Stable's clock is `feed.created_at`, which does not move when the job runs, so the
        second run is a plain replay at a later `now` rather than something the first run
        had to set up.
        """
        self.set_feed_created_at(TRACKED, NOW)
        self.seed_dataset(TRACKED, NOW + timedelta(days=400))
        self.seed_availability_check(TRACKED, success=True)
        self.seed_validation_report(f"{TRACKED}_dataset", total_error=0)
        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=NOW)
        self.assertFalse(
            self.seal_row(TRACKED).has_seal, "in the database for zero days"
        )

        later = NOW + timedelta(days=181)
        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=later)

        row = self.criterion_rows(TRACKED)[SealCriterionName.STABLE.value]
        self.assertEqual(row.confirmed_status, CriterionStatus.PASS.value)
        self.assertIsNone(row.probation_start, "Stable serves no probation")
        self.assertTrue(self.seal_row(TRACKED).has_seal)

    def test_an_old_feed_qualifies_on_its_very_first_run(self):
        """The point of reading `feed.created_at`: no six-month wait after deployment for a
        feed that has already been in the catalog for years."""
        self.satisfy_everything()

        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=NOW)

        self.assertEqual(
            self.criteria_of()[SealCriterionName.STABLE.value],
            CriterionStatus.PASS.value,
        )
        self.assertTrue(self.seal_row(TRACKED).has_seal)

    def test_an_unstable_producer_url_denies_the_seal_immediately(self):
        """Stable has no grace period, so the flag costs the seal the day it is set."""
        self.satisfy_everything()
        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=NOW)
        self.assertTrue(self.seal_row(TRACKED).has_seal)

        self.set_producer_url_unstable(TRACKED, True)
        later = NOW + timedelta(days=1)
        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=later)

        self.assertEqual(
            self.criteria_of()[SealCriterionName.STABLE.value],
            CriterionStatus.FAIL.value,
        )
        self.assertFalse(self.seal_row(TRACKED).has_seal)

    def test_a_feed_with_no_dataset_leaves_the_seal_unknown(self):
        """UNKNOWN is not a failure - but it is not a pass to be skipped over either."""

        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=NOW)

        row = self.criterion_rows(TRACKED)[SealCriterionName.FRESH_COVERAGE.value]
        self.assertEqual(row.observed_status, CriterionStatus.UNKNOWN.value)
        self.assertEqual(
            row.confirmed_status,
            CriterionStatus.NEVER_EVALUATED.value,
            "no verdict was ever produced, so the criterion is out of service",
        )
        self.assertIsNone(row.last_verdict_at)
        seal = self.seal_row(TRACKED)
        self.assertEqual(
            self.derived_seal_status(TRACKED),
            SealStatus.UNKNOWN.value,
            "Official and Stable pass, but Fresh has never been judged",
        )
        self.assertFalse(seal.has_seal)

    def test_lapsed_coverage_is_confirmed_at_once_on_a_first_evaluation(self):
        """Fresh has a 14-day grace period, but a criterion that has never passed has not
        earned it, so its first verdict lands as a confirmed failure the same day."""
        self.seed_dataset(TRACKED, NOW + timedelta(days=2))

        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=NOW)

        row = self.criterion_rows(TRACKED)[SealCriterionName.FRESH_COVERAGE.value]
        self.assertEqual(row.observed_status, CriterionStatus.FAIL.value)
        self.assertEqual(row.confirmed_status, CriterionStatus.FAIL.value)
        self.assertFalse(self.seal_row(TRACKED).has_seal)

    def test_the_grace_period_absorbs_a_lapse_on_a_feed_that_was_passing(self):
        self.seed_dataset(TRACKED, NOW + timedelta(days=10))
        self.seed_availability_check(TRACKED, success=True)
        self.seed_validation_report(f"{TRACKED}_dataset", total_error=0)
        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=NOW)
        self.assertTrue(self.seal_row(TRACKED).has_seal)

        # Five days on, the same dataset now covers only five more days: inside the horizon.
        within_grace = NOW + timedelta(days=5)
        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=within_grace)

        row = self.criterion_rows(TRACKED)[SealCriterionName.FRESH_COVERAGE.value]
        self.assertEqual(row.observed_status, CriterionStatus.FAIL.value)
        self.assertEqual(
            row.confirmed_status,
            CriterionStatus.PASS.value,
            "the grace period holds the verdict while the producer catches up",
        )
        self.assertEqual(row.first_observed_failure_at, within_grace)
        self.assertTrue(self.seal_row(TRACKED).has_seal)

    def test_a_lapse_outlasting_the_grace_period_costs_the_seal(self):
        self.seed_dataset(TRACKED, NOW + timedelta(days=10))
        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=NOW)
        first_failure = NOW + timedelta(days=5)
        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=first_failure)

        outlasted = first_failure + timedelta(days=15)
        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=outlasted)

        row = self.criterion_rows(TRACKED)[SealCriterionName.FRESH_COVERAGE.value]
        self.assertEqual(row.confirmed_status, CriterionStatus.FAIL.value)
        self.assertEqual(
            row.first_observed_failure_at,
            first_failure,
            "the streak is measured from its start, not from this run",
        )
        self.assertFalse(self.seal_row(TRACKED).has_seal)

    def test_a_seasonal_feed_is_not_denied_by_fresh(self):
        """NOT_APPLICABLE withdraws the criterion instead of failing it, which is the whole
        point of the value: a seasonal feed keeps the seal on the criteria that do apply.
        """
        self.satisfy_everything()
        self.set_seasonal(TRACKED, True)

        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=NOW)

        row = self.criterion_rows(TRACKED)[SealCriterionName.FRESH_COVERAGE.value]
        self.assertEqual(row.observed_status, CriterionStatus.NOT_APPLICABLE.value)
        self.assertEqual(row.confirmed_status, CriterionStatus.NOT_APPLICABLE.value)
        self.assertTrue(self.seal_row(TRACKED).has_seal)

    def test_becoming_seasonal_freezes_a_failing_fresh_rather_than_carrying_it(self):
        """A feed marked seasonal after a confirmed Fresh failure stops being judged on it."""
        self.seed_dataset(TRACKED, NOW - timedelta(days=1))
        self.seed_availability_check(TRACKED, success=True)
        self.seed_validation_report(f"{TRACKED}_dataset", total_error=0)
        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=NOW)
        self.assertFalse(self.seal_row(TRACKED).has_seal)

        self.set_seasonal(TRACKED, True)
        later = NOW + timedelta(days=1)
        update_seals(dry_run=False, stable_feed_ids=[TRACKED], now=later)

        row = self.criterion_rows(TRACKED)[SealCriterionName.FRESH_COVERAGE.value]
        self.assertEqual(row.confirmed_status, CriterionStatus.NOT_APPLICABLE.value)
        self.assertEqual(
            row.last_confirmed_failure_at, NOW, "the failure stays on record"
        )
        self.assertTrue(self.seal_row(TRACKED).has_seal)

    def test_a_run_reports_every_criterion_with_its_reason(self):
        self.seed_dataset(TRACKED, self.FAR_FUTURE)
        report = update_seals(dry_run=True, stable_feed_ids=[TRACKED], now=NOW)

        criteria = report["feeds"][0]["criteria"]
        self.assertEqual(
            [row["criterion"] for row in criteria],
            [evaluator.name.value for evaluator in EVALUATORS],
        )
        for row in criteria:
            with self.subTest(criterion=row["criterion"]):
                self.assertTrue(row["reason"])


class TestCriteriaSelection(SealDbTestCase):
    """The `criteria` filter, against the real registry rather than a patched one."""

    def test_unknown_criterion_raises(self):
        with self.assertRaises(ValueError):
            update_seals(
                stable_feed_ids=[OFFICIAL], criteria=["not_a_criterion"], now=NOW
            )

    def test_criterion_without_an_evaluator_raises(self):
        """`fresh_continuous` is a valid DB enum value but has no evaluator yet (#1782)."""
        with self.assertRaises(ValueError):
            update_seals(
                stable_feed_ids=[OFFICIAL],
                criteria=[SealCriterionName.FRESH_CONTINUOUS.value],
                now=NOW,
            )

    def test_naming_every_implemented_criterion_is_not_a_partial_run(self):
        report = update_seals(
            dry_run=True,
            stable_feed_ids=[OFFICIAL],
            criteria=[evaluator.name.value for evaluator in EVALUATORS],
            now=NOW,
        )
        self.assertFalse(report["partial_run"])

    def test_naming_a_subset_is_a_partial_run(self):
        """More than one criterion is implemented now, so a subset is genuinely partial."""
        report = update_seals(
            dry_run=True,
            stable_feed_ids=[OFFICIAL],
            criteria=[SealCriterionName.OFFICIAL.value],
            now=NOW,
        )
        self.assertTrue(report["partial_run"])
        self.assertIn("note", report)


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
    BLIP_AT = datetime(
        2026, 6, 18, 12, 0, tzinfo=timezone.utc
    )  # one day into probation
    RESTARTED_FROM = datetime(2026, 6, 19, 0, 0, tzinfo=timezone.utc)

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
        self.assertEqual(row.observed_status, CriterionStatus.FAIL.value)
        self.assertEqual(
            row.confirmed_status,
            CriterionStatus.PASS.value,
            "still inside its grace period",
        )
        self.assertIsNone(row.probation_start)

    def test_probation_starts_on_the_day_of_repair(self):
        self.run_at(NOW)
        self.set_official(OFFICIAL, False)
        self.run_at(self.STREAK_STARTS)
        self.run_at(self.CONFIRMED_AT)

        row = self.stand_in()
        self.assertEqual(
            row.confirmed_status,
            CriterionStatus.FAIL.value,
            "the streak outlasted the grace period",
        )
        self.assertEqual(row.probation_start, self.PROBATION_FROM)

    def test_probation_withholds_the_seal_while_every_criterion_passes(self):
        self.run_at(NOW)
        self.set_official(OFFICIAL, False)
        self.run_at(self.STREAK_STARTS)
        self.run_at(self.CONFIRMED_AT)
        self.set_official(OFFICIAL, True)
        self.run_at(self.REPAIRED_AT)

        rows = self.criterion_rows(OFFICIAL)
        self.assertEqual(
            rows[SealCriterionName.OFFICIAL.value].confirmed_status,
            CriterionStatus.PASS.value,
        )
        self.assertEqual(
            rows[SealCriterionName.AVAILABLE.value].confirmed_status,
            CriterionStatus.PASS.value,
        )
        self.assertEqual(
            rows[SealCriterionName.AVAILABLE.value].probation_start,
            self.PROBATION_FROM,
            "recovery clears the status but starts probation",
        )
        self.assertFalse(
            self.seal_row(OFFICIAL).has_seal,
            "both criteria pass, so only the open probation can be withholding it",
        )

    def test_a_failure_during_probation_is_not_absorbed_by_the_grace_period(self):
        """Probation suspends the grace period, persisted and reloaded through the DB.

        The stand-in has a 14-day grace period, so off probation this single failing day
        would leave `confirmed_status` at pass. Serving probation, it is confirmed at once
        and the probation count restarts.
        """
        self.run_at(NOW)
        self.set_official(OFFICIAL, False)
        self.run_at(self.STREAK_STARTS)
        self.run_at(self.CONFIRMED_AT)
        self.set_official(OFFICIAL, True)
        self.run_at(self.REPAIRED_AT)
        self.assertEqual(self.stand_in().probation_start, self.PROBATION_FROM)

        self.set_official(OFFICIAL, False)
        self.run_at(self.BLIP_AT)

        row = self.stand_in()
        self.assertEqual(
            row.confirmed_status,
            CriterionStatus.FAIL.value,
            "the grace period is forfeited while on probation",
        )
        self.assertEqual(row.last_confirmed_failure_at, self.BLIP_AT)
        self.assertEqual(
            row.probation_start, self.RESTARTED_FROM, "and the count goes back to zero"
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
        self.assertEqual(row.confirmed_status, CriterionStatus.PASS.value)
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
        self.assertEqual(row.observed_status, CriterionStatus.FAIL.value)
        self.assertEqual(
            row.confirmed_status,
            CriterionStatus.FAIL.value,
            "a confirmed failure on its very first verdict",
        )
        self.assertEqual(row.first_observed_failure_at, self.LATER)
        self.assertEqual(row.last_confirmed_failure_at, self.LATER)

        seal = self.seal_row(OFFICIAL)
        self.assertFalse(seal.has_seal)
        self.assertEqual(seal.seal_lost_at, self.LATER)


@patch("tasks.seal_of_reliability.seal_updater.EVALUATORS", GOES_DARK)
class TestCriterionThatStopsBeingEvaluable(SealDbTestCase):
    """A criterion that produced a verdict once and then loses its input.

    The roll-up reads `confirmed_status`, and skips criteria whose value there is not a
    verdict. An UNKNOWN run writes `observed_status` but deliberately leaves
    `confirmed_status` alone, which is what keeps such a criterion in the roll-up with the
    verdict it already had — the safety of the skip rule rests on that.
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

        # Official recovers, but the stand-in has lost its input. Its stored confirmed
        # failure must stand and keep withholding the seal.
        self.set_official(OFFICIAL, True)
        self.run_at(DARK_FROM)

        rows = self.criterion_rows(OFFICIAL)
        self.assertEqual(
            rows[SealCriterionName.OFFICIAL.value].confirmed_status,
            CriterionStatus.PASS.value,
            "the only other criterion is passing again",
        )
        frozen = rows[SealCriterionName.COMPLIANT.value]
        self.assertEqual(
            frozen.observed_status,
            CriterionStatus.UNKNOWN.value,
            "we could not look this run, and that is recorded",
        )
        self.assertEqual(
            frozen.confirmed_status,
            CriterionStatus.FAIL.value,
            "but the last verdict still stands",
        )
        self.assertFalse(
            self.seal_row(OFFICIAL).has_seal,
            "going dark must not hand the seal back",
        )

    def test_going_dark_records_the_attempt_without_moving_the_verdict(self):
        """`evaluated_at` advances, `last_verdict_at` does not.

        The gap between them is how long the criterion has been unable to answer, which is
        the whole reason the two are separate columns.
        """
        self.run_at(NOW)
        self.set_official(OFFICIAL, False)
        self.run_at(self.FAILED_AT)
        self.run_at(DARK_FROM)

        frozen = self.stand_in()
        self.assertEqual(frozen.evaluated_at, DARK_FROM, "we did try again")
        self.assertEqual(
            frozen.last_verdict_at, self.FAILED_AT, "but got no new verdict"
        )

    def test_going_dark_before_any_verdict_leaves_the_seal_unknown(self):
        """The other half: with no verdict ever, there is nothing to hold in service.

        A row is written, because the attempt is worth recording, but `confirmed_status`
        stays NEVER_EVALUATED - and a criterion that has never been judged cannot be skipped
        over, so the seal is UNKNOWN rather than granted on the strength of the others.
        """
        self.run_at(DARK_FROM)

        row = self.stand_in()
        self.assertIsNotNone(row, "the attempt is recorded")
        self.assertEqual(row.observed_status, CriterionStatus.UNKNOWN.value)
        self.assertEqual(
            row.confirmed_status,
            CriterionStatus.NEVER_EVALUATED.value,
            "no verdict has ever been produced",
        )
        self.assertIsNone(row.last_verdict_at)
        seal = self.seal_row(OFFICIAL)
        self.assertEqual(self.derived_seal_status(OFFICIAL), SealStatus.UNKNOWN.value)
        self.assertFalse(
            seal.has_seal, "unknown is not a grant, and not a denial either"
        )


@patch("tasks.seal_of_reliability.seal_updater.EVALUATORS", STOPS_APPLYING)
class TestCriterionThatStopsApplying(SealDbTestCase):
    """The contrast with going dark, and the reason UNKNOWN and NOT_APPLICABLE are separate.

    Both withhold a verdict, and they go in opposite directions. A criterion we could not
    look at keeps denying the seal with the verdict it already had; one that does not apply
    to the feed stops counting altogether and cannot deny anything.
    """

    FAILED_AT = NOW + timedelta(days=1)

    def stand_in(self):
        return self.criterion_rows(OFFICIAL).get(
            SealCriterionName.FRESH_CONTINUOUS.value
        )

    def run_at(self, moment):
        update_seals(dry_run=False, stable_feed_ids=[OFFICIAL], now=moment)

    def test_becoming_not_applicable_hands_the_seal_back(self):
        # Both criteria fail, so the seal goes.
        self.run_at(NOW)
        self.set_official(OFFICIAL, False)
        self.run_at(self.FAILED_AT)
        self.assertFalse(self.seal_row(OFFICIAL).has_seal)

        # Official recovers, and the stand-in stops applying to this feed. Unlike going
        # dark, it withdraws rather than keeping its failure on the books.
        self.set_official(OFFICIAL, True)
        self.run_at(EXCLUDED_FROM)

        row = self.stand_in()
        self.assertEqual(row.observed_status, CriterionStatus.NOT_APPLICABLE.value)
        self.assertEqual(
            row.confirmed_status,
            CriterionStatus.NOT_APPLICABLE.value,
            "the confirmed status is overwritten, which is what withdraws it",
        )
        self.assertTrue(
            self.seal_row(OFFICIAL).has_seal,
            "a criterion that does not apply cannot deny the seal",
        )

    def test_withdrawing_freezes_the_penalty_rather_than_clearing_it(self):
        """Its probation is left in place in case the criterion applies again later."""
        self.run_at(NOW)
        self.set_official(OFFICIAL, False)
        self.run_at(self.FAILED_AT)
        self.set_official(OFFICIAL, True)
        self.run_at(EXCLUDED_FROM)

        row = self.stand_in()
        self.assertIsNotNone(
            row.probation_start, "the penalty is still recorded on the row"
        )
        self.assertTrue(
            self.seal_row(OFFICIAL).has_seal,
            "but it cannot withhold the seal while the criterion is out of service",
        )

    def test_withdrawing_does_not_move_the_last_verdict(self):
        self.run_at(NOW)
        self.set_official(OFFICIAL, False)
        self.run_at(self.FAILED_AT)
        self.run_at(EXCLUDED_FROM)

        row = self.stand_in()
        self.assertEqual(row.evaluated_at, EXCLUDED_FROM, "we did run the check")
        self.assertEqual(
            row.last_verdict_at, self.FAILED_AT, "but it produced no verdict"
        )

    def test_the_report_counts_it_separately_from_unknown(self):
        report = update_seals(
            dry_run=True, stable_feed_ids=[OFFICIAL], now=EXCLUDED_FROM
        )
        self.assertEqual(report["not_applicable"], 1)
        self.assertEqual(report["unknown"], 0)


if __name__ == "__main__":
    unittest.main()
