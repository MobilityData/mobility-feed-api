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
"""A day-scripted stand-in evaluator, and the tests proving it drives.

Only Official is implemented, and it has neither a grace period nor probation. So nothing
otherwise exercises the path-dependent behaviour a backfill (#1763) exists to reconstruct: a
failure streak debounced by a grace period, a confirmed failure, the probation that follows
recovery, and an UNKNOWN day that freezes the lot.

**It borrows the `official` enum value on purpose.** Official already has an evaluator, so no
future criterion implementation can collide with this fixture — unlike borrowing `compliant`
or `available`, whose real evaluators are still to be written (#1782, #1784). The grace and
probation values below are the harness's, chosen to exercise the state machine; the real
Official has neither, and nothing here should be read as its policy.

Why scripted by day rather than driven through the database, as the stand-ins in
`test_seal_updater_db.py` are: those read `ctx.official` and a test moves them by issuing an
UPDATE between runs. A backfill marches its days in memory with no writes in between, so a
criterion it can drive has to answer from `ctx.now` alone. `Script` is that — sets of failing,
unknown and not-applicable days fixed up front, replayed by advancing the clock.
"""

import unittest
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import FrozenSet, Iterable, Optional, Tuple
from unittest.mock import patch

from sqlalchemy import delete, select

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Feed, Gtfsfeed, SealCriterion
from tasks.seal_of_reliability.criteria import (
    PROBATION_PERIOD,
    CriterionStatus,
    SealCriterionName,
)
from tasks.seal_of_reliability.evaluators import CriterionEvaluator, OfficialEvaluator
from tasks.seal_of_reliability.seal_updater import update_seals
from test_shared.test_utils.database_utils import default_db_url

# The harness's debouncing values, not any criterion's published policy. 30 days is long
# enough that a streak has to be deliberate to outlast it, and short enough that a test can
# step over the boundary without marching a year.
TEST_GRACE = timedelta(days=30)

DAY_ZERO = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

PREFIX = "seal_sc_"
FEED = f"{PREFIX}scripted"

# Distinguishes "not given" from an explicit None, which means "this criterion has no grace
# period" and is a value a test may legitimately want to pass.
_UNSET = object()


def day(offset: int) -> datetime:
    """The run timestamp `offset` days after day zero."""
    return DAY_ZERO + timedelta(days=offset)


@dataclass(frozen=True)
class Script:
    """What the stand-in answers on each day, fixed before the run starts.

    Days named in none of the three sets pass. Built from offsets against an anchor — a
    feed's march start, usually — so a scenario reads in the same relative terms whatever
    day the window actually begins on.
    """

    failing: FrozenSet[date] = field(default_factory=frozenset)
    unknown: FrozenSet[date] = field(default_factory=frozenset)
    not_applicable: FrozenSet[date] = field(default_factory=frozenset)

    @classmethod
    def from_offsets(
        cls,
        anchor: date,
        failing: Iterable[int] = (),
        unknown: Iterable[int] = (),
        not_applicable: Iterable[int] = (),
    ) -> "Script":
        def days(offsets):
            return frozenset(anchor + timedelta(days=int(o)) for o in offsets)

        return cls(days(failing), days(unknown), days(not_applicable))

    def status_on(self, today: date) -> CriterionStatus:
        """Precedence matters: an input we could not read is never a failure."""
        if today in self.unknown:
            return CriterionStatus.UNKNOWN
        if today in self.not_applicable:
            return CriterionStatus.NOT_APPLICABLE
        if today in self.failing:
            return CriterionStatus.FAIL
        return CriterionStatus.PASS


