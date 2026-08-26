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
from datetime import date, datetime, timezone

from tasks.seal_of_reliability.context import FeedSealContext, collect_inputs
from tasks.seal_of_reliability.criteria import CriterionStatus, SealCriterionName
from tasks.seal_of_reliability.evaluators import (
    EVALUATORS,
    CriterionEvaluator,
    OfficialEvaluator,
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
        self.assertIsNone(OfficialEvaluator.grace_period)
        self.assertIsNone(OfficialEvaluator.probation_period)

    def test_reason_names_the_offending_value(self):
        result = OfficialEvaluator().evaluate(_ctx(official=None))
        self.assertIn("None", result.reason)


class TestLoadInputs(unittest.TestCase):
    """The `load_inputs` hook, and how what it loads reaches `_evaluate`."""

    def test_default_loader_loads_nothing(self):
        """A criterion reading only day-invariant context fields has nothing to load.

        None here means "nothing to load", not "the load failed" — Official reads
        `feed.official` off the context and never needs a query.
        """
        for evaluator in EVALUATORS:
            with self.subTest(criterion=evaluator.name):
                self.assertIsNone(evaluator.load_inputs(object(), [], [NOW.date()]))

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


if __name__ == "__main__":
    unittest.main()
