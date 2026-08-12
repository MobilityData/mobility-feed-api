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

from tasks.seal_of_reliability.criteria import PROBATION_PERIOD, SealCriterionName
from tasks.seal_of_reliability.evaluators.base import CriterionObservation
from tasks.seal_of_reliability.state_machine import SealCriterionState, transition

DAY_ZERO = datetime(2026, 1, 1, tzinfo=timezone.utc)
FEED_ID = "feed-1"

# Official, the first criterion implemented, has neither a grace period nor probation, so it
# exercises almost none of the state machine. These tests drive a synthetic criterion that
# has both.
GRACE = timedelta(days=14)


def _day(offset: int) -> datetime:
    return DAY_ZERO + timedelta(days=offset)


def _observation(observed_pass, criterion=SealCriterionName.AVAILABLE):
    return CriterionObservation(
        criterion=criterion, observed_pass=observed_pass, reason="test"
    )


def _run(days, grace_period=GRACE, probation_period=PROBATION_PERIOD, state=None):
    """Apply one verdict per entry in `days`: (day offset, observed_pass)."""
    for offset, observed_pass in days:
        state = transition(
            prev=state,
            observation=_observation(observed_pass),
            grace_period=grace_period,
            probation_period=probation_period,
            now=_day(offset),
            feed_id=FEED_ID,
        )
    return state


def _failing(start, end):
    """Observed failures on every day in [start, end)."""
    return [(day, False) for day in range(start, end)]


class TestNotEvaluable(unittest.TestCase):
    def test_none_verdict_leaves_state_untouched(self):
        """A criterion that cannot be evaluated must not change anything."""
        state = _run([(0, False)])
        unchanged = transition(
            prev=state,
            observation=_observation(None),
            grace_period=GRACE,
            probation_period=PROBATION_PERIOD,
            now=_day(1),
        )
        self.assertIs(unchanged, state)

    def test_none_verdict_with_no_previous_state_stays_none(self):
        """No row is created, so `observed_pass IS NULL` keeps meaning never evaluated."""
        self.assertIsNone(
            transition(
                prev=None,
                observation=_observation(None),
                grace_period=GRACE,
                probation_period=PROBATION_PERIOD,
                now=DAY_ZERO,
                feed_id=FEED_ID,
            )
        )

    def test_missing_feed_id_without_previous_state_raises(self):
        with self.assertRaises(ValueError):
            transition(
                prev=None,
                observation=_observation(False),
                grace_period=GRACE,
                probation_period=PROBATION_PERIOD,
                now=DAY_ZERO,
            )


class TestGracePeriod(unittest.TestCase):
    def test_first_evaluation_passes_immediately(self):
        """No observation period to serve: a passing first verdict is a confirmed pass."""
        state = _run([(0, True)])
        self.assertTrue(state.observed_pass)
        self.assertTrue(state.confirmed_pass)
        self.assertIsNone(state.first_observed_failure_at)
        self.assertIsNone(state.probation_start)

    def test_first_evaluation_gets_no_grace_period(self):
        """A criterion never seen to pass has no earned pass for the grace period to hold."""
        state = _run([(0, False)])
        self.assertFalse(state.observed_pass)
        self.assertFalse(state.confirmed_pass)
        self.assertEqual(state.last_confirmed_failure_at, DAY_ZERO)

    def test_failure_within_grace_is_not_confirmed(self):
        state = _run([(0, True)] + _failing(1, 14))
        self.assertFalse(state.observed_pass)
        self.assertTrue(state.confirmed_pass, "still inside the grace period")
        self.assertIsNone(state.last_confirmed_failure_at)

    def test_failure_at_grace_expiry_is_confirmed(self):
        state = _run([(0, True)] + _failing(1, 16))
        self.assertFalse(state.confirmed_pass)
        self.assertEqual(state.last_confirmed_failure_at, _day(15))

    def test_recovery_is_immediate(self):
        """The first day with an observed pass clears the status, with no wait."""
        state = _run([(0, True)] + _failing(1, 20) + [(20, True)])
        self.assertTrue(state.confirmed_pass)
        self.assertIsNone(state.first_observed_failure_at, "the streak is cleared")
        self.assertEqual(state.last_observed_failure_at, _day(19), "history is kept")
        self.assertEqual(state.last_confirmed_failure_at, _day(19))

    def test_streak_restarts_after_recovery(self):
        """A new streak gets a full grace period, it does not resume the old one."""
        days = [(0, True)] + _failing(1, 10) + [(10, True)] + _failing(11, 20)
        state = _run(days)
        self.assertFalse(state.observed_pass)
        self.assertTrue(state.confirmed_pass)
        self.assertEqual(state.first_observed_failure_at, _day(11))

    def test_no_grace_period_confirms_immediately(self):
        state = _run([(0, True), (1, False)], grace_period=None)
        self.assertFalse(state.confirmed_pass)
        self.assertEqual(state.last_confirmed_failure_at, _day(1))


