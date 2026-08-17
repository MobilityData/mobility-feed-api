import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from shared.common.seal_criteria import PROBATION_PERIOD, SealCriterionName
from shared.database_gen.sqlacodegen_models import Sealcriterion
from shared.db_models.feed_reliability_report_impl import FeedReliabilityReportImpl
from shared.db_models.reliability_criterion_impl import STATUS_FAIL, STATUS_NOT_EVALUATED, STATUS_PASS

NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=timezone.utc)


def make_criterion_row(criterion, **overrides):
    values = {
        "feed_id": "feed_id",
        "criterion": criterion.value,
        "observed_pass": True,
        "confirmed_pass": True,
        "evaluated_at": NOW,
        "first_observed_failure_at": None,
        "last_observed_failure_at": None,
        "last_confirmed_failure_at": None,
        "probation_start": None,
    }
    values.update(overrides)
    return Sealcriterion(**values)


def make_seal_row(**overrides):
    values = {
        "has_seal": True,
        "seal_earned_at": NOW - timedelta(days=200),
        "seal_lost_at": None,
        "seal_evaluated_at": NOW,
        "seal_latest_probation_start": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def by_criterion(report):
    return {criterion.criterion: criterion for criterion in report.criteria}


class TestFeedReliabilityReportImpl(unittest.TestCase):
    """Test the `FeedReliabilityReportImpl` model."""

    def test_never_evaluated_feed(self):
        """A feed the nightly job has not reached still gets a full report, not an error."""
        report = FeedReliabilityReportImpl.from_orm("mdb-1", None, [], NOW)

        assert report.feed_id == "mdb-1"
        assert report.has_seal is False
        assert report.earned_at is None
        assert report.evaluated_at is None
        assert report.on_probation is False
        assert len(report.criteria) == 6
        assert all(criterion.status == STATUS_NOT_EVALUATED for criterion in report.criteria)

    def test_all_six_criteria_always_returned_in_order(self):
        """Criteria with no row are filled in, so a client can render six cards unconditionally."""
        rows = [make_criterion_row(SealCriterionName.OFFICIAL)]
        report = FeedReliabilityReportImpl.from_orm("mdb-1", make_seal_row(), rows, NOW)

        assert [criterion.criterion for criterion in report.criteria] == [name.value for name in SealCriterionName]
        criteria = by_criterion(report)
        assert criteria["official"].status == STATUS_PASS
        assert criteria["compliant"].status == STATUS_NOT_EVALUATED

    def test_mixed_criteria(self):
        """The report carries each criterion's own verdict alongside the stored seal outcome."""
        rows = [
            make_criterion_row(SealCriterionName.OFFICIAL),
            make_criterion_row(
                SealCriterionName.AVAILABLE,
                observed_pass=False,
                confirmed_pass=False,
                first_observed_failure_at=NOW - timedelta(days=60),
                last_observed_failure_at=NOW,
            ),
            make_criterion_row(
                SealCriterionName.COMPLIANT,
                observed_pass=False,
                confirmed_pass=True,
                first_observed_failure_at=NOW - timedelta(days=5),
                last_observed_failure_at=NOW,
            ),
        ]
        report = FeedReliabilityReportImpl.from_orm(
            "mdb-1", make_seal_row(has_seal=False, seal_lost_at=NOW - timedelta(days=45)), rows, NOW
        )

        criteria = by_criterion(report)
        assert report.has_seal is False
        assert criteria["official"].status == STATUS_PASS
        assert criteria["available"].status == STATUS_FAIL
        assert criteria["available"].in_grace_period is False
        assert criteria["compliant"].status == STATUS_FAIL
        assert criteria["compliant"].in_grace_period is True

    def test_probation_rolled_up_from_criteria(self):
        """The feed-level probation is the latest of its criteria's, so the two cannot disagree."""
        earlier = NOW - timedelta(days=40)
        later = NOW - timedelta(days=10)
        rows = [
            make_criterion_row(SealCriterionName.AVAILABLE, probation_start=earlier),
            make_criterion_row(SealCriterionName.COMPLIANT, probation_start=later),
        ]
        report = FeedReliabilityReportImpl.from_orm("mdb-1", make_seal_row(has_seal=False), rows, NOW)

        assert report.on_probation is True
        assert report.probation_ends_at == later + PROBATION_PERIOD

    def test_probation_ignored_for_exempt_criteria(self):
        """A stray probation_start on `official` does not put the feed on probation."""
        rows = [make_criterion_row(SealCriterionName.OFFICIAL, probation_start=NOW - timedelta(days=1))]
        report = FeedReliabilityReportImpl.from_orm("mdb-1", make_seal_row(), rows, NOW)

        assert report.on_probation is False
        assert report.probation_ends_at is None

    def test_unknown_criterion_is_skipped(self):
        """A criterion the DB has but this build does not know about degrades to not evaluated."""
        rows = [make_criterion_row(SealCriterionName.OFFICIAL)]
        rows[0].criterion = "some_future_criterion"
        report = FeedReliabilityReportImpl.from_orm("mdb-1", make_seal_row(), rows, NOW)

        assert len(report.criteria) == 6
        assert all(criterion.status == STATUS_NOT_EVALUATED for criterion in report.criteria)