class ScriptedEvaluator(CriterionEvaluator):
    """A stand-in whose verdict is a pure function of the day being evaluated.

    It files its rows under the `official` criterion — see the module docstring for why that
    name and not one of the unimplemented ones.

    **Its debouncing is not Official's.** The real `OfficialEvaluator` has `grace_period` and
    `probation_period` both `None`: it is a point-in-time check that flips the same day the
    flag moves, in either direction. This stand-in gives that name a 30-day grace period and
    the standard 180-day probation *for the duration of the test only*, because those are the
    mechanisms a backfill has to reconstruct and no implemented criterion has them yet.

    Nothing here changes the real evaluator. `registry()` patches the whole `EVALUATORS`
    list for the length of a `with` block, so the substitution cannot leak past it.
    """

    name = SealCriterionName.OFFICIAL
    grace_period = TEST_GRACE

    def __init__(
        self,
        script: Script,
        criterion: Optional[SealCriterionName] = None,
        grace_period=_UNSET,
        probation_period=_UNSET,
    ):
        self.script = script
        # Instance attributes shadow the class ones the job reads, so a test can vary the
        # policy per case without subclassing.
        if criterion is not None:
            self.name = criterion
        if grace_period is not _UNSET:
            self.grace_period = grace_period
        if probation_period is not _UNSET:
            self.probation_period = probation_period

    def _evaluate(self, ctx) -> Tuple[CriterionStatus, str]:
        today = ctx.now.astimezone(timezone.utc).date()
        status = self.script.status_on(today)
        return status, f"scripted: {status.value} on {today}"


@contextmanager
def registry(evaluator: ScriptedEvaluator):
    """Run with the stand-in as the only criterion.

    Sole occupant on purpose: `update_seals` treats a shorter evaluator list as a partial run
    and skips the has_seal roll-up, so patching the registry itself rather than filtering it
    is what keeps the seal in play. Patched in `seal_updater`, which is where both the nightly
    job and the backfill resolve the registry from.
    """
    with patch(
        "tasks.seal_of_reliability.seal_updater.EVALUATORS",
        [evaluator],
    ):
        yield


def cleanup(db_session, prefix: str = PREFIX):
    """Delete from `feed`, not `gtfsfeed`.

    Gtfsfeed is a joined-table subclass, so deleting the subclass leaves the parent row and
    the next insert collides on feed_pkey. The seal tables are ON DELETE CASCADE.
    """
    db_session.execute(delete(Feed).where(Feed.stable_id.like(f"{prefix}%")))
    db_session.commit()


def seed_feed(db_session, stable_id: str, created_at: datetime, official=True):
    db_session.add(
        Gtfsfeed(
            id=stable_id,
            stable_id=stable_id,
            data_type="gtfs",
            status="active",
            operational_status="published",
            official=official,
            created_at=created_at,
            producer_url=f"https://example.com/{stable_id}.zip",
        )
    )
    db_session.flush()


class ScriptedEvaluatorTestCase(unittest.TestCase):
    """Seeds one eligible feed and replays scripted days against it."""

    @with_db_session(db_url=default_db_url)
    def setUp(self, db_session):
        cleanup(db_session)
        seed_feed(db_session, FEED, DAY_ZERO - timedelta(days=400))
        db_session.commit()

    @with_db_session(db_url=default_db_url)
    def tearDown(self, db_session):
        cleanup(db_session)

    @staticmethod
    def run_days(script: Script, offsets) -> None:
        """Evaluate the feed once per day, in order, writing each day's state.

        A march done the slow way — through the database, one `update_seals` call per day —
        which is exactly what #1763's in-memory march has to reproduce.
        """
        with registry(ScriptedEvaluator(script)):
            for offset in offsets:
                update_seals(stable_feed_ids=[FEED], dry_run=False, now=day(offset))

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def state(db_session=None):
        return db_session.execute(
            select(SealCriterion.__table__).where(
                SealCriterion.__table__.c.feed_id == FEED,
                SealCriterion.__table__.c.criterion == SealCriterionName.OFFICIAL.value,
            )
        ).one()