class TestProbation(unittest.TestCase):
    def test_a_clean_first_evaluation_opens_no_probation(self):
        """Probation is opened only by a recovery, and this is not one."""
        self.assertIsNone(_run([(0, True)]).probation_start)
        self.assertIsNone(_run([(0, True), (1, True), (2, True)]).probation_start)

    def test_a_blip_inside_grace_does_not_open_probation(self):
        """Off probation, a failure absorbed by the grace period costs nothing."""
        state = _run([(0, True), (1, False), (2, True)])
        self.assertTrue(state.confirmed_pass)
        self.assertIsNone(state.probation_start)

    def test_recovery_from_a_confirmed_failure_opens_probation(self):
        state = _run([(0, True)] + _failing(1, 16) + [(16, True)])
        self.assertTrue(state.confirmed_pass, "the status clears the same day")
        self.assertEqual(
            state.probation_start, _day(16), "but probation runs from the repair day"
        )

    def test_probation_starts_the_day_after_the_last_failure(self):
        """Stamped at tomorrow every failing day, so it lands on the day of repair."""
        state = _run([(0, True)] + _failing(1, 16))
        self.assertEqual(state.probation_start, _day(16))

    def test_probation_ends_after_the_full_period(self):
        days = [(0, True)] + _failing(1, 16) + [(16, True)]
        served = _run(days + [(16 + PROBATION_PERIOD.days, True)])
        self.assertIsNone(served.probation_start)

    def test_probation_still_open_one_day_short(self):
        days = [(0, True)] + _failing(1, 16) + [(16, True)]
        state = _run(days + [(15 + PROBATION_PERIOD.days, True)])
        self.assertEqual(state.probation_start, _day(16))

    def test_a_failure_the_day_before_probation_ends_restarts_the_whole_period(self):
        """Nearly served is not served: the count goes back to zero, not to one day left."""
        # Probation runs from D16, so it would have ended on D196.
        served = [(0, True)] + _failing(1, 16) + [(16, True)]

        state = _run(served + [(195, False), (196, True)])
        self.assertEqual(
            state.probation_start, _day(196), "restarted on the repair day"
        )

        self.assertIsNotNone(
            _run(served + [(195, False), (196, True), (375, True)]).probation_start,
            "the original D196 end date is gone",
        )
        self.assertIsNone(
            _run(served + [(195, False), (196, True), (376, True)]).probation_start,
            "it ends 180 days after the restart instead",
        )

    def test_a_failure_on_the_last_day_of_probation_restarts_it(self):
        """Expiry is only ever checked on a passing day, so a failure that day wins."""
        served = [(0, True)] + _failing(1, 16) + [(16, True)]
        state = _run(served + [(196, False)])
        self.assertEqual(state.probation_start, _day(197))

    def test_two_runs_on_the_same_failing_day_stamp_the_same_start(self):
        """The `+1 day` is stamped from the UTC day, so the hour of the run cannot shift it."""
        state = None
        for moment in (_day(1) + timedelta(hours=2), _day(1) + timedelta(hours=23)):
            state = transition(
                prev=state,
                observation=_observation(False),
                grace_period=None,
                probation_period=PROBATION_PERIOD,
                now=moment,
                feed_id=FEED_ID,
            )
        self.assertEqual(state.probation_start, _day(2))

    def test_an_observed_failure_during_probation_restarts_it(self):
        """Confirmed or not: during probation any failure costs the whole count."""
        days = [(0, True)] + _failing(1, 16) + [(16, True), (100, False), (101, True)]
        state = _run(days)
        self.assertTrue(state.confirmed_pass, "the blip stayed inside the grace period")
        self.assertEqual(state.probation_start, _day(101))

    def test_a_criterion_without_probation_never_gets_one(self):
        """Official's shape: it clears outright as soon as the feed recovers."""
        state = _run(
            [(0, True)] + _failing(1, 30) + [(30, True)],
            grace_period=None,
            probation_period=None,
        )
        self.assertTrue(state.confirmed_pass)
        self.assertIsNone(state.probation_start)

    def test_probation_uses_day_granularity(self):
        """A run at any hour stamps the same start, so the period is not shifted."""
        midday = _day(1) + timedelta(hours=13, minutes=27)
        state = transition(
            prev=None,
            observation=_observation(False),
            grace_period=None,
            probation_period=PROBATION_PERIOD,
            now=midday,
            feed_id=FEED_ID,
        )
        self.assertEqual(state.probation_start, _day(2))


class TestIdempotency(unittest.TestCase):
    def test_same_timestamp_twice_produces_the_same_state(self):
        """A re-run for the same instant must not compound a failure streak."""
        once = _run([(0, True), (1, False), (2, False)])
        twice = _run([(2, False)], state=once)
        self.assertEqual(
            once.first_observed_failure_at, twice.first_observed_failure_at
        )
        self.assertEqual(once.last_observed_failure_at, twice.last_observed_failure_at)
        self.assertEqual(once.confirmed_pass, twice.confirmed_pass)
        self.assertEqual(once.probation_start, twice.probation_start)

    def test_state_is_not_mutated_in_place(self):
        state = _run([(0, False)])
        _run([(1, False)], state=state)
        self.assertEqual(state.last_observed_failure_at, DAY_ZERO)


class TestStateShape(unittest.TestCase):
    def test_state_carries_feed_id_and_criterion(self):
        state = _run([(0, False)])
        self.assertEqual(state.feed_id, FEED_ID)
        self.assertEqual(state.criterion, SealCriterionName.AVAILABLE)

    def test_state_defaults_are_all_none(self):
        state = SealCriterionState(
            feed_id=FEED_ID, criterion=SealCriterionName.OFFICIAL
        )
        self.assertIsNone(state.observed_pass)
        self.assertIsNone(state.confirmed_pass)
        self.assertIsNone(state.evaluated_at)
        self.assertIsNone(state.probation_start)


if __name__ == "__main__":
    unittest.main()
