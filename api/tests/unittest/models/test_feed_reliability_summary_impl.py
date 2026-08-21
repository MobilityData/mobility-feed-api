import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from shared.common.seal_criteria import PROBATION_PERIOD, SealCriterionName
from shared.database_gen.sqlacodegen_models import FeedReliabilitySeal, SealCriterion
from shared.db_models.feed_reliability_summary_impl import FeedReliabilitySummaryImpl

NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=timezone.utc)


def make_seal_row(**overrides):
    """A seal roll-up row shaped like a `feedsearch` view row (the `from_orm_search_row` path)."""
    values = {
        "has_seal": True,
        "seal_earned_at": NOW - timedelta(days=200),
        "seal_lost_at": None,
        "seal_evaluated_at": NOW,
        "seal_latest_probation_start": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def make_criterion(criterion, **overrides):
    values = {
        "feed_id": "feed_id",
        "criterion": criterion.value,
        "observed_status": "pass",
        "confirmed_status": "pass",
        "evaluated_at": NOW,
        "first_observed_failure_at": None,
        "last_observed_failure_at": None,
        "last_confirmed_failure_at": None,
        "probation_start": None,
    }
    values.update(overrides)
    return SealCriterion(**values)


def make_feed(has_seal=True, seal_lost_at=None, criteria=None):
    """A feed carrying its eager-loaded seal relationships (the `from_orm` path)."""
    return SimpleNamespace(
        feed_reliability_seal=FeedReliabilitySeal(
            feed_id="feed_id",
            has_seal=has_seal,
            seal_earned_at=NOW - timedelta(days=200),
            seal_lost_at=seal_lost_at,
        ),
        seal_criteria=criteria if criteria is not None else [make_criterion(SealCriterionName.OFFICIAL)],
    )


class TestFeedReliabilitySummaryFromOrmSearchRow(unittest.TestCase):
    """Test `FeedReliabilitySummaryImpl.from_orm_search_row` - the `feedsearch` view-row path."""

    def test_no_row_returns_none(self):
        """A feed with no seal row has never been evaluated, so there is no badge to render."""
        assert FeedReliabilitySummaryImpl.from_orm_search_row(None, NOW) is None

    def test_row_without_seal_value_returns_none(self):
        """A search row for a feed with no seal row has NULL in every seal column."""
        row = make_seal_row(has_seal=None, seal_earned_at=None, seal_evaluated_at=None)

        assert FeedReliabilitySummaryImpl.from_orm_search_row(row, NOW) is None

    def test_feed_holding_the_seal(self):
        """A feed with the seal and no probation."""
        row = make_seal_row()
        result = FeedReliabilitySummaryImpl.from_orm_search_row(row, NOW)

        assert result.has_seal is True
        assert result.earned_at == row.seal_earned_at
        assert result.lost_at is None
        assert result.evaluated_at == NOW
        assert result.on_probation is False
        assert result.probation_ends_at is None

    def test_feed_serving_probation(self):
        """A feed that lost the seal reports when it could earn it back."""
        probation_start = NOW - timedelta(days=20)
        row = make_seal_row(
            has_seal=False,
            seal_lost_at=NOW - timedelta(days=25),
            seal_latest_probation_start=probation_start,
        )
        result = FeedReliabilitySummaryImpl.from_orm_search_row(row, NOW)

        assert result.has_seal is False
        assert result.lost_at == row.seal_lost_at
        assert result.on_probation is True
        assert result.probation_ends_at == probation_start + PROBATION_PERIOD

    def test_elapsed_probation_reports_no_end_date(self):
        """A probation the nightly job should have cleared serves no stale countdown."""
        row = make_seal_row(has_seal=False, seal_latest_probation_start=NOW - PROBATION_PERIOD - timedelta(days=1))
        result = FeedReliabilitySummaryImpl.from_orm_search_row(row, NOW)

        assert result.on_probation is True
        assert result.probation_ends_at is None


class TestFeedReliabilitySummaryFromOrm(unittest.TestCase):
    """Test `FeedReliabilitySummaryImpl.from_orm` - the ORM-relationship path (detail / list)."""

    def test_no_seal_row_returns_none(self):
        """A feed whose `feed_reliability_seal` relationship is empty has never been evaluated."""
        feed = SimpleNamespace(feed_reliability_seal=None, seal_criteria=[])
        assert FeedReliabilitySummaryImpl.from_orm(feed, NOW) is None

    def test_evaluated_at_is_latest_across_criteria(self):
        """`evaluated_at` rolls up to the most recent criterion evaluation, not the seal row."""
        feed = make_feed(
            criteria=[
                make_criterion(SealCriterionName.OFFICIAL, evaluated_at=NOW - timedelta(days=3)),
                make_criterion(SealCriterionName.AVAILABLE, evaluated_at=NOW),
            ]
        )
        result = FeedReliabilitySummaryImpl.from_orm(feed, NOW)

        assert result.has_seal is True
        assert result.evaluated_at == NOW
        assert result.on_probation is False

    def test_probation_rolls_up_over_non_exempt_criteria(self):
        """Probation is the latest `probation_start` among the criteria that serve it."""
        earlier = NOW - timedelta(days=40)
        later = NOW - timedelta(days=10)
        feed = make_feed(
            has_seal=False,
            criteria=[
                make_criterion(SealCriterionName.AVAILABLE, probation_start=earlier),
                make_criterion(SealCriterionName.COMPLIANT, probation_start=later),
            ],
        )
        result = FeedReliabilitySummaryImpl.from_orm(feed, NOW)

        assert result.on_probation is True
        assert result.probation_ends_at == later + PROBATION_PERIOD

    def test_probation_ignored_for_exempt_criteria(self):
        """A stray `probation_start` on `official` never rolls up into the feed's probation."""
        feed = make_feed(criteria=[make_criterion(SealCriterionName.OFFICIAL, probation_start=NOW - timedelta(days=1))])
        result = FeedReliabilitySummaryImpl.from_orm(feed, NOW)

        assert result.on_probation is False
        assert result.probation_ends_at is None