class TestScriptDrivesTheEvaluator(unittest.TestCase):
    """The fixture itself, with no database in the way."""

    class _Ctx:
        def __init__(self, now):
            self.now = now
            self.feed_id = FEED
            self.stable_id = FEED

    def observed(self, script: Script, offset: int) -> CriterionStatus:
        return (
            ScriptedEvaluator(script).evaluate(self._Ctx(day(offset))).observed_status
        )

    def test_unnamed_days_pass(self):
        script = Script.from_offsets(DAY_ZERO.date(), failing=[3])
        self.assertIs(self.observed(script, 0), CriterionStatus.PASS)

    def test_named_days_fail(self):
        script = Script.from_offsets(DAY_ZERO.date(), failing=[3])
        self.assertIs(self.observed(script, 3), CriterionStatus.FAIL)

    def test_a_range_is_inclusive_of_both_ends(self):
        script = Script.from_offsets(DAY_ZERO.date(), failing=range(5, 8))
        for offset, expected in (
            (4, CriterionStatus.PASS),
            (5, CriterionStatus.FAIL),
            (7, CriterionStatus.FAIL),
            (8, CriterionStatus.PASS),
        ):
            with self.subTest(offset=offset):
                self.assertIs(self.observed(script, offset), expected)

    def test_unknown_wins_over_failing(self):
        """An input we could not read is not a failure, whatever else the script says."""
        script = Script.from_offsets(DAY_ZERO.date(), failing=[3], unknown=[3])
        self.assertIs(self.observed(script, 3), CriterionStatus.UNKNOWN)

    def test_not_applicable_wins_over_failing(self):
        script = Script.from_offsets(DAY_ZERO.date(), failing=[3], not_applicable=[3])
        self.assertIs(self.observed(script, 3), CriterionStatus.NOT_APPLICABLE)

    def test_it_borrows_official_so_nothing_future_can_collide(self):
        self.assertIs(ScriptedEvaluator(Script()).name, SealCriterionName.OFFICIAL)

    def test_policy_is_the_harness_own_and_overridable(self):
        default = ScriptedEvaluator(Script())
        self.assertEqual(default.grace_period, TEST_GRACE)
        self.assertEqual(default.probation_period, PROBATION_PERIOD)

        custom = ScriptedEvaluator(Script(), grace_period=None, probation_period=None)
        self.assertIsNone(custom.grace_period)
        self.assertIsNone(custom.probation_period)

    def test_the_stand_in_debounces_where_the_real_official_does_not(self):
        """Pins the divergence, so it is a fact rather than a comment.

        The real Official is a point-in-time check with neither mechanism. Every scenario
        built on this fixture depends on the stand-in having both — so if Official were ever
        given a grace period for real, this fails and says which assumption moved.
        """
        self.assertIsNone(OfficialEvaluator.grace_period)
        self.assertIsNone(OfficialEvaluator.probation_period)

        stand_in = ScriptedEvaluator(Script())
        self.assertIs(stand_in.name, OfficialEvaluator.name)
        self.assertIsNotNone(stand_in.grace_period)
        self.assertIsNotNone(stand_in.probation_period)

    def test_the_substitution_does_not_outlive_the_context(self):
        """`registry()` swaps the whole list, so nothing leaks into a later test."""
        from tasks.seal_of_reliability import seal_updater

        before = list(seal_updater.EVALUATORS)
        with registry(ScriptedEvaluator(Script())):
            self.assertEqual(len(seal_updater.EVALUATORS), 1)
        self.assertEqual(list(seal_updater.EVALUATORS), before)


