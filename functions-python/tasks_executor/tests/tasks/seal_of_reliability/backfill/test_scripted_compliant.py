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
"""A scripted stand-in for the Compliant criterion, and the tests proving it drives.

Compliant (#1761) has no evaluator yet, and Official — the only one that does — has neither
a grace period nor probation. So nothing currently exercises the path-dependent behaviour a
backfill (#1763) exists to reconstruct: a failure streak debounced by a grace period, a
confirmed failure, the probation that follows recovery, and an UNKNOWN day that freezes the
lot. This stand-in supplies it, with Compliant's real policy values.

Why scripted by day rather than driven through the database, as the stand-ins in
`test_seal_updater_db.py` are: those read `ctx.official` and a test moves them by issuing an
UPDATE between runs. A backfill marches its days in memory with no writes in between, so a
criterion it can drive has to answer from `ctx.now` alone. `ComplianceScript` is that — a set
of failing days and a set of unknown days, fixed up front, replayed by simply advancing the
clock.
"""

import unittest
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import FrozenSet, Tuple
from unittest.mock import patch

from sqlalchemy import delete, select

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Feed, Gtfsfeed, SealCriterion
from tasks.seal_of_reliability.criteria import (
    PROBATION_PERIOD,
    CriterionStatus,
    SealCriterionName,
)
from tasks.seal_of_reliability.evaluators import CriterionEvaluator
from tasks.seal_of_reliability.seal_updater import update_seals
from test_shared.test_utils.database_utils import default_db_url

# Compliant's published policy (#1761): a failure streak is held for 30 days before the
# status flips, and recovery from a confirmed failure serves the standard 180-day probation.
COMPLIANT_GRACE = timedelta(days=30)

DAY_ZERO = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

PREFIX = "seal_sc_"
FEED = f"{PREFIX}compliant"


def day(offset: int) -> datetime:
    """The run timestamp `offset` days after day zero."""
    return DAY_ZERO + timedelta(days=offset)


@dataclass(frozen=True)
class ComplianceScript:
    """What the stand-in answers on each day, fixed before the run starts.

    Days named in neither set pass. Keyed by `date` rather than by offset so a script stays
    readable next to the assertions that check it.
    """

    failing: FrozenSet[date] = field(default_factory=frozenset)
    unknown: FrozenSet[date] = field(default_factory=frozenset)

    @classmethod
    def failing_on(cls, *offsets: int) -> "ComplianceScript":
        return cls(failing=frozenset(day(offset).date() for offset in offsets))

    @classmethod
    def failing_between(cls, first: int, last: int) -> "ComplianceScript":
        """Inclusive of both ends, which is how a failure streak is described."""
        return cls.failing_on(*range(first, last + 1))

    def with_unknown_on(self, *offsets: int) -> "ComplianceScript":
        return ComplianceScript(
            failing=self.failing,
            unknown=frozenset(day(offset).date() for offset in offsets),
        )


class ScriptedCompliantEvaluator(CriterionEvaluator):
    """A Compliant stand-in whose verdict is a pure function of the day being evaluated.

    Borrows the `compliant` enum value, which has no evaluator of its own yet. Carries
    Compliant's real grace period and inherits the default probation period, so the
    debouncing under test is the one that will actually ship.
    """

    name = SealCriterionName.COMPLIANT
    grace_period = COMPLIANT_GRACE

    def __init__(self, script: ComplianceScript):
        self.script = script

    def _evaluate(self, ctx) -> Tuple[CriterionStatus, str]:
        today = ctx.now.astimezone(timezone.utc).date()
        if today in self.script.unknown:
            # No validation report for the latest dataset — the real Compliant's UNKNOWN
            # case, and the reason a never-validated feed does not sit at a confirmed
            # failure.
            return CriterionStatus.UNKNOWN, f"scripted: no report on {today}"
        if today in self.script.failing:
            return CriterionStatus.FAIL, f"scripted: errors on {today}"
        return CriterionStatus.PASS, f"scripted: clean on {today}"


@contextmanager
def registry(script: ComplianceScript):
    """Run with the scripted stand-in as the only criterion.

    Sole occupant on purpose: `update_seals` treats a shorter evaluator list as a partial run
    and skips the has_seal roll-up, so patching the registry itself rather than filtering it
    is what keeps the seal in play.
    """
    with patch(
        "tasks.seal_of_reliability.seal_updater.EVALUATORS",
        [ScriptedCompliantEvaluator(script)],
    ):
        yield


def _cleanup(db_session):
    db_session.execute(delete(Feed).where(Feed.stable_id.like(f"{PREFIX}%")))
    db_session.commit()


