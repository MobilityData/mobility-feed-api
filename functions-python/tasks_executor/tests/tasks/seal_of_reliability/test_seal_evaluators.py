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
"""Unit tests for the seal criterion evaluators. No database."""

import unittest
from datetime import datetime, timedelta, timezone

from shared.common.continuous_coverage import MAX_COVERAGE_WINDOW
from shared.common.seal_criteria import (
    FUTURE_COVERAGE_HORIZON,
    PROBATION_PERIOD,
    TRACKING_PERIOD,
    CriterionStatus,
    SealCriterionName,
)
from tasks.seal_of_reliability.context import (
    AvailabilityCheck,
    FeedSealContext,
    DatasetCoverage,
    ValidationReport,
)
from tasks.seal_of_reliability.evaluators import (
    EVALUATORS,
    AvailableEvaluator,
    CompliantEvaluator,
    CriterionEvaluator,
    FreshContinuousEvaluator,
    FreshCoverageEvaluator,
    OfficialEvaluator,
    StableEvaluator,
)

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _ctx(**overrides) -> FeedSealContext:
    defaults = {"feed_id": "feed-1", "now": NOW, "stable_id": "mdb-1"}
    defaults.update(overrides)
    return FeedSealContext(**defaults)


class TestBaseClass(unittest.TestCase):
    def test_subclass_must_implement_evaluate(self):
        class Incomplete(CriterionEvaluator):
            name = SealCriterionName.OFFICIAL

        with self.assertRaises(NotImplementedError):
            Incomplete().evaluate(_ctx())

    def test_result_is_labelled_with_the_evaluator_name(self):
        for evaluator in EVALUATORS:
            with self.subTest(criterion=evaluator.name):
                result = evaluator.evaluate(_ctx(official=True))
                self.assertEqual(result.criterion, evaluator.name)

    def test_every_result_carries_a_reason(self):
        for evaluator in EVALUATORS:
            with self.subTest(criterion=evaluator.name):
                self.assertTrue(evaluator.evaluate(_ctx()).reason)

    def test_never_evaluated_is_rejected(self):
        """NEVER_EVALUATED describes a row never written to, so no evaluator may return it.

        An evaluator that did would look to the state machine like a criterion that has
        never been seen, silently handing it a grace period it has not earned. UNKNOWN and
        NOT_APPLICABLE are the two ways to withhold a verdict.
        """

        class Confused(CriterionEvaluator):
            name = SealCriterionName.OFFICIAL

            def _evaluate(self, ctx):
                return CriterionStatus.NEVER_EVALUATED, "should not be allowed"

        with self.assertRaises(ValueError) as caught:
            Confused().evaluate(_ctx())
        self.assertIn("NEVER_EVALUATED", str(caught.exception))

    def test_no_verdict_statuses_are_passed_through(self):
        """An evaluator may withhold a verdict either way, and both reach the observation."""
        for status in (CriterionStatus.UNKNOWN, CriterionStatus.NOT_APPLICABLE):
            with self.subTest(status=status):

                class Withholding(CriterionEvaluator):
                    name = SealCriterionName.COMPLIANT

                    def _evaluate(self, ctx, _status=status):
                        return _status, "withheld"

                self.assertIs(Withholding().evaluate(_ctx()).observed_status, status)

    def test_registry_has_no_duplicate_criteria(self):
        names = [evaluator.name for evaluator in EVALUATORS]
        self.assertEqual(sorted(names), sorted(set(names)))

    def test_registry_only_uses_known_criteria(self):
        """Every registered evaluator must map onto a value of the DB enum."""
        for evaluator in EVALUATORS:
            with self.subTest(criterion=evaluator.name):
                self.assertIn(evaluator.name, set(SealCriterionName))