class TestGracePeriod(ScriptedEvaluatorTestCase):
    def test_a_short_streak_is_absorbed(self):
        """29 failing days is inside the 30-day grace period, so the status holds."""
        script = Script.from_offsets(DAY_ZERO.date(), failing=range(1, 30))
        self.run_days(script, range(0, 30))

        row = self.state()
        self.assertEqual(row.observed_status, CriterionStatus.FAIL.value)
        self.assertEqual(
            row.confirmed_status,
            CriterionStatus.PASS.value,
            "still inside the grace period on day 29",
        )
        self.assertIsNone(row.probation_start, "an absorbed failure opens no probation")

    def test_a_streak_past_the_grace_period_confirms(self):
        script = Script.from_offsets(DAY_ZERO.date(), failing=range(1, 41))
        self.run_days(script, range(0, 41))

        row = self.state()
        self.assertEqual(row.confirmed_status, CriterionStatus.FAIL.value)
        self.assertIsNotNone(row.last_confirmed_failure_at)

    def test_the_first_evaluation_gets_no_grace(self):
        """A criterion that has never passed has no track record to hold."""
        self.run_days(Script.from_offsets(DAY_ZERO.date(), failing=[0]), [0])
        self.assertEqual(self.state().confirmed_status, CriterionStatus.FAIL.value)


class TestProbationFollowsRecovery(ScriptedEvaluatorTestCase):
    def test_recovery_from_a_confirmed_failure_opens_probation(self):
        script = Script.from_offsets(DAY_ZERO.date(), failing=range(1, 41))
        self.run_days(script, list(range(0, 42)))  # day 41 is the repair

        row = self.state()
        self.assertEqual(
            row.confirmed_status, CriterionStatus.PASS.value, "the check passes again"
        )
        self.assertIsNotNone(
            row.probation_start, "but it is serving probation for the failure"
        )

    def test_probation_suspends_the_grace_period(self):
        """One bad day during probation confirms at once, and restarts the count.

        Off probation, a single failing day sits well inside the 30-day grace period and
        would confirm nothing. This is the ratchet that makes a cold start's error persist.
        """
        script = Script.from_offsets(DAY_ZERO.date(), failing=list(range(1, 41)) + [60])
        self.run_days(script, list(range(0, 62)))

        row = self.state()
        self.assertEqual(
            row.last_confirmed_failure_at.astimezone(timezone.utc).date(),
            day(60).date(),
            "the single day confirmed because probation had suspended the grace period",
        )
        self.assertEqual(
            row.probation_start.astimezone(timezone.utc).date(),
            day(61).date(),
            "and probation restarted from the day after it",
        )

    def test_probation_clears_once_served(self):
        script = Script.from_offsets(DAY_ZERO.date(), failing=range(1, 41))
        served = 41 + PROBATION_PERIOD.days
        self.run_days(script, [*range(0, 42), served])

        self.assertIsNone(
            self.state().probation_start, "the full stretch has been served"
        )


class TestNoVerdictDays(ScriptedEvaluatorTestCase):
    def test_an_unknown_day_leaves_the_verdict_standing(self):
        script = Script.from_offsets(DAY_ZERO.date(), unknown=[1])
        self.run_days(script, [0, 1])

        row = self.state()
        self.assertEqual(row.observed_status, CriterionStatus.UNKNOWN.value)
        self.assertEqual(
            row.confirmed_status,
            CriterionStatus.PASS.value,
            "a missing input must never read as a failure",
        )

    def test_an_unknown_day_does_not_advance_a_failure_streak(self):
        """The streak keeps its start, so the grace period is not quietly extended."""
        script = Script.from_offsets(DAY_ZERO.date(), failing=range(1, 6), unknown=[3])
        self.run_days(script, range(0, 6))

        self.assertEqual(
            self.state().first_observed_failure_at.astimezone(timezone.utc).date(),
            day(1).date(),
        )

    def test_a_not_applicable_day_withdraws_the_criterion(self):
        script = Script.from_offsets(DAY_ZERO.date(), not_applicable=[1])
        self.run_days(script, [0, 1])

        row = self.state()
        self.assertEqual(
            row.confirmed_status,
            CriterionStatus.NOT_APPLICABLE.value,
            "it leaves the roll-up rather than being frozen in it",
        )


if __name__ == "__main__":
    unittest.main()
