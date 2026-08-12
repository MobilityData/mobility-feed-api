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
from datetime import datetime, timezone

from tasks.seal_of_reliability.context import FeedSealContext
from tasks.seal_of_reliability.criteria import SealCriterionName
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
        self.assertTrue(OfficialEvaluator().evaluate(_ctx(official=True)).observed_pass)

    def test_non_official_feed_fails(self):
        self.assertFalse(
            OfficialEvaluator().evaluate(_ctx(official=False)).observed_pass
        )

    def test_unknown_official_flag_fails(self):
        """NULL is not an endorsement: only an explicit True passes."""
        self.assertFalse(
            OfficialEvaluator().evaluate(_ctx(official=None)).observed_pass
        )

    def test_has_no_grace_or_probation(self):
        """A point-in-time check: it clears as soon as the feed is official again."""
        self.assertIsNone(OfficialEvaluator.grace_period)
        self.assertIsNone(OfficialEvaluator.probation_period)

    def test_reason_names_the_offending_value(self):
        result = OfficialEvaluator().evaluate(_ctx(official=None))
        self.assertIn("None", result.reason)


if __name__ == "__main__":
    unittest.main()