class TestOfficial(unittest.TestCase):
    def test_official_feed_passes(self):
        self.assertIs(
            OfficialEvaluator().evaluate(_ctx(official=True)).observed_status,
            CriterionStatus.PASS,
        )

    def test_non_official_feed_fails(self):
        self.assertIs(
            OfficialEvaluator().evaluate(_ctx(official=False)).observed_status,
            CriterionStatus.FAIL,
        )

    def test_null_official_flag_fails_rather_than_unknown(self):
        """NULL is not an endorsement, and the column is always readable.

        So an absent flag is a verdict of FAIL, not UNKNOWN: nothing is missing, the answer
        is simply no. UNKNOWN would freeze the criterion instead of denying the seal.
        """
        self.assertIs(
            OfficialEvaluator().evaluate(_ctx(official=None)).observed_status,
            CriterionStatus.FAIL,
        )

    def test_never_returns_a_no_verdict_status(self):
        """Official is always evaluable, so it can never withhold a verdict."""
        for official in (True, False, None):
            with self.subTest(official=official):
                status = (
                    OfficialEvaluator()
                    .evaluate(_ctx(official=official))
                    .observed_status
                )
                self.assertTrue(status.is_verdict)

    def test_has_no_grace_or_probation(self):
        """A point-in-time check: it clears as soon as the feed is official again."""
        self.assertIsNone(OfficialEvaluator().grace_period)
        self.assertIsNone(OfficialEvaluator().probation_period)

    def test_reason_names_the_offending_value(self):
        result = OfficialEvaluator().evaluate(_ctx(official=None))
        self.assertIn("None", result.reason)


class TestStable(unittest.TestCase):
    """`feed.created_at <= now - 180 days` and the producer URL is not flagged unstable."""

    def _stable_ctx(self, **overrides):
        defaults = {"feed_created_at": NOW - TRACKING_PERIOD - timedelta(days=1)}
        defaults.update(overrides)
        return _ctx(**defaults)

    def test_an_old_feed_with_a_stable_url_passes(self):
        self.assertIs(
            StableEvaluator().evaluate(self._stable_ctx()).observed_status,
            CriterionStatus.PASS,
        )

    def test_an_unstable_producer_url_fails(self):
        result = StableEvaluator().evaluate(
            self._stable_ctx(is_producer_url_unstable=True)
        )
        self.assertIs(result.observed_status, CriterionStatus.FAIL)
        self.assertIn("is_producer_url_unstable", result.reason)

    def test_a_null_unstable_flag_is_not_a_claim_of_instability(self):
        """The SQL predicate is `IS NOT TRUE`, so NULL and False both leave the check open."""
        for flag in (None, False):
            with self.subTest(is_producer_url_unstable=flag):
                self.assertIs(
                    StableEvaluator()
                    .evaluate(self._stable_ctx(is_producer_url_unstable=flag))
                    .observed_status,
                    CriterionStatus.PASS,
                )

    def test_a_young_feed_fails(self):
        result = StableEvaluator().evaluate(
            self._stable_ctx(feed_created_at=NOW - timedelta(days=179))
        )
        self.assertIs(result.observed_status, CriterionStatus.FAIL)
        self.assertIn("179", result.reason)

    def test_a_feed_created_today_fails(self):
        result = StableEvaluator().evaluate(self._stable_ctx(feed_created_at=NOW))
        self.assertIs(result.observed_status, CriterionStatus.FAIL)
        self.assertIn("0 day(s)", result.reason)

    def test_the_boundary_day_passes(self):
        """Exactly 180 days in the database is enough; the check is `<= now - 180 days`."""
        self.assertIs(
            StableEvaluator()
            .evaluate(self._stable_ctx(feed_created_at=NOW - TRACKING_PERIOD))
            .observed_status,
            CriterionStatus.PASS,
        )

    def test_a_missing_creation_date_fails_rather_than_withholding(self):
        """feed.created_at is NOT NULL, so this is unreachable from the database.

        It is still a verdict: an UNKNOWN would freeze the criterion at whatever it last
        said, and reporting a feed as not yet stable beats holding a seal on a value nobody
        supplied.
        """
        result = StableEvaluator().evaluate(self._stable_ctx(feed_created_at=None))
        self.assertIs(result.observed_status, CriterionStatus.FAIL)
        self.assertIn("created_at", result.reason)

    def test_the_unstable_flag_is_checked_before_the_feed_age(self):
        """Both fail, but the reason has to name the one an operator can act on."""
        result = StableEvaluator().evaluate(
            _ctx(feed_created_at=NOW, is_producer_url_unstable=True)
        )
        self.assertIn("is_producer_url_unstable", result.reason)

    def test_never_returns_a_no_verdict_status(self):
        """Both inputs are on the feed row, so Stable can never withhold a verdict."""
        for created_at in (None, NOW, NOW - timedelta(days=400)):
            for flag in (None, False, True):
                with self.subTest(feed_created_at=created_at, unstable=flag):
                    status = (
                        StableEvaluator()
                        .evaluate(
                            _ctx(
                                feed_created_at=created_at,
                                is_producer_url_unstable=flag,
                            )
                        )
                        .observed_status
                    )
                    self.assertTrue(status.is_verdict)

    def test_has_no_grace_or_probation(self):
        """A point-in-time check, like Official: neither input flickers."""
        self.assertIsNone(StableEvaluator().grace_period)
        self.assertIsNone(StableEvaluator().probation_period)


