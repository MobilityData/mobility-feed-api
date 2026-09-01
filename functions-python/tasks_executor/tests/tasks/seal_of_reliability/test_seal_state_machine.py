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

from shared.common.seal_criteria import (
    PROBATION_PERIOD,
    CriterionPhase,
    CriterionStatus,
    SealCriterionName,
)
from tasks.seal_of_reliability.evaluators.base import CriterionObservation
from tasks.seal_of_reliability.state_machine import (
    SealCriterionState,
    phase,
    transition,
)

DAY_ZERO = datetime(2026, 1, 1, tzinfo=timezone.utc)
FEED_ID = "feed-1"

# Official, the first criterion implemented, has neither a grace period nor probation, so it
# exercises almost none of the state machine. These tests drive a synthetic criterion that
# has both.
GRACE = timedelta(days=14)

PASS = CriterionStatus.PASS
FAIL = CriterionStatus.FAIL


def _day(offset: int) -> datetime:
    return DAY_ZERO + timedelta(days=offset)


def _observation(status, criterion=SealCriterionName.AVAILABLE):
    return CriterionObservation(
        criterion=criterion, observed_status=status, reason="test"
    )


def _run(days, grace_period=GRACE, probation_period=PROBATION_PERIOD, state=None):
    """Apply one observation per entry in `days`: (day offset, observed_status)."""
    for offset, status in days:
        state = transition(
            prev=state,
            observation=_observation(status),
            grace_period=grace_period,
            probation_period=probation_period,
            now=_day(offset),
            feed_id=FEED_ID,
        )
    return state


def _failing(start, end):
    """Observed failures on every day in [start, end)."""
    return [(day, FAIL) for day in range(start, end)]


class TestNoVerdict(unittest.TestCase):
    """UNKNOWN and NOT_APPLICABLE both withhold a verdict, in opposite directions."""

    def test_unknown_keeps_the_stored_confirmed_status(self):
        """An outage must freeze a criterion, never waive it.

        Leaving `confirmed_status` alone is what keeps the criterion in the roll-up with the
        verdict it already had.
        """
        before = _run([(0, PASS)])
        after = _run([(1, CriterionStatus.UNKNOWN)], state=before)
        self.assertIs(after.observed_status, CriterionStatus.UNKNOWN)
        self.assertIs(after.confirmed_status, PASS, "the last verdict still stands")

    def test_unknown_records_the_attempt_but_not_a_verdict(self):
        """`evaluated_at` moves, `last_verdict_at` does not — that is the whole split."""
        before = _run([(0, PASS)])
        after = _run([(1, CriterionStatus.UNKNOWN)], state=before)
        self.assertEqual(after.evaluated_at, _day(1), "we did run the check")
        self.assertEqual(
            after.last_verdict_at, before.last_verdict_at, "but got no verdict"
        )

    def test_unknown_leaves_probation_and_the_failure_timestamps_alone(self):
        serving = _run([(0, PASS)] + _failing(1, 16) + [(16, PASS)])
        after = _run([(17, CriterionStatus.UNKNOWN)], state=serving)
        self.assertEqual(after.probation_start, serving.probation_start)
        self.assertEqual(
            after.first_observed_failure_at, serving.first_observed_failure_at
        )
        self.assertEqual(
            after.last_observed_failure_at, serving.last_observed_failure_at
        )
        self.assertEqual(
            after.last_confirmed_failure_at, serving.last_confirmed_failure_at
        )

    def test_unknown_with_no_previous_state_creates_a_row_with_no_verdict(self):
        """A row is written so the attempt is recorded, but it holds no verdict.

        `confirmed_status` stays NEVER_EVALUATED, which keeps the criterion out of the roll-up,
        and `last_verdict_at` stays NULL, which is what still denies it a grace period.
        """
        state = _run([(0, CriterionStatus.UNKNOWN)])
        self.assertIs(state.observed_status, CriterionStatus.UNKNOWN)
        self.assertIs(state.confirmed_status, CriterionStatus.NEVER_EVALUATED)
        self.assertIsNone(state.last_verdict_at)
        self.assertEqual(state.evaluated_at, DAY_ZERO)

    def test_not_applicable_withdraws_the_criterion(self):
        """Unlike UNKNOWN, this overwrites `confirmed_status` so the criterion stops counting."""
        before = _run([(0, PASS)])
        after = _run([(1, CriterionStatus.NOT_APPLICABLE)], state=before)
        self.assertIs(after.observed_status, CriterionStatus.NOT_APPLICABLE)
        self.assertIs(after.confirmed_status, CriterionStatus.NOT_APPLICABLE)
        self.assertFalse(after.confirmed_status.is_verdict)

    def test_not_applicable_freezes_probation_rather_than_clearing_it(self):
        """If the criterion becomes applicable again, its penalty is still there."""
        serving = _run([(0, PASS)] + _failing(1, 16) + [(16, PASS)])
        after = _run([(17, CriterionStatus.NOT_APPLICABLE)], state=serving)
        self.assertEqual(after.probation_start, serving.probation_start)

    def test_no_verdict_never_moves_last_verdict_at(self):
        for status in (CriterionStatus.UNKNOWN, CriterionStatus.NOT_APPLICABLE):
            with self.subTest(status=status):
                before = _run([(0, FAIL)])
                after = _run([(5, status)], state=before)
                self.assertEqual(after.last_verdict_at, DAY_ZERO)

    def test_missing_feed_id_without_previous_state_raises(self):
        with self.assertRaises(ValueError):
            transition(
                prev=None,
                observation=_observation(FAIL),
                grace_period=GRACE,
                probation_period=PROBATION_PERIOD,
                now=DAY_ZERO,
            )


