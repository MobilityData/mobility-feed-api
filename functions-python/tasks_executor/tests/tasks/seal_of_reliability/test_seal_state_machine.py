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
"""Unit tests for the generic seal criterion state machine. No database."""

import unittest
from datetime import datetime, timedelta, timezone

from tasks.seal_of_reliability.criteria import RELIABILITY_WINDOW, SealCriterionName
from tasks.seal_of_reliability.evaluators.base import RawEvaluation
from tasks.seal_of_reliability.state_machine import SealCriterionState, transition

DAY_ZERO = datetime(2026, 1, 1, tzinfo=timezone.utc)
FEED_ID = "feed-1"

# Official, the first criterion implemented, has neither a grace period nor a reliability
# window, so it exercises almost none of the state machine. These tests drive a synthetic
# criterion that has both.
GRACE = timedelta(days=14)


def _raw(failing, criterion=SealCriterionName.AVAILABLE):
    return RawEvaluation(criterion=criterion, failing=failing, reason="test")


def _run(days, grace_period=GRACE, reliability_window=RELIABILITY_WINDOW, state=None):
    """Apply one verdict per entry in `days`: (day offset, failing)."""
    for offset, failing in days:
        state = transition(
            prev=state,
            raw=_raw(failing),
            grace_period=grace_period,
            reliability_window=reliability_window,
            now=DAY_ZERO + timedelta(days=offset),
            feed_id=FEED_ID,
        )
    return state


class TestNotEvaluable(unittest.TestCase):
    def test_none_verdict_leaves_state_untouched(self):
        """A criterion that cannot be evaluated must not change anything."""
        state = _run([(0, True)])
        unchanged = transition(
            prev=state,
            raw=_raw(None),
            grace_period=GRACE,
            reliability_window=RELIABILITY_WINDOW,
            now=DAY_ZERO + timedelta(days=1),
        )
        self.assertIs(unchanged, state)

    def test_none_verdict_with_no_previous_state_stays_none(self):
        self.assertIsNone(
            transition(
                prev=None,
                raw=_raw(None),
                grace_period=GRACE,
                reliability_window=RELIABILITY_WINDOW,
                now=DAY_ZERO,
                feed_id=FEED_ID,
            )
        )

    def test_missing_feed_id_without_previous_state_raises(self):
        with self.assertRaises(ValueError):
            transition(
                prev=None,
                raw=_raw(True),
                grace_period=GRACE,
                reliability_window=RELIABILITY_WINDOW,
                now=DAY_ZERO,
            )


class TestGracePeriod(unittest.TestCase):
    def test_first_failure_is_not_confirmed(self):
        state = _run([(0, True)])
        self.assertTrue(state.raw_failing)
        self.assertFalse(state.grace_failing)
        self.assertEqual(state.first_raw_failure_at, DAY_ZERO)
        self.assertEqual(state.last_raw_failure_at, DAY_ZERO)
        self.assertIsNone(state.last_grace_failure_at)

    def test_failure_within_grace_is_not_confirmed(self):
        state = _run([(day, True) for day in range(0, 14)])
        self.assertTrue(state.raw_failing)
        self.assertFalse(state.grace_failing)
        self.assertIsNone(state.last_grace_failure_at)

    def test_failure_at_grace_expiry_is_confirmed(self):
        state = _run([(day, True) for day in range(0, 15)])
        self.assertTrue(state.grace_failing)
        self.assertEqual(state.last_grace_failure_at, DAY_ZERO + timedelta(days=14))

    def test_recovery_within_grace_resets_the_streak(self):
        state = _run([(0, True), (1, True), (2, False)])
        self.assertFalse(state.raw_failing)
        self.assertFalse(state.grace_failing)
        self.assertIsNone(state.first_raw_failure_at)
        # History is kept.
        self.assertEqual(state.last_raw_failure_at, DAY_ZERO + timedelta(days=1))

    def test_streak_restarts_after_recovery(self):
        """A new streak gets a full grace period, it does not resume the old one."""
        days = [(day, True) for day in range(0, 10)]
        days += [(10, False)]
        days += [(day, True) for day in range(11, 20)]
        state = _run(days)
        self.assertTrue(state.raw_failing)
        self.assertFalse(state.grace_failing)
        self.assertEqual(state.first_raw_failure_at, DAY_ZERO + timedelta(days=11))

    def test_no_grace_period_confirms_immediately(self):
        state = _run([(0, True)], grace_period=None)
        self.assertTrue(state.grace_failing)
        self.assertEqual(state.last_grace_failure_at, DAY_ZERO)


class TestReliabilityWindow(unittest.TestCase):
    def test_confirmed_failure_persists_after_recovery(self):
        days = [(day, True) for day in range(0, 15)] + [(15, False)]
        state = _run(days)
        self.assertFalse(state.raw_failing)
        self.assertTrue(
            state.grace_failing, "a confirmed failure must hold through the window"
        )

    def test_criterion_clears_once_the_window_passes(self):
        days = [(day, True) for day in range(0, 15)]
        days += [(15, False), (15 + RELIABILITY_WINDOW.days, False)]
        self.assertFalse(_run(days).grace_failing)

    def test_criterion_still_failing_just_inside_the_window(self):
        days = [(day, True) for day in range(0, 15)]
        days += [(15, False), (14 + RELIABILITY_WINDOW.days, False)]
        self.assertTrue(_run(days).grace_failing)

    def test_no_window_tracks_current_state_only(self):
        """Official's shape: no grace, no window, clears as soon as the feed recovers."""
        state = _run(
            [(0, True), (1, False)], grace_period=None, reliability_window=None
        )
        self.assertFalse(state.grace_failing)
        self.assertIsNotNone(state.last_grace_failure_at, "history is still recorded")


class TestIdempotency(unittest.TestCase):
    def test_same_timestamp_twice_produces_the_same_state(self):
        """A re-run for the same instant must not compound a failure streak."""
        once = _run([(0, True), (1, True)])
        twice = _run([(1, True)], state=once)
        self.assertEqual(once.first_raw_failure_at, twice.first_raw_failure_at)
        self.assertEqual(once.last_raw_failure_at, twice.last_raw_failure_at)
        self.assertEqual(once.grace_failing, twice.grace_failing)

    def test_state_is_not_mutated_in_place(self):
        state = _run([(0, True)])
        _run([(1, True)], state=state)
        self.assertEqual(state.last_raw_failure_at, DAY_ZERO)


class TestStateShape(unittest.TestCase):
    def test_state_carries_feed_id_and_criterion(self):
        state = _run([(0, True)])
        self.assertEqual(state.feed_id, FEED_ID)
        self.assertEqual(state.criterion, SealCriterionName.AVAILABLE)

    def test_state_defaults_are_all_none(self):
        state = SealCriterionState(
            feed_id=FEED_ID, criterion=SealCriterionName.OFFICIAL
        )
        self.assertIsNone(state.raw_failing)
        self.assertIsNone(state.grace_failing)
        self.assertIsNone(state.evaluated_at)


if __name__ == "__main__":
    unittest.main()