class TestFreshCoverage(unittest.TestCase):
    """`closest_dataset.service_date_range_end >= now + 7 days`."""

    @staticmethod
    def _dataset(coverage_end):
        return DatasetCoverage(
            dataset_id="mdb-1-202606010000",
            downloaded_at=NOW - timedelta(days=1),
            service_date_range_end=coverage_end,
        )

    def _fresh_ctx(self, coverage_end=NOW + timedelta(days=90), **overrides):
        defaults = {"closest_dataset": self._dataset(coverage_end)}
        defaults.update(overrides)
        return _ctx(**defaults)

    def test_coverage_beyond_the_horizon_passes(self):
        self.assertIs(
            FreshCoverageEvaluator().evaluate(self._fresh_ctx()).observed_status,
            CriterionStatus.PASS,
        )

    def test_coverage_inside_the_horizon_fails(self):
        """It fails before the data runs out, not on the day it does."""
        result = FreshCoverageEvaluator().evaluate(
            self._fresh_ctx(NOW + timedelta(days=3))
        )
        self.assertIs(result.observed_status, CriterionStatus.FAIL)
        self.assertIn("before the", result.reason)

    def test_the_horizon_itself_passes(self):
        self.assertIs(
            FreshCoverageEvaluator()
            .evaluate(self._fresh_ctx(NOW + FUTURE_COVERAGE_HORIZON))
            .observed_status,
            CriterionStatus.PASS,
        )

    def test_expired_coverage_fails(self):
        self.assertIs(
            FreshCoverageEvaluator()
            .evaluate(self._fresh_ctx(NOW - timedelta(days=1)))
            .observed_status,
            CriterionStatus.FAIL,
        )

    def test_a_seasonal_feed_is_not_applicable(self):
        """Withdrawn from the roll-up rather than failed: the question is meaningless."""
        result = FreshCoverageEvaluator().evaluate(self._fresh_ctx(seasonal=True))
        self.assertIs(result.observed_status, CriterionStatus.NOT_APPLICABLE)
        self.assertIn("seasonal", result.reason)

    def test_a_seasonal_feed_is_not_applicable_even_with_no_dataset(self):
        """Applicability is a property of the feed, so it is settled before the inputs."""
        self.assertIs(
            FreshCoverageEvaluator()
            .evaluate(self._fresh_ctx(seasonal=True, closest_dataset=None))
            .observed_status,
            CriterionStatus.NOT_APPLICABLE,
        )

    def test_a_non_seasonal_feed_is_evaluated(self):
        for seasonal in (None, False):
            with self.subTest(seasonal=seasonal):
                self.assertIs(
                    FreshCoverageEvaluator()
                    .evaluate(self._fresh_ctx(seasonal=seasonal))
                    .observed_status,
                    CriterionStatus.PASS,
                )

    def test_no_closest_dataset_is_unknown(self):
        """Not a failure: a feed we have never fetched says nothing about its freshness."""
        result = FreshCoverageEvaluator().evaluate(
            self._fresh_ctx(closest_dataset=None)
        )
        self.assertIs(result.observed_status, CriterionStatus.UNKNOWN)
        self.assertIn("no dataset", result.reason)

    def test_a_dataset_with_no_coverage_end_is_unknown(self):
        """The other missing input, and the reason has to tell the two apart."""
        result = FreshCoverageEvaluator().evaluate(self._fresh_ctx(None))
        self.assertIs(result.observed_status, CriterionStatus.UNKNOWN)
        self.assertIn("service_date_range_end", result.reason)

    def test_has_a_grace_period_and_serves_probation(self):
        """Coverage lapses are the routine failure the grace period exists to absorb."""
        self.assertEqual(FreshCoverageEvaluator().grace_period, timedelta(days=14))
        self.assertEqual(FreshCoverageEvaluator().probation_period, PROBATION_PERIOD)