class TestGracePeriod(unittest.TestCase):
    def test_first_evaluation_passes_immediately(self):
        """No observation period to serve: a passing first verdict is a confirmed pass."""
        state = _run([(0, PASS)])
        self.assertIs(state.observed_status, PASS)
        self.assertIs(state.confirmed_status, PASS)
        self.assertIsNone(state.first_observed_failure_at)
        self.assertIsNone(state.probation_start)
        self.assertEqual(state.last_verdict_at, DAY_ZERO)

    def test_first_evaluation_gets_no_grace_period(self):
        """A criterion never seen to pass has no earned pass for the grace period to hold."""
        state = _run([(0, FAIL)])
        self.assertIs(state.observed_status, FAIL)
        self.assertIs(state.confirmed_status, FAIL)
        self.assertEqual(state.last_confirmed_failure_at, DAY_ZERO)

    def test_a_row_of_only_unknowns_is_still_a_first_evaluation(self):
        """`first_evaluation` comes from `last_verdict_at`, not from the status column.

        Compliant on a feed that has never had a validation report: every run so far wrote
        UNKNOWN, so `observed_status` has left NEVER_EVALUATED. The criterion has still never
        produced a verdict and is still not entitled to a grace period.
        """
        attempted = _run([(0, CriterionStatus.UNKNOWN), (1, CriterionStatus.UNKNOWN)])
        self.assertIsNot(attempted.observed_status, CriterionStatus.NEVER_EVALUATED)

        first = _run([(2, FAIL)], state=attempted)
        self.assertIs(first.confirmed_status, FAIL, "no grace on a first verdict")

    def test_failure_within_grace_is_not_confirmed(self):
        state = _run([(0, PASS)] + _failing(1, 14))
        self.assertIs(state.observed_status, FAIL)
        self.assertIs(state.confirmed_status, PASS, "still inside the grace period")
        self.assertIsNone(state.last_confirmed_failure_at)
        self.assertIs(phase(state), CriterionPhase.IN_GRACE_PERIOD)

    def test_failure_at_grace_expiry_is_confirmed(self):
        state = _run([(0, PASS)] + _failing(1, 16))
        self.assertIs(state.confirmed_status, FAIL)
        self.assertEqual(state.last_confirmed_failure_at, _day(15))

    def test_recovery_is_immediate(self):
        """The first day with an observed pass clears the status, with no wait."""
        state = _run([(0, PASS)] + _failing(1, 20) + [(20, PASS)])
        self.assertIs(state.confirmed_status, PASS)
        self.assertIsNone(state.first_observed_failure_at, "the streak is cleared")
        self.assertEqual(state.last_observed_failure_at, _day(19), "history is kept")
        self.assertEqual(state.last_confirmed_failure_at, _day(19))

    def test_streak_restarts_after_recovery(self):
        """A new streak gets a full grace period, it does not resume the old one."""
        days = [(0, PASS)] + _failing(1, 10) + [(10, PASS)] + _failing(11, 20)
        state = _run(days)
        self.assertIs(state.observed_status, FAIL)
        self.assertIs(state.confirmed_status, PASS)
        self.assertEqual(state.first_observed_failure_at, _day(11))

    def test_no_grace_period_confirms_immediately(self):
        state = _run([(0, PASS), (1, FAIL)], grace_period=None)
        self.assertIs(state.confirmed_status, FAIL)
        self.assertEqual(state.last_confirmed_failure_at, _day(1))


