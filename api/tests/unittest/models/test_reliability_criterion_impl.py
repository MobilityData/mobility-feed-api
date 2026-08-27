import unittest
from datetime import datetime, timedelta, timezone

from shared.common.error_handling import InternalHTTPException
from shared.common.seal_criteria import (
    GRACE_PERIODS,
    PROBATION_PERIOD,
    CriterionStatus,
    SealCriterionName,
)
from shared.database_gen.sqlacodegen_models import SealCriterion
from shared.db_models.reliability_criterion_impl import ReliabilityCriterionImpl

# Anchored to the real clock because the countdowns are derived against `datetime.now`. Every window
# below is at least a day clear of its boundary, so the assertions do not race the wall clock.
NOW = datetime.now(timezone.utc)


def make_row(criterion=SealCriterionName.COMPLIANT, **overrides):
    """A `seal_criterion` row that passes, unless overridden."""
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


class TestReliabilityCriterionImpl(unittest.TestCase):
    """Test the `ReliabilityCriterionImpl` model."""

    def test_passing_criterion(self):
        """A criterion whose check passed reports `pass`, with neither window open."""
        result = ReliabilityCriterionImpl.from_orm(make_row())

        assert result.criterion == "compliant"
        assert result.status == CriterionStatus.PASS.value
        assert result.in_grace_period is False
        assert result.grace_period_ends_at is None
        assert result.on_probation is False
        assert result.probation_ends_at is None
        assert result.evaluated_at == NOW

    def test_no_row_returns_none(self):
        """There is nothing to convert without a row - the report fills the gap instead."""
        assert ReliabilityCriterionImpl.from_orm(None) is None

    def test_unknown_criterion_raises(self):
        """A criterion this build does not know about is a schema/code mismatch, not a skip.

        Dropping it would serve an incomplete report and hide the incompatibility.
        """
        row = make_row()
        row.criterion = "some_future_criterion"

        with self.assertRaises(InternalHTTPException) as context:
            ReliabilityCriterionImpl.from_orm(row)

        assert context.exception.status_code == 500
        assert "some_future_criterion" in context.exception.detail

    def test_never_evaluated_factory(self):
        """`never_evaluated` is the entry for a criterion with no row at all."""
        result = ReliabilityCriterionImpl.never_evaluated(SealCriterionName.AVAILABLE)

        assert result.criterion == "available"
        assert result.status == CriterionStatus.NEVER_EVALUATED.value
        assert result.in_grace_period is False
        assert result.on_probation is False

    def test_never_evaluated_status_passes_through(self):
        """A stored `never_evaluated` is served as-is, with no windows."""
        row = make_row(observed_status="never_evaluated", confirmed_status="never_evaluated")
        result = ReliabilityCriterionImpl.from_orm(row)

        assert result.status == CriterionStatus.NEVER_EVALUATED.value
        assert result.in_grace_period is False
        assert result.on_probation is False

    def test_unknown_status_passes_through(self):
        """`unknown` (inputs missing this evaluation) is reported as its own status, not a failure."""
        row = make_row(criterion=SealCriterionName.AVAILABLE, observed_status="unknown", confirmed_status="pass")
        result = ReliabilityCriterionImpl.from_orm(row)

        assert result.status == CriterionStatus.UNKNOWN.value
        assert result.in_grace_period is False

    def test_not_applicable_status_is_withdrawn(self):
        """`not_applicable` withdraws the criterion: flat status, no windows, no probation.

        Even a stored probation_start is ignored - the criterion does not participate at all.
        """
        row = make_row(
            criterion=SealCriterionName.FRESH_COVERAGE,
            observed_status="not_applicable",
            confirmed_status="not_applicable",
            probation_start=NOW - timedelta(days=1),
        )
        result = ReliabilityCriterionImpl.from_orm(row)

        assert result.status == CriterionStatus.NOT_APPLICABLE.value
        assert result.in_grace_period is False
        assert result.on_probation is False
        assert result.probation_ends_at is None

    def test_failing_inside_grace_period(self):
        """A failure the grace period is still holding reports `fail` with `in_grace_period`.

        The seal is not withdrawn yet, and the countdown says when it would be.
        """
        first_failure = NOW - timedelta(days=10)
        row = make_row(
            observed_status="fail",
            confirmed_status="pass",
            first_observed_failure_at=first_failure,
            last_observed_failure_at=NOW,
        )
        result = ReliabilityCriterionImpl.from_orm(row)

        assert result.status == CriterionStatus.FAIL.value
        assert result.in_grace_period is True
        assert result.grace_period_ends_at == first_failure + GRACE_PERIODS[SealCriterionName.COMPLIANT]
        assert result.first_failure_at == first_failure
        assert result.last_failure_at == NOW

    def test_grace_exempt_criterion_is_never_in_grace(self):
        """A criterion with no grace period reports the failure straight away.

        `fresh_continuous` has no grace period, so even a row whose `confirmed_status` still reads
        `pass` must not be served as being under grace - there would be no end date to report.
        """
        row = make_row(
            criterion=SealCriterionName.FRESH_CONTINUOUS,
            observed_status="fail",
            confirmed_status="pass",
            first_observed_failure_at=NOW - timedelta(days=1),
            last_observed_failure_at=NOW,
        )
        result = ReliabilityCriterionImpl.from_orm(row)

        assert result.status == CriterionStatus.FAIL.value
        assert result.in_grace_period is False
        assert result.grace_period_ends_at is None

    def test_failing_beyond_grace_period(self):
        """Once the failure is confirmed, the criterion reports `fail` with no grace left."""
        row = make_row(
            observed_status="fail",
            confirmed_status="fail",
            first_observed_failure_at=NOW - timedelta(days=40),
            last_observed_failure_at=NOW,
            last_confirmed_failure_at=NOW,
        )
        result = ReliabilityCriterionImpl.from_orm(row)

        assert result.status == CriterionStatus.FAIL.value
        assert result.in_grace_period is False
        assert result.grace_period_ends_at is None

    def test_passing_while_on_probation(self):
        """A criterion can pass its check and still not count towards the seal.

        This is the case the probation fields exist for: every criterion green, no seal.
        """
        probation_start = NOW - timedelta(days=30)
        row = make_row(criterion=SealCriterionName.AVAILABLE, probation_start=probation_start)
        result = ReliabilityCriterionImpl.from_orm(row)

        assert result.status == CriterionStatus.PASS.value
        assert result.on_probation is True
        assert result.probation_ends_at == probation_start + PROBATION_PERIOD

    def test_grace_does_not_apply_during_probation(self):
        """A failure during probation restarts probation, so grace has nothing to protect."""
        row = make_row(
            criterion=SealCriterionName.AVAILABLE,
            observed_status="fail",
            confirmed_status="pass",
            first_observed_failure_at=NOW - timedelta(days=2),
            last_observed_failure_at=NOW,
            probation_start=NOW - timedelta(days=1),
        )
        result = ReliabilityCriterionImpl.from_orm(row)

        assert result.status == CriterionStatus.FAIL.value
        assert result.on_probation is True
        assert result.in_grace_period is False
        assert result.grace_period_ends_at is None

    def test_official_and_stable_serve_no_probation(self):
        """`official` and `stable` are exempt, even if a probation_start is somehow stored."""
        for criterion in (SealCriterionName.OFFICIAL, SealCriterionName.STABLE):
            with self.subTest(criterion=criterion):
                row = make_row(criterion=criterion, probation_start=NOW - timedelta(days=1))
                result = ReliabilityCriterionImpl.from_orm(row)

                assert result.on_probation is False
                assert result.probation_ends_at is None

    def test_official_and_stable_have_no_grace_period(self):
        """Exempt criteria expose no grace countdown either - their failures are immediate."""
        for criterion in (SealCriterionName.OFFICIAL, SealCriterionName.STABLE):
            with self.subTest(criterion=criterion):
                row = make_row(
                    criterion=criterion,
                    observed_status="fail",
                    confirmed_status="fail",
                    first_observed_failure_at=NOW - timedelta(days=1),
                )
                result = ReliabilityCriterionImpl.from_orm(row)

                assert result.status == CriterionStatus.FAIL.value
                assert result.in_grace_period is False
                assert result.grace_period_ends_at is None

    def test_elapsed_probation_reports_no_end_date(self):
        """A probation that should already have been cleared serves no countdown.

        `on_probation` stays true because that stored state is what produced `has_seal`; the null
        end date is the signal that the nightly job has not caught up.
        """
        row = make_row(
            criterion=SealCriterionName.AVAILABLE,
            probation_start=NOW - PROBATION_PERIOD - timedelta(days=1),
        )
        result = ReliabilityCriterionImpl.from_orm(row)

        assert result.on_probation is True
        assert result.probation_ends_at is None

    def test_elapsed_grace_period_reports_no_end_date(self):
        """Likewise for a grace window that has run out without the job acting on it."""
        row = make_row(
            observed_status="fail",
            confirmed_status="pass",
            first_observed_failure_at=NOW - timedelta(days=31),
            last_observed_failure_at=NOW,
        )
        result = ReliabilityCriterionImpl.from_orm(row)

        assert result.in_grace_period is True
        assert result.grace_period_ends_at is None
