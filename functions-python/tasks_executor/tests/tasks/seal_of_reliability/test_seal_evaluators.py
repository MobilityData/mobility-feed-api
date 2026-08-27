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
from datetime import date, datetime, timedelta, timezone

from shared.common.seal_criteria import (
    FUTURE_COVERAGE_HORIZON,
    PROBATION_PERIOD,
    TRACKING_PERIOD,
    CriterionStatus,
    SealCriterionName,
)
from tasks.seal_of_reliability.context import FeedSealContext, collect_inputs
from tasks.seal_of_reliability.evaluators.fresh_coverage import (
    FreshCoverageInputs,
    LatestDataset,
)
from tasks.seal_of_reliability.evaluators import (
    EVALUATORS,
    CriterionEvaluator,
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


class TestLoadInputs(unittest.TestCase):
    """The `load_inputs` hook, and how what it loads reaches `_evaluate`."""

    def test_no_criterion_queries_for_an_empty_batch(self):
        """A criterion reading only day-invariant context fields has nothing to load.

        None means "nothing to load", not "the load failed" — Official and Stable read the
        feed row off the context and never need a query. Fresh overrides the loader, because
        which dataset is "the latest" changes on every day a march evaluates, but it must
        still answer an empty batch without touching the session.

        The session is `object()` on purpose: any evaluator that queried here would raise.
        """
        for evaluator in EVALUATORS:
            with self.subTest(criterion=evaluator.name):
                loaded = evaluator.load_inputs(object(), [], [NOW.date()])
                if isinstance(evaluator, FreshCoverageEvaluator):
                    self.assertIsInstance(loaded, FreshCoverageInputs)
                else:
                    self.assertIsNone(loaded)

    def test_each_criterion_is_asked_once_for_the_whole_batch(self):
        """One call per criterion, carrying every feed and every day.

        This is the property the backfill depends on: a criterion loading per day instead
        would turn a year's march into several thousand queries.
        """
        calls = []

        class Recording(CriterionEvaluator):
            name = SealCriterionName.AVAILABLE

            def load_inputs(self, db_session, feeds, days):
                calls.append((tuple(feeds), tuple(days)))
                return {"loaded": True}

            def _evaluate(self, ctx):
                return CriterionStatus.PASS, "recorded"

        feeds = ["feed-1", "feed-2"]
        days = [date(2026, 5, 30), date(2026, 5, 31), NOW.date()]
        inputs = collect_inputs(object(), feeds, days, [Recording()])

        self.assertEqual(calls, [(("feed-1", "feed-2"), tuple(days))])
        self.assertEqual(inputs, {SealCriterionName.AVAILABLE: {"loaded": True}})

    def test_a_criterion_reaches_only_its_own_inputs(self):
        ctx = _ctx(
            inputs={
                SealCriterionName.AVAILABLE: "available-inputs",
                SealCriterionName.COMPLIANT: "compliant-inputs",
            }
        )
        self.assertEqual(
            ctx.inputs_for(SealCriterionName.AVAILABLE), "available-inputs"
        )
        self.assertIsNone(ctx.inputs_for(SealCriterionName.OFFICIAL))

    def test_context_defaults_to_no_inputs(self):
        self.assertIsNone(_ctx().inputs_for(SealCriterionName.AVAILABLE))


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
    """`latest dataset.service_date_range_end >= now + 7 days`."""

    @staticmethod
    def _inputs(coverage_end):
        """The criterion's own loaded inputs, holding one dataset for `feed-1`."""
        return FreshCoverageInputs(
            {
                "feed-1": [
                    LatestDataset(
                        dataset_id="mdb-1-202606010000",
                        downloaded_at=NOW - timedelta(days=1),
                        service_date_range_end=coverage_end,
                    )
                ]
            }
        )

    def _fresh_ctx(
        self, coverage_end=NOW + timedelta(days=90), dataset=True, **overrides
    ):
        """A context whose Fresh inputs were loaded, with or without a dataset in them.

        `dataset=False` is a feed that had none as of `now` — an empty load, which is not the
        same thing as a load that never ran (see `test_unloaded_inputs_say_so`).
        """
        defaults = {
            "inputs": {
                SealCriterionName.FRESH_COVERAGE: (
                    self._inputs(coverage_end) if dataset else FreshCoverageInputs({})
                )
            }
        }
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
            .evaluate(self._fresh_ctx(seasonal=True, dataset=False))
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

    def test_no_latest_dataset_is_unknown(self):
        """Not a failure: a feed we have never fetched says nothing about its freshness."""
        result = FreshCoverageEvaluator().evaluate(self._fresh_ctx(dataset=False))
        self.assertIs(result.observed_status, CriterionStatus.UNKNOWN)
        self.assertIn("no latest dataset", result.reason)

    def test_a_dataset_with_no_coverage_end_is_unknown(self):
        """The other missing input, and the reason has to tell the two apart."""
        result = FreshCoverageEvaluator().evaluate(self._fresh_ctx(None))
        self.assertIs(result.observed_status, CriterionStatus.UNKNOWN)
        self.assertIn("service_date_range_end", result.reason)

    def test_has_a_grace_period_and_serves_probation(self):
        """Coverage lapses are the routine failure the grace period exists to absorb."""
        self.assertEqual(FreshCoverageEvaluator().grace_period, timedelta(days=14))
        self.assertEqual(FreshCoverageEvaluator().probation_period, PROBATION_PERIOD)

    def test_unloaded_inputs_say_so(self):
        """A context built without running the loader is a bug, not a missing dataset.

        Both end as UNKNOWN, because a raise would take down a whole nightly run over the
        catalogue, but the reason has to name the real cause: a silent "no latest dataset"
        across every feed of a backfill is exactly what going unnoticed looks like.
        """
        result = FreshCoverageEvaluator().evaluate(_ctx())
        self.assertIs(result.observed_status, CriterionStatus.UNKNOWN)
        self.assertIn("never loaded", result.reason)

    def test_the_latest_dataset_is_resolved_as_of_the_day_being_evaluated(self):
        """The point of loading a range: each day of a march sees its own latest dataset.

        Three datasets, published a week apart, each covering less of the future than the
        last. Evaluated at three different `now`s from one loaded input set, the criterion
        reads a different dataset each time.
        """
        published = [
            (NOW - timedelta(days=14), NOW + timedelta(days=90)),
            (NOW - timedelta(days=7), NOW + timedelta(days=30)),
            (NOW - timedelta(days=1), NOW + timedelta(days=2)),
        ]
        inputs = FreshCoverageInputs(
            {
                "feed-1": [
                    LatestDataset(
                        dataset_id=f"mdb-1-{index}",
                        downloaded_at=downloaded_at,
                        service_date_range_end=coverage_end,
                    )
                    for index, (downloaded_at, coverage_end) in enumerate(published)
                ]
            }
        )
        payload = {SealCriterionName.FRESH_COVERAGE: inputs}

        for offset, expected in (
            (-20, CriterionStatus.UNKNOWN),  # before the feed had any dataset
            (-10, CriterionStatus.PASS),  # the first one, covering 90 days out
            (-3, CriterionStatus.PASS),  # the second, still beyond the horizon
            (0, CriterionStatus.FAIL),  # the third, covering only 2 more days
        ):
            moment = NOW + timedelta(days=offset)
            with self.subTest(days_from_now=offset):
                result = FreshCoverageEvaluator().evaluate(
                    _ctx(now=moment, inputs=payload)
                )
                self.assertIs(result.observed_status, expected)


if __name__ == "__main__":
    unittest.main()
