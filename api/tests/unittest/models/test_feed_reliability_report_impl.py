import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from shared.common.error_handling import InternalHTTPException
from shared.common.seal_criteria import PROBATION_PERIOD, SealCriterionName
from shared.database_gen.sqlacodegen_models import FeedReliabilitySeal, SealCriterion
from shared.db_models.feed_reliability_report_impl import FeedReliabilityReportImpl
from shared.db_models.reliability_criterion_impl import STATUS_FAIL, STATUS_NEVER_EVALUATED, STATUS_PASS

# Anchored to the real clock because the countdowns are derived against `datetime.now`. Every window
# below is at least a day clear of its boundary, so the assertions do not race the wall clock.
NOW = datetime.now(timezone.utc)


def make_criterion_row(criterion, **overrides):
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


def make_seal(**overrides):
    """A `feed_reliability_seal` ORM row - the report reads only the stored outcome from it and
    rolls `evaluated_at` up from the criteria itself."""
    values = {
        "feed_id": "feed_id",
        "has_seal": True,
        "seal_earned_at": NOW - timedelta(days=200),
        "seal_lost_at": None,
    }
    values.update(overrides)
    return FeedReliabilitySeal(**values)


def make_feed(stable_id="mdb-1", seal=None, criteria=()):
    """A feed carrying its eager-loaded seal relationships."""
    return SimpleNamespace(stable_id=stable_id, feed_reliability_seal=seal, seal_criteria=list(criteria))


def by_criterion(report):
    return {criterion.criterion: criterion for criterion in report.criteria}


class TestFeedReliabilityReportImpl(unittest.TestCase):
    """Test the `FeedReliabilityReportImpl` model."""

    def test_no_feed_returns_none(self):
        """There is nothing to convert without a feed."""
        assert FeedReliabilityReportImpl.from_orm(None) is None

    def test_never_evaluated_feed(self):
        """A feed the nightly job has not reached still gets a full report, not an error."""
        report = FeedReliabilityReportImpl.from_orm(make_feed())

        assert report.feed_id == "mdb-1"
        assert report.has_seal is False
        assert report.earned_at is None
        assert report.evaluated_at is None
        assert report.on_probation is False
        assert len(report.criteria) == 6
        assert all(criterion.status == STATUS_NEVER_EVALUATED for criterion in report.criteria)

    def test_all_six_criteria_always_returned_in_order(self):
        """Criteria with no row are filled in, so a client can render six cards unconditionally."""
        feed = make_feed(seal=make_seal(), criteria=[make_criterion_row(SealCriterionName.OFFICIAL)])
        report = FeedReliabilityReportImpl.from_orm(feed)

        assert [criterion.criterion for criterion in report.criteria] == [name.value for name in SealCriterionName]
        criteria = by_criterion(report)
        assert criteria["official"].status == STATUS_PASS
        assert criteria["compliant"].status == STATUS_NEVER_EVALUATED

    def test_mixed_criteria(self):
        """The report carries each criterion's own verdict alongside the stored seal outcome."""
        feed = make_feed(
            seal=make_seal(has_seal=False, seal_lost_at=NOW - timedelta(days=45)),
            criteria=[
                make_criterion_row(SealCriterionName.OFFICIAL),
                make_criterion_row(
                    SealCriterionName.AVAILABLE,
                    observed_status="fail",
                    confirmed_status="fail",
                    first_observed_failure_at=NOW - timedelta(days=60),
                    last_observed_failure_at=NOW,
                ),
                make_criterion_row(
                    SealCriterionName.COMPLIANT,
                    observed_status="fail",
                    confirmed_status="pass",
                    first_observed_failure_at=NOW - timedelta(days=5),
                    last_observed_failure_at=NOW,
                ),
            ],
        )
        report = FeedReliabilityReportImpl.from_orm(feed)

        criteria = by_criterion(report)
        assert report.has_seal is False
        assert criteria["official"].status == STATUS_PASS
        assert criteria["available"].status == STATUS_FAIL
        assert criteria["available"].in_grace_period is False
        assert criteria["compliant"].status == STATUS_FAIL
        assert criteria["compliant"].in_grace_period is True

    def test_evaluated_at_is_latest_across_criteria(self):
        """`evaluated_at` rolls up to the most recent criterion evaluation."""
        feed = make_feed(
            seal=make_seal(),
            criteria=[
                make_criterion_row(SealCriterionName.OFFICIAL, evaluated_at=NOW - timedelta(days=3)),
                make_criterion_row(SealCriterionName.AVAILABLE, evaluated_at=NOW),
            ],
        )
        report = FeedReliabilityReportImpl.from_orm(feed)

        assert report.evaluated_at == NOW

    def test_probation_rolled_up_from_criteria(self):
        """The feed-level probation is the latest of its criteria's, so the two cannot disagree."""
        earlier = NOW - timedelta(days=40)
        later = NOW - timedelta(days=10)
        feed = make_feed(
            seal=make_seal(has_seal=False),
            criteria=[
                make_criterion_row(SealCriterionName.AVAILABLE, probation_start=earlier),
                make_criterion_row(SealCriterionName.COMPLIANT, probation_start=later),
            ],
        )
        report = FeedReliabilityReportImpl.from_orm(feed)

        assert report.on_probation is True
        assert report.probation_ends_at == later + PROBATION_PERIOD

    def test_probation_ignored_for_exempt_criteria(self):
        """A stray probation_start on `official` does not put the feed on probation."""
        feed = make_feed(
            seal=make_seal(),
            criteria=[make_criterion_row(SealCriterionName.OFFICIAL, probation_start=NOW - timedelta(days=1))],
        )
        report = FeedReliabilityReportImpl.from_orm(feed)

        assert report.on_probation is False
        assert report.probation_ends_at is None

    def test_unknown_criterion_raises(self):
        """A criterion the DB has but this build does not know about fails the report.

        Serving five of six criteria would hide a seal_criterion_name/SealCriterionName mismatch,
        so the report errors instead and the mismatch gets fixed.
        """
        row = make_criterion_row(SealCriterionName.OFFICIAL)
        row.criterion = "some_future_criterion"

        with self.assertRaises(InternalHTTPException) as context:
            FeedReliabilityReportImpl.from_orm(make_feed(seal=make_seal(), criteria=[row]))

        assert context.exception.status_code == 500
        assert "some_future_criterion" in context.exception.detail