class TestAvailable(unittest.TestCase):
    """The latest availability check in the window since the previous evaluation."""

    @staticmethod
    def _check(success, checked_at=None):
        return AvailabilityCheck(checked_at=checked_at or NOW, success=success)

    def test_a_successful_check_passes(self):
        self.assertIs(
            AvailableEvaluator()
            .evaluate(_ctx(availability_check=self._check(True)))
            .observed_status,
            CriterionStatus.PASS,
        )

    def test_a_failed_check_fails(self):
        result = AvailableEvaluator().evaluate(
            _ctx(availability_check=self._check(False))
        )
        self.assertIs(result.observed_status, CriterionStatus.FAIL)
        self.assertIn("failed", result.reason)

    def test_no_check_in_the_window_is_unknown_not_a_failure(self):
        """A window the availability job did not cover says nothing about the producer."""
        result = AvailableEvaluator().evaluate(_ctx(availability_check=None))
        self.assertIs(result.observed_status, CriterionStatus.UNKNOWN)
        self.assertIn("no availability check since", result.reason)

    def test_the_reason_names_the_check_it_read(self):
        """The window makes "which check decided this" a real question, so answer it."""
        checked_at = NOW - timedelta(hours=3)
        result = AvailableEvaluator().evaluate(
            _ctx(availability_check=self._check(False, checked_at))
        )
        self.assertIn(checked_at.isoformat(), result.reason)

    def test_is_never_not_applicable(self):
        """Availability applies to every feed, seasonal ones included."""
        for check in (self._check(True), self._check(False), None):
            with self.subTest(check=check):
                self.assertIsNot(
                    AvailableEvaluator()
                    .evaluate(_ctx(availability_check=check, seasonal=True))
                    .observed_status,
                    CriterionStatus.NOT_APPLICABLE,
                )

    def test_has_a_grace_period_and_serves_probation(self):
        self.assertEqual(AvailableEvaluator().grace_period, timedelta(days=14))
        self.assertEqual(AvailableEvaluator().probation_period, PROBATION_PERIOD)


class TestCompliant(unittest.TestCase):
    """`total_error = 0` on the latest validation report of the feed's closest dataset."""

    DATASET_ID = "mdb-1-202605280000"

    def _compliant_ctx(
        self, total_error=0, with_report=True, with_dataset=True, **overrides
    ):
        report = (
            ValidationReport(
                report_id="report-1",
                dataset_id=self.DATASET_ID,
                validated_at=NOW - timedelta(hours=1),
                total_error=total_error,
            )
            if with_report
            else None
        )
        dataset = (
            DatasetCoverage(
                dataset_id=self.DATASET_ID,
                downloaded_at=NOW - timedelta(hours=2),
            )
            if with_dataset
            else None
        )
        defaults = {"latest_validation_report": report, "closest_dataset": dataset}
        defaults.update(overrides)
        return _ctx(**defaults)

    def test_a_clean_report_passes(self):
        self.assertIs(
            CompliantEvaluator().evaluate(self._compliant_ctx(0)).observed_status,
            CriterionStatus.PASS,
        )

    def test_any_error_fails(self):
        result = CompliantEvaluator().evaluate(self._compliant_ctx(1))
        self.assertIs(result.observed_status, CriterionStatus.FAIL)
        self.assertIn("1 error(s)", result.reason)

    def test_a_feed_with_no_dataset_is_unknown(self):
        """Nothing published means nothing to validate, not a failure."""
        result = CompliantEvaluator().evaluate(
            self._compliant_ctx(with_report=False, with_dataset=False)
        )
        self.assertIs(result.observed_status, CriterionStatus.UNKNOWN)
        self.assertIn("no dataset", result.reason)

    def test_an_unvalidated_closest_dataset_is_unknown(self):
        """The case that keeps a never-validated feed off a confirmed failure.

        Validation lags publication, so a feed publishing faster than the validator sits at
        UNKNOWN and keeps whatever verdict it last earned.
        """
        result = CompliantEvaluator().evaluate(self._compliant_ctx(with_report=False))
        self.assertIs(result.observed_status, CriterionStatus.UNKNOWN)
        self.assertIn("no validation report", result.reason)
        self.assertIn(self.DATASET_ID, result.reason)

    def test_the_reason_names_the_dataset_that_was_validated(self):
        result = CompliantEvaluator().evaluate(self._compliant_ctx(3))
        self.assertIn(self.DATASET_ID, result.reason)

    def test_a_report_with_no_error_count_is_unknown_not_a_pass(self):
        """total_error is nullable, and a missing count must not read as zero errors."""
        result = CompliantEvaluator().evaluate(self._compliant_ctx(None))
        self.assertIs(result.observed_status, CriterionStatus.UNKNOWN)
        self.assertIn("no total_error", result.reason)

    def test_is_never_not_applicable(self):
        """Compliance applies to every feed, seasonal ones included."""
        self.assertIsNot(
            CompliantEvaluator()
            .evaluate(self._compliant_ctx(0, seasonal=True))
            .observed_status,
            CriterionStatus.NOT_APPLICABLE,
        )

    def test_has_a_grace_period_and_serves_probation(self):
        self.assertEqual(CompliantEvaluator().grace_period, timedelta(days=30))
        self.assertEqual(CompliantEvaluator().probation_period, PROBATION_PERIOD)


