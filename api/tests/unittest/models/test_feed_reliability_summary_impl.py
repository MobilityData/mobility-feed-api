import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from shared.common.seal_criteria import PROBATION_PERIOD
from shared.db_models.feed_reliability_summary_impl import FeedReliabilitySummaryImpl

NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=timezone.utc)


def make_seal_row(**overrides):
    """A seal roll-up row, shaped like both `get_reliability_seals` and the `feedsearch` view."""
    values = {
        "has_seal": True,
        "seal_earned_at": NOW - timedelta(days=200),
        "seal_lost_at": None,
        "seal_evaluated_at": NOW,
        "seal_latest_probation_start": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class TestFeedReliabilitySummaryImpl(unittest.TestCase):
    """Test the `FeedReliabilitySummaryImpl` model."""

    def test_no_row_returns_none(self):
        """A feed with no seal row has never been evaluated, so there is no badge to render."""
        assert FeedReliabilitySummaryImpl.from_orm(None, NOW) is None

    def test_row_without_seal_value_returns_none(self):
        """A search row for a feed with no seal row has NULL in every seal column."""
        row = make_seal_row(has_seal=None, seal_earned_at=None, seal_evaluated_at=None)

        assert FeedReliabilitySummaryImpl.from_orm(row, NOW) is None

    def test_feed_holding_the_seal(self):
        """A feed with the seal and no probation."""
        row = make_seal_row()
        result = FeedReliabilitySummaryImpl.from_orm(row, NOW)

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
        result = FeedReliabilitySummaryImpl.from_orm(row, NOW)

        assert result.has_seal is False
        assert result.lost_at == row.seal_lost_at
        assert result.on_probation is True
        assert result.probation_ends_at == probation_start + PROBATION_PERIOD

    def test_elapsed_probation_reports_no_end_date(self):
        """A probation the nightly job should have cleared serves no stale countdown."""
        row = make_seal_row(has_seal=False, seal_latest_probation_start=NOW - PROBATION_PERIOD - timedelta(days=1))
        result = FeedReliabilitySummaryImpl.from_orm(row, NOW)

        assert result.on_probation is True
        assert result.probation_ends_at is None