class TestProbationSuspendsGrace(unittest.TestCase):
    """Probation is a penalty, and the grace period is a privilege it forfeits."""

    def test_a_failure_during_probation_is_confirmed_the_same_day(self):
        serving = _run([(0, PASS)] + _failing(1, 16) + [(16, PASS)])
        self.assertIs(phase(serving), CriterionPhase.ON_PROBATION)

        blip = _run([(17, FAIL)], state=serving)
        self.assertIs(
            blip.confirmed_status,
            FAIL,
            "on probation the grace period must not absorb the failure",
        )
        self.assertEqual(blip.last_confirmed_failure_at, _day(17))

    def test_the_same_failure_off_probation_is_absorbed(self):
        """The contrast: identical observation, no probation, held by the grace period."""
        clean = _run([(0, PASS)])
        blip = _run([(1, FAIL)], state=clean)
        self.assertIs(blip.confirmed_status, PASS)

    def test_grace_returns_once_probation_is_served(self):
        served = _run(
            [(0, PASS)]
            + _failing(1, 16)
            + [(16, PASS), (16 + PROBATION_PERIOD.days, PASS)]
        )
        self.assertIs(phase(served), CriterionPhase.STEADY)

        blip = _run([(17 + PROBATION_PERIOD.days, FAIL)], state=served)
        self.assertIs(blip.confirmed_status, PASS, "the privilege is back")

    def test_the_two_phases_are_never_both_true(self):
        """IN_GRACE_PERIOD needs a confirmed pass mid-streak, which probation denies."""
        serving = _run([(0, PASS)] + _failing(1, 16) + [(16, PASS)])
        during = _run([(17, FAIL)], state=serving)
        self.assertIs(phase(during), CriterionPhase.ON_PROBATION)
        self.assertIsNot(phase(during), CriterionPhase.IN_GRACE_PERIOD)