class TestFreshContinuous(unittest.TestCase):
    """The maximum coverage window, then the single-dataset pass, then the boundary."""

    TODAY = NOW.date()

    def _days(self, offset):
        return self.TODAY + timedelta(days=offset)

    @staticmethod
    def _dataset(dataset_id, service=None, declared=None, has_calendar_data=True):
        """One dataset, its two windows given as `(start, end)` date pairs or None."""
        return DatasetCoverage(
            dataset_id=dataset_id,
            downloaded_at=NOW,
            service_date_range_start=service[0] if service else None,
            service_date_range_end=service[1] if service else None,
            feed_info_start=declared[0] if declared else None,
            feed_info_end=declared[1] if declared else None,
            has_calendar_data=has_calendar_data,
        )

    def _verdict(self, older, newer, **overrides):
        return FreshContinuousEvaluator().evaluate(
            _ctx(previous_dataset=older, closest_dataset=newer, **overrides)
        )

    def _continuous_pair(self):
        older = self._dataset(
            "ds-older",
            service=(self._days(-60), self._days(-10)),
            declared=(self._days(-60), self._days(-10)),
        )
        newer = self._dataset(
            "ds-newer",
            service=(self._days(-20), self._days(60)),
            declared=(self._days(-20), self._days(60)),
        )
        return older, newer

    # 1. the maximum coverage window, on the closest dataset alone

    def test_an_overlong_declared_range_fails(self):
        newer = self._dataset(
            "ds-newer",
            service=(self._days(-20), self._days(60)),
            declared=(self._days(-20), self._days(MAX_COVERAGE_WINDOW.days + 1)),
        )
        older, _ = self._continuous_pair()
        result = self._verdict(older, newer)
        self.assertIs(result.observed_status, CriterionStatus.FAIL)
        self.assertIn("maximum coverage window", result.reason)

    def test_the_maximum_window_itself_passes(self):
        older, _ = self._continuous_pair()
        newer = self._dataset(
            "ds-newer",
            declared=(self._days(-20), self._days(-20 + MAX_COVERAGE_WINDOW.days)),
        )
        self.assertIs(self._verdict(older, newer).observed_status, CriterionStatus.PASS)

    def test_the_threshold_falls_back_to_the_service_window(self):
        """No declared range, so the validated one is what the threshold measures."""
        newer = self._dataset(
            "ds-newer",
            service=(self._days(-20), self._days(MAX_COVERAGE_WINDOW.days + 1)),
        )
        result = self._verdict(None, newer)
        self.assertIs(result.observed_status, CriterionStatus.FAIL)
        self.assertIn("maximum coverage window", result.reason)

    def test_the_declared_range_is_measured_ahead_of_the_service_window(self):
        newer = self._dataset(
            "ds-newer",
            service=(self._days(-20), self._days(MAX_COVERAGE_WINDOW.days + 1)),
            declared=(self._days(-20), self._days(60)),
        )
        self.assertIs(self._verdict(None, newer).observed_status, CriterionStatus.PASS)

    def test_the_threshold_is_reached_before_the_single_dataset_pass(self):
        """A feed can fail on its only dataset, which is why this step comes first."""
        newer = self._dataset(
            "ds-newer",
            declared=(self._days(-20), self._days(MAX_COVERAGE_WINDOW.days + 1)),
        )
        self.assertIs(self._verdict(None, newer).observed_status, CriterionStatus.FAIL)

    def test_the_previous_datasets_window_is_not_measured(self):
        older = self._dataset(
            "ds-older",
            service=(self._days(-MAX_COVERAGE_WINDOW.days - 100), self._days(-10)),
            declared=(self._days(-MAX_COVERAGE_WINDOW.days - 100), self._days(-10)),
        )
        _, newer = self._continuous_pair()
        self.assertIs(self._verdict(older, newer).observed_status, CriterionStatus.PASS)

    # 2. no previous dataset

    def test_a_feed_with_one_dataset_passes(self):
        newer = self._dataset("ds-newer", service=(self._days(-20), self._days(60)))
        result = self._verdict(None, newer)
        self.assertIs(result.observed_status, CriterionStatus.PASS)
        self.assertIn("only dataset", result.reason)

    def test_no_window_and_no_calendar_files_fails(self):
        result = self._verdict(None, self._dataset("ds-newer", has_calendar_data=False))
        self.assertIs(result.observed_status, CriterionStatus.FAIL)
        self.assertIn("carries neither", result.reason)

    def test_no_window_with_calendar_files_is_unknown(self):
        """The file is there and the window is not, so the missing input is ours."""
        result = self._verdict(None, self._dataset("ds-newer", has_calendar_data=True))
        self.assertIs(result.observed_status, CriterionStatus.UNKNOWN)
        self.assertIn("no validated service window yet", result.reason)

    def test_a_windowless_closest_dataset_is_settled_before_the_boundary(self):
        older, _ = self._continuous_pair()
        result = self._verdict(
            older, self._dataset("ds-newer", has_calendar_data=False)
        )
        self.assertIs(result.observed_status, CriterionStatus.FAIL)
        self.assertIn("ds-newer carries neither", result.reason)

    def test_a_feed_with_no_dataset_is_unknown(self):
        result = FreshContinuousEvaluator().evaluate(_ctx())
        self.assertIs(result.observed_status, CriterionStatus.UNKNOWN)
        self.assertIn("no dataset", result.reason)

    # 3. the boundary

    def test_overlapping_declared_ranges_pass(self):
        result = self._verdict(*self._continuous_pair())
        self.assertIs(result.observed_status, CriterionStatus.PASS)
        self.assertIn("no gap", result.reason)

    def test_declared_ranges_that_meet_exactly_pass(self):
        older = self._dataset("ds-older", declared=(self._days(-60), self._days(-10)))
        newer = self._dataset("ds-newer", declared=(self._days(-9), self._days(60)))
        self.assertIs(self._verdict(older, newer).observed_status, CriterionStatus.PASS)

    def test_a_declared_gap_is_excused_by_continuous_calendars(self):
        older = self._dataset(
            "ds-older",
            service=(self._days(-60), self._days(-5)),
            declared=(self._days(-60), self._days(-30)),
        )
        newer = self._dataset(
            "ds-newer",
            service=(self._days(-10), self._days(60)),
            declared=(self._days(-20), self._days(60)),
        )
        result = self._verdict(older, newer)
        self.assertIs(result.observed_status, CriterionStatus.PASS)
        self.assertIn("9-day gap", result.reason)
        self.assertIn("validated service windows leave no gap", result.reason)

    def test_a_gap_in_both_windows_fails(self):
        older = self._dataset(
            "ds-older",
            service=(self._days(-60), self._days(-30)),
            declared=(self._days(-60), self._days(-30)),
        )
        newer = self._dataset(
            "ds-newer",
            service=(self._days(-20), self._days(60)),
            declared=(self._days(-20), self._days(60)),
        )
        result = self._verdict(older, newer)
        self.assertIs(result.observed_status, CriterionStatus.FAIL)
        self.assertIn("validated service windows leave a 9-day gap", result.reason)

    def test_one_uncovered_day_is_enough_to_fail(self):
        older = self._dataset(
            "ds-older",
            service=(self._days(-60), self._days(-10)),
            declared=(self._days(-60), self._days(-10)),
        )
        newer = self._dataset(
            "ds-newer",
            service=(self._days(-8), self._days(60)),
            declared=(self._days(-8), self._days(60)),
        )
        result = self._verdict(older, newer)
        self.assertIs(result.observed_status, CriterionStatus.FAIL)
        self.assertIn("1-day gap", result.reason)

    def test_a_declared_gap_with_no_calendar_published_fails(self):
        """The thread's decision: no calendar file is the producer's answer, not a missing one."""
        older = self._dataset(
            "ds-older",
            service=(self._days(-60), self._days(-30)),
            declared=(self._days(-60), self._days(-30)),
        )
        newer = self._dataset(
            "ds-newer",
            declared=(self._days(-20), self._days(60)),
            has_calendar_data=False,
        )
        result = self._verdict(older, newer)
        self.assertIs(result.observed_status, CriterionStatus.FAIL)
        self.assertIn("ds-newer carries no calendar.txt", result.reason)

    def test_a_declared_gap_with_an_unprocessed_calendar_is_unknown(self):
        """The file is there and the window is not, so the missing input is ours."""
        older = self._dataset(
            "ds-older",
            service=(self._days(-60), self._days(-30)),
            declared=(self._days(-60), self._days(-30)),
        )
        newer = self._dataset(
            "ds-newer",
            declared=(self._days(-20), self._days(60)),
            has_calendar_data=True,
        )
        result = self._verdict(older, newer)
        self.assertIs(result.observed_status, CriterionStatus.UNKNOWN)
        self.assertIn("no validated service window yet", result.reason)

    def test_a_producer_omission_outweighs_our_own_lag(self):
        """One dataset short of each: the producer's omission decides."""
        older = self._dataset(
            "ds-older",
            declared=(self._days(-60), self._days(-30)),
            has_calendar_data=False,
        )
        newer = self._dataset(
            "ds-newer",
            declared=(self._days(-20), self._days(60)),
            has_calendar_data=True,
        )
        result = self._verdict(older, newer)
        self.assertIs(result.observed_status, CriterionStatus.FAIL)
        self.assertIn("ds-older carries no", result.reason)

    def test_with_no_declared_range_the_calendars_decide(self):
        older = self._dataset("ds-older", service=(self._days(-60), self._days(-10)))
        newer = self._dataset("ds-newer", service=(self._days(-20), self._days(60)))
        result = self._verdict(older, newer)
        self.assertIs(result.observed_status, CriterionStatus.PASS)
        self.assertIn("do not both declare", result.reason)

    def test_with_no_declared_range_a_calendar_gap_fails(self):
        older = self._dataset("ds-older", service=(self._days(-60), self._days(-30)))
        newer = self._dataset("ds-newer", service=(self._days(-20), self._days(60)))
        self.assertIs(self._verdict(older, newer).observed_status, CriterionStatus.FAIL)

    def test_a_declared_range_on_only_one_dataset_falls_back_to_the_calendars(self):
        """Half a declared boundary is not a boundary; the two ends must be comparable."""
        older = self._dataset(
            "ds-older",
            service=(self._days(-60), self._days(-30)),
            declared=(self._days(-60), self._days(-10)),
        )
        newer = self._dataset("ds-newer", service=(self._days(-20), self._days(60)))
        result = self._verdict(older, newer)
        self.assertIs(result.observed_status, CriterionStatus.FAIL)
        self.assertIn("do not both declare", result.reason)

    def test_an_inverted_window_is_no_window(self):
        older = self._dataset(
            "ds-older",
            service=(self._days(-60), self._days(-10)),
            declared=(self._days(-10), self._days(-60)),
        )
        _, newer = self._continuous_pair()
        result = self._verdict(older, newer)
        self.assertIs(result.observed_status, CriterionStatus.PASS)
        self.assertIn("do not both declare", result.reason)

    # policy

    def test_a_seasonal_feed_is_still_evaluated(self):
        """Unlike Fresh / future coverage, this criterion has no seasonal exemption."""
        result = self._verdict(*self._continuous_pair(), seasonal=True)
        self.assertIs(result.observed_status, CriterionStatus.PASS)

    def test_has_no_grace_period_but_serves_probation(self):
        self.assertIsNone(FreshContinuousEvaluator().grace_period)
        self.assertEqual(FreshContinuousEvaluator().probation_period, PROBATION_PERIOD)


if __name__ == "__main__":
    unittest.main()