class ScriptedCompliantTestCase(unittest.TestCase):
    """Seeds one eligible feed and replays scripted days against it."""

    @with_db_session(db_url=default_db_url)
    def setUp(self, db_session):
        _cleanup(db_session)
        db_session.add(
            Gtfsfeed(
                id=FEED,
                stable_id=FEED,
                data_type="gtfs",
                status="active",
                operational_status="published",
                official=True,
                created_at=DAY_ZERO - timedelta(days=400),
                producer_url=f"https://example.com/{FEED}.zip",
            )
        )
        db_session.commit()

    @with_db_session(db_url=default_db_url)
    def tearDown(self, db_session):
        _cleanup(db_session)

    @staticmethod
    def run_days(script: ComplianceScript, offsets) -> None:
        """Evaluate the feed once per day, in order, writing each day's state.

        This is a march done the slow way — through the database, one `update_seals` call per
        day — which is exactly what #1763's in-memory march has to reproduce.
        """
        with registry(script):
            for offset in offsets:
                update_seals(stable_feed_ids=[FEED], dry_run=False, now=day(offset))

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def state(db_session=None):
        return db_session.execute(
            select(SealCriterion.__table__).where(
                SealCriterion.__table__.c.feed_id == FEED,
                SealCriterion.__table__.c.criterion
                == SealCriterionName.COMPLIANT.value,
            )
        ).one()


class TestScriptDrivesTheEvaluator(unittest.TestCase):
    """The fixture itself, with no database in the way."""

    class _Ctx:
        def __init__(self, now):
            self.now = now
            self.feed_id = FEED
            self.stable_id = FEED

    def observed(self, script: ComplianceScript, offset: int) -> CriterionStatus:
        evaluator = ScriptedCompliantEvaluator(script)
        return evaluator.evaluate(self._Ctx(day(offset))).observed_status

    def test_unnamed_days_pass(self):
        self.assertIs(
            self.observed(ComplianceScript.failing_on(3), 0), CriterionStatus.PASS
        )

    def test_named_days_fail(self):
        self.assertIs(
            self.observed(ComplianceScript.failing_on(3), 3), CriterionStatus.FAIL
        )

    def test_a_range_is_inclusive_of_both_ends(self):
        script = ComplianceScript.failing_between(5, 7)
        for offset, expected in (
            (4, CriterionStatus.PASS),
            (5, CriterionStatus.FAIL),
            (7, CriterionStatus.FAIL),
            (8, CriterionStatus.PASS),
        ):
            with self.subTest(offset=offset):
                self.assertIs(self.observed(script, offset), expected)

    def test_unknown_days_win_over_failing_days(self):
        """An input we could not read is not a failure, whatever else the script says."""
        script = ComplianceScript.failing_on(3).with_unknown_on(3)
        self.assertIs(self.observed(script, 3), CriterionStatus.UNKNOWN)

    def test_it_carries_compliant_policy(self):
        self.assertEqual(ScriptedCompliantEvaluator.grace_period, timedelta(days=30))
        self.assertEqual(
            ScriptedCompliantEvaluator.probation_period,
            PROBATION_PERIOD,
            "the default 180 days, not an override",
        )


class TestGracePeriod(ScriptedCompliantTestCase):
    def test_a_short_streak_is_absorbed(self):
        """29 failing days is inside the 30-day grace period, so the status holds."""
        script = ComplianceScript.failing_between(1, 29)
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
        script = ComplianceScript.failing_between(1, 40)
        self.run_days(script, range(0, 41))

        row = self.state()
        self.assertEqual(row.confirmed_status, CriterionStatus.FAIL.value)
        self.assertIsNotNone(row.last_confirmed_failure_at)

    def test_the_first_evaluation_gets_no_grace(self):
        """A criterion that has never passed has no track record to hold."""
        self.run_days(ComplianceScript.failing_on(0), [0])
        self.assertEqual(self.state().confirmed_status, CriterionStatus.FAIL.value)


class TestProbationFollowsRecovery(ScriptedCompliantTestCase):
    def test_recovery_from_a_confirmed_failure_opens_probation(self):
        script = ComplianceScript.failing_between(1, 40)
        self.run_days(script, list(range(0, 42)))  # day 41 is the repair

        row = self.state()
        self.assertEqual(
            row.confirmed_status,
            CriterionStatus.PASS.value,
            "the check passes again",
        )
        self.assertIsNotNone(
            row.probation_start, "but it is serving probation for the failure"
        )

    def test_probation_suspends_the_grace_period(self):
        """One bad day during probation confirms at once, and restarts the count.

        Off probation, a single failing day sits well inside the 30-day grace period and
        would confirm nothing. This is the ratchet that makes a cold start's error persist.
        """
        script = ComplianceScript(
            failing=frozenset(
                [day(offset).date() for offset in range(1, 41)] + [day(60).date()]
            )
        )
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
        script = ComplianceScript.failing_between(1, 40)
        served = 41 + PROBATION_PERIOD.days
        self.run_days(script, [*range(0, 42), served])

        self.assertIsNone(
            self.state().probation_start, "the full stretch has been served"
        )


class TestUnknownFreezesTheState(ScriptedCompliantTestCase):
    def test_an_unknown_day_leaves_the_verdict_standing(self):
        script = ComplianceScript().with_unknown_on(1)
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
        script = ComplianceScript.failing_between(1, 5).with_unknown_on(3)
        self.run_days(script, range(0, 6))

        row = self.state()
        self.assertEqual(
            row.first_observed_failure_at.astimezone(timezone.utc).date(),
            day(1).date(),
        )


if __name__ == "__main__":
    unittest.main()