class TestProbation(unittest.TestCase):
    def test_a_clean_first_evaluation_opens_no_probation(self):
        """Probation is opened only by a recovery, and this is not one."""
        self.assertIsNone(_run([(0, PASS)]).probation_start)
        self.assertIsNone(_run([(0, PASS), (1, PASS), (2, PASS)]).probation_start)

    def test_a_blip_inside_grace_does_not_open_probation(self):
        """Off probation, a failure absorbed by the grace period costs nothing."""
        state = _run([(0, PASS), (1, FAIL), (2, PASS)])
        self.assertIs(state.confirmed_status, PASS)
        self.assertIsNone(state.probation_start)

    def test_recovery_from_a_confirmed_failure_opens_probation(self):
        state = _run([(0, PASS)] + _failing(1, 16) + [(16, PASS)])
        self.assertIs(state.confirmed_status, PASS, "the status clears the same day")
        self.assertEqual(
            state.probation_start, _day(16), "but probation runs from the repair day"
        )

    def test_probation_starts_the_day_after_the_last_failure(self):
        """Stamped at tomorrow every failing day, so it lands on the day of repair."""
        state = _run([(0, PASS)] + _failing(1, 16))
        self.assertEqual(state.probation_start, _day(16))

    def test_probation_start_may_be_in_the_future_during_a_streak(self):
        """It reads as "on probation from" rather than "since"."""
        state = _run([(0, PASS)] + _failing(1, 16))
        self.assertGreater(state.probation_start, _day(15))
        self.assertIs(phase(state), CriterionPhase.ON_PROBATION)

    def test_probation_ends_after_the_full_period(self):
        days = [(0, PASS)] + _failing(1, 16) + [(16, PASS)]
        served = _run(days + [(16 + PROBATION_PERIOD.days, PASS)])
        self.assertIsNone(served.probation_start)
        self.assertIs(phase(served), CriterionPhase.STEADY)

    def test_probation_still_open_one_day_short(self):
        days = [(0, PASS)] + _failing(1, 16) + [(16, PASS)]
        state = _run(days + [(15 + PROBATION_PERIOD.days, PASS)])
        self.assertEqual(state.probation_start, _day(16))

    def test_a_failure_the_day_before_probation_ends_restarts_the_whole_period(self):
        """Nearly served is not served: the count goes back to zero, not to one day left."""
        # Probation runs from D16, so it would have ended on D196.
        served = [(0, PASS)] + _failing(1, 16) + [(16, PASS)]

        state = _run(served + [(195, FAIL), (196, PASS)])
        self.assertEqual(
            state.probation_start, _day(196), "restarted on the repair day"
        )

        self.assertIsNotNone(
            _run(served + [(195, FAIL), (196, PASS), (375, PASS)]).probation_start,
            "the original D196 end date is gone",
        )
        self.assertIsNone(
            _run(served + [(195, FAIL), (196, PASS), (376, PASS)]).probation_start,
            "it ends 180 days after the restart instead",
        )

    def test_a_failure_on_the_last_day_of_probation_restarts_it(self):
        """Expiry is only ever checked on a passing day, so a failure that day wins."""
        served = [(0, PASS)] + _failing(1, 16) + [(16, PASS)]
        state = _run(served + [(196, FAIL)])
        self.assertEqual(state.probation_start, _day(197))

    def test_two_runs_on_the_same_failing_day_stamp_the_same_start(self):
        """The `+1 day` is stamped from the UTC day, so the hour of the run cannot shift it."""
        state = None
        for moment in (_day(1) + timedelta(hours=2), _day(1) + timedelta(hours=23)):
            state = transition(
                prev=state,
                observation=_observation(FAIL),
                grace_period=None,
                probation_period=PROBATION_PERIOD,
                now=moment,
                feed_id=FEED_ID,
            )
        self.assertEqual(state.probation_start, _day(2))

    def test_an_observed_failure_during_probation_restarts_it(self):
        """During probation any failure costs the whole count.

        It is also a confirmed failure the same day, since probation suspends the grace
        period — off probation the same blip would have been absorbed.
        """
        days = [(0, PASS)] + _failing(1, 16) + [(16, PASS), (100, FAIL), (101, PASS)]
        state = _run(days)
        self.assertEqual(state.probation_start, _day(101))
        self.assertEqual(
            state.last_confirmed_failure_at,
            _day(100),
            "the blip was confirmed, not held by grace",
        )

    def test_a_criterion_without_probation_never_gets_one(self):
        """Official's shape: it clears outright as soon as the feed recovers."""
        state = _run(
            [(0, PASS)] + _failing(1, 30) + [(30, PASS)],
            grace_period=None,
            probation_period=None,
        )
        self.assertIs(state.confirmed_status, PASS)
        self.assertIsNone(state.probation_start)
        self.assertIs(phase(state), CriterionPhase.STEADY)

    def test_probation_uses_day_granularity(self):
        """A run at any hour stamps the same start, so the period is not shifted."""
        midday = _day(1) + timedelta(hours=13, minutes=27)
        state = transition(
            prev=None,
            observation=_observation(FAIL),
            grace_period=None,
            probation_period=PROBATION_PERIOD,
            now=midday,
            feed_id=FEED_ID,
        )
        self.assertEqual(state.probation_start, _day(2))


