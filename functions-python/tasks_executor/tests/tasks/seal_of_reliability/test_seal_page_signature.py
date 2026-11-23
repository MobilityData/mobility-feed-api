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

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from shared.common.seal_criteria import CriterionStatus, SealCriterionName
from tasks.seal_of_reliability.page_signature import (
    criterion_signature,
    feed_signature,
    page_state_changed,
)
from tasks.seal_of_reliability.state_machine import SealCriterionState

DAY_ZERO = datetime(2026, 1, 1, tzinfo=timezone.utc)
FEED_ID = "feed-1"

PASS = CriterionStatus.PASS
FAIL = CriterionStatus.FAIL
AVAILABLE = SealCriterionName.AVAILABLE
COMPLIANT = SealCriterionName.COMPLIANT


def steady(criterion=AVAILABLE, status=PASS, **overrides) -> SealCriterionState:
    """A criterion in no window: not on probation, no failure streak running."""
    base = SealCriterionState(
        feed_id=FEED_ID,
        criterion=criterion,
        observed_status=status,
        confirmed_status=status,
        evaluated_at=DAY_ZERO,
        last_verdict_at=DAY_ZERO,
    )
    return replace(base, **overrides)


def as_map(*states) -> dict:
    """The {criterion: state} shape `seal_updater` keys its two sides by."""
    return {state.criterion.value: state for state in states}


class TestCriterionSignature(unittest.TestCase):
    def test_carries_criterion_status_and_phase_only(self):
        self.assertEqual(
            criterion_signature(steady()),
            ("available", "pass", "steady"),
        )

    def test_grace_period_is_visible_in_the_signature(self):
        in_grace = steady(observed_status=FAIL, first_observed_failure_at=DAY_ZERO)
        self.assertEqual(criterion_signature(in_grace)[2], "in_grace_period")

    def test_probation_is_visible_in_the_signature(self):
        on_probation = steady(probation_start=DAY_ZERO)
        self.assertEqual(criterion_signature(on_probation)[2], "on_probation")


class TestFeedSignature(unittest.TestCase):
    def test_criterion_order_does_not_matter(self):
        one = steady(criterion=AVAILABLE)
        two = steady(criterion=COMPLIANT, status=FAIL)
        self.assertEqual(
            feed_signature(True, [one, two]),
            feed_signature(True, [two, one]),
        )

    def test_has_seal_is_part_of_the_signature(self):
        self.assertNotEqual(
            feed_signature(True, [steady()]),
            feed_signature(False, [steady()]),
        )


class TestTimestampsAreIgnored(unittest.TestCase):
    """The whole point: a run that only moves clocks must not bust the website cache."""

    def _unchanged(self, **overrides):
        previous = as_map(steady())
        new = as_map(replace(steady(), **overrides))
        self.assertFalse(
            page_state_changed(previous, new, had_seal=True, has_seal=True),
            f"{sorted(overrides)} should not count as a page change",
        )

    def test_evaluated_at_moving_is_not_a_change(self):
        self._unchanged(evaluated_at=DAY_ZERO + timedelta(days=1))

    def test_last_verdict_at_moving_is_not_a_change(self):
        self._unchanged(last_verdict_at=DAY_ZERO + timedelta(days=1))

    def test_failure_timestamps_moving_is_not_a_change(self):
        self._unchanged(
            last_observed_failure_at=DAY_ZERO + timedelta(days=1),
            last_confirmed_failure_at=DAY_ZERO + timedelta(days=1),
        )

    def test_probation_start_shifting_while_still_on_probation_is_not_a_change(self):
        # `probation_ends_at` on the response moves with it, but the page's on_probation badge
        # does not, and only the badge is rendered state.
        previous = as_map(steady(probation_start=DAY_ZERO))
        new = as_map(steady(probation_start=DAY_ZERO + timedelta(days=3)))
        self.assertFalse(
            page_state_changed(previous, new, had_seal=False, has_seal=False)
        )


class TestRealChanges(unittest.TestCase):
    def test_confirmed_status_flip_is_a_change(self):
        previous = as_map(steady(status=PASS))
        new = as_map(steady(status=FAIL))
        self.assertTrue(
            page_state_changed(previous, new, had_seal=True, has_seal=False)
        )

    def test_entering_the_grace_period_is_a_change(self):
        previous = as_map(steady())
        new = as_map(steady(observed_status=FAIL, first_observed_failure_at=DAY_ZERO))
        self.assertTrue(page_state_changed(previous, new, had_seal=True, has_seal=True))

    def test_leaving_the_grace_period_is_a_change(self):
        previous = as_map(
            steady(observed_status=FAIL, first_observed_failure_at=DAY_ZERO)
        )
        new = as_map(steady())
        self.assertTrue(page_state_changed(previous, new, had_seal=True, has_seal=True))

    def test_entering_probation_is_a_change(self):
        previous = as_map(steady())
        new = as_map(steady(probation_start=DAY_ZERO))
        self.assertTrue(
            page_state_changed(previous, new, had_seal=True, has_seal=False)
        )

    def test_leaving_probation_is_a_change(self):
        previous = as_map(steady(probation_start=DAY_ZERO))
        new = as_map(steady())
        self.assertTrue(
            page_state_changed(previous, new, had_seal=False, has_seal=True)
        )

    def test_has_seal_flip_alone_is_a_change(self):
        # Contrived - has_seal is rolled up from the criteria - but it is the field the header
        # badge reads, so it is compared in its own right.
        previous = as_map(steady())
        new = as_map(steady())
        self.assertTrue(
            page_state_changed(previous, new, had_seal=False, has_seal=True)
        )

    def test_a_new_criterion_appearing_is_a_change(self):
        previous = as_map(steady(criterion=AVAILABLE))
        new = as_map(steady(criterion=AVAILABLE), steady(criterion=COMPLIANT))
        self.assertTrue(page_state_changed(previous, new, had_seal=True, has_seal=True))


class TestFirstEvaluation(unittest.TestCase):
    def test_no_previous_state_is_a_change(self):
        """No seal_criterion row at all: the seal is new and the page has never shown it."""
        self.assertTrue(
            page_state_changed({}, as_map(steady()), had_seal=None, has_seal=True)
        )


class TestPartialRun(unittest.TestCase):
    """A partial-criteria run skips the roll-up, so both seal values are None."""

    def test_unevaluated_criterion_merged_in_unchanged_is_not_a_change(self):
        untouched = steady(criterion=COMPLIANT, status=FAIL)
        previous = as_map(steady(criterion=AVAILABLE), untouched)
        # `merged` is the stored states with this run's over them, so the criterion the run
        # did not evaluate carries the identical object on both sides.
        new = as_map(steady(criterion=AVAILABLE), untouched)
        self.assertFalse(
            page_state_changed(previous, new, had_seal=None, has_seal=None)
        )

    def test_evaluated_criterion_moving_is_still_a_change(self):
        untouched = steady(criterion=COMPLIANT, status=FAIL)
        previous = as_map(steady(criterion=AVAILABLE, status=PASS), untouched)
        new = as_map(steady(criterion=AVAILABLE, status=FAIL), untouched)
        self.assertTrue(page_state_changed(previous, new, had_seal=None, has_seal=None))


if __name__ == "__main__":
    unittest.main()