class TestPhase(unittest.TestCase):
    def test_no_row_is_steady(self):
        """A criterion with no history is not on probation and has no streak running."""
        self.assertIs(phase(None), CriterionPhase.STEADY)

    def test_a_clean_criterion_is_steady(self):
        self.assertIs(phase(_run([(0, PASS)])), CriterionPhase.STEADY)

    def test_a_confirmed_failure_without_probation_is_steady(self):
        """Official's shape again: nothing is debouncing it in either direction."""
        state = _run([(0, PASS), (1, FAIL)], grace_period=None, probation_period=None)
        self.assertIs(state.confirmed_status, FAIL)
        self.assertIs(phase(state), CriterionPhase.STEADY)

    def test_a_recovered_criterion_still_serving_is_on_probation(self):
        """The case `confirmed_status` cannot express on its own: a pass that denies the seal."""
        state = _run([(0, PASS)] + _failing(1, 16) + [(16, PASS)])
        self.assertIs(state.confirmed_status, PASS)
        self.assertIs(phase(state), CriterionPhase.ON_PROBATION)


class TestIdempotency(unittest.TestCase):
    def test_same_timestamp_twice_produces_the_same_state(self):
        """A re-run for the same instant must not compound a failure streak."""
        once = _run([(0, PASS), (1, FAIL), (2, FAIL)])
        twice = _run([(2, FAIL)], state=once)
        self.assertEqual(
            once.first_observed_failure_at, twice.first_observed_failure_at
        )
        self.assertEqual(once.last_observed_failure_at, twice.last_observed_failure_at)
        self.assertIs(once.confirmed_status, twice.confirmed_status)
        self.assertEqual(once.probation_start, twice.probation_start)

    def test_a_same_day_rerun_does_not_deny_an_earned_grace_period(self):
        """`last_verdict_at` moving to today must not make today look like a first evaluation."""
        once = _run([(0, PASS), (1, FAIL)])
        self.assertIs(once.confirmed_status, PASS)
        twice = _run([(1, FAIL)], state=once)
        self.assertIs(twice.confirmed_status, PASS, "still inside the grace period")

    def test_state_is_not_mutated_in_place(self):
        state = _run([(0, FAIL)])
        _run([(1, FAIL)], state=state)
        self.assertEqual(state.last_observed_failure_at, DAY_ZERO)


class TestStateShape(unittest.TestCase):
    def test_state_carries_feed_id_and_criterion(self):
        state = _run([(0, FAIL)])
        self.assertEqual(state.feed_id, FEED_ID)
        self.assertEqual(state.criterion, SealCriterionName.AVAILABLE)

    def test_a_fresh_state_has_never_been_evaluated(self):
        state = SealCriterionState(
            feed_id=FEED_ID, criterion=SealCriterionName.OFFICIAL
        )
        self.assertIs(state.observed_status, CriterionStatus.NEVER_EVALUATED)
        self.assertIs(state.confirmed_status, CriterionStatus.NEVER_EVALUATED)
        self.assertIsNone(state.evaluated_at)
        self.assertIsNone(state.last_verdict_at)
        self.assertIsNone(state.probation_start)

    def test_is_verdict_only_covers_pass_and_fail(self):
        for status in (PASS, FAIL):
            self.assertTrue(status.is_verdict, status)
        for status in (
            CriterionStatus.UNKNOWN,
            CriterionStatus.NEVER_EVALUATED,
            CriterionStatus.NOT_APPLICABLE,
        ):
            self.assertFalse(status.is_verdict, status)


class TestGraceExpiresOnAnUnknownDay(unittest.TestCase):
    """A streak whose grace runs out on a day that produced no reading.

    Found by marching a feed locally: fourteen failures, UNKNOWN across the day grace
    expired, then a pass — and nothing was confirmed, so the outage left no trace.
    """

    def _grace_expired_under_unknowns(self):
        # Grace runs 14 days from the streak start on day 1, so day 15 both expires it and
        # is the first day with no reading.
        return _run(
            [(0, PASS)]
            + _failing(1, 15)
            + [
                (15, CriterionStatus.UNKNOWN),
                (16, CriterionStatus.UNKNOWN),
                (17, CriterionStatus.UNKNOWN),
            ]
        )

    def test_the_streak_start_survives_the_unknown_days(self):
        """The unknowns neither reset nor forget the streak."""
        state = self._grace_expired_under_unknowns()
        self.assertEqual(state.first_observed_failure_at, _day(1))
        self.assertEqual(
            state.last_verdict_at,
            _day(14),
            "no verdict since the last observed failure",
        )

    def test_a_streak_past_its_grace_confirms_without_a_fresh_verdict(self):
        state = self._grace_expired_under_unknowns()
        self.assertIs(
            state.confirmed_status,
            FAIL,
            "17 days into a streak whose grace expired on day 15",
        )

    def test_a_pass_cannot_forgive_a_streak_that_outlived_its_grace(self):
        """Otherwise one pass after the unknowns erases the whole outage."""
        recovered = _run([(18, PASS)], state=self._grace_expired_under_unknowns())
        self.assertIsNotNone(
            recovered.last_confirmed_failure_at,
            "a fortnight of failure left no record at all",
        )


class TestProbationAcrossAnUnknownDay(unittest.TestCase):
    """`probation_start` when a confirmed failure is followed by no reading.

    A confirmed streak re-stamps it to the following day. An UNKNOWN day leaves it alone,
    which makes that day the first of probation and counts it toward the term.
    """

    def _confirmed_then_unknown(self):
        streaking = _run([(0, PASS)] + _failing(1, 17))
        return streaking, _run([(17, CriterionStatus.UNKNOWN)], state=streaking)

    def test_the_streak_leaves_probation_stamped_for_the_following_day(self):
        streaking, _ = self._confirmed_then_unknown()
        self.assertIs(streaking.confirmed_status, FAIL)
        self.assertEqual(streaking.probation_start, _day(17))

    def test_an_unknown_day_does_not_push_probation_forward(self):
        streaking, after = self._confirmed_then_unknown()
        self.assertEqual(
            after.probation_start,
            streaking.probation_start,
            "no verdict re-stamps it, so probation begins on the unknown day",
        )
        self.assertIs(after.confirmed_status, FAIL, "the last verdict still stands")
        self.assertIs(phase(after), CriterionPhase.ON_PROBATION)

    def test_the_unknown_day_counts_toward_serving_probation(self):
        """A day with no reading still serves the term."""
        _, after = self._confirmed_then_unknown()
        served = _run([(17 + PROBATION_PERIOD.days, PASS)], state=after)
        self.assertIsNone(served.probation_start, "the term was served")
        self.assertIs(phase(served), CriterionPhase.STEADY)


class TestNotApplicableRetiresTheStreak(unittest.TestCase):
    """A streak frozen by NOT_APPLICABLE must not be confirmed by a later UNKNOWN day.

    The grace-expiry check on the UNKNOWN path reads `first_observed_failure_at` against the
    clock. A streak left open across a not-applicable spell would be confirmed by the first
    day with no reading, on failures nobody has observed since — which is why NOT_APPLICABLE
    closes the streak.

    The reachable case is Fresh (future coverage) on a feed whose `seasonal` flag is set and
    later cleared: it answers NOT_APPLICABLE throughout the season, and UNKNOWN on the first
    day after the flag goes if the feed has no dataset.
    """

    def _one_failure_then_a_seasonal_spell(self):
        """Day 1 fails inside grace, days 2-59 do not apply, day 60 has no reading."""
        return _run(
            [(0, PASS), (1, FAIL)]
            + [(day, CriterionStatus.NOT_APPLICABLE) for day in range(2, 60)]
            + [(60, CriterionStatus.UNKNOWN)]
        )

    def test_the_criterion_stays_withdrawn(self):
        state = self._one_failure_then_a_seasonal_spell()
        self.assertIs(
            state.confirmed_status,
            CriterionStatus.NOT_APPLICABLE,
            "the one failure was 59 days ago and the spell retired it",
        )

    def test_the_retired_streak_carries_no_penalty(self):
        """Backdated to day 2, probation would run to day 182 and hold the seal down to it."""
        state = self._one_failure_then_a_seasonal_spell()
        self.assertIsNone(state.probation_start)
        self.assertIsNone(
            state.last_confirmed_failure_at,
            "the failure was absorbed by the grace period",
        )


if __name__ == "__main__":
    unittest.main()
