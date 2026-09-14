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
"""End-state matrix for the backfill march (#1763): feed age x observation pattern.

Every cell runs one real backfill over a 365-day window and asserts the three things that
survive it — `confirmed_status`, whether probation is open, and whether the feed holds the
seal. The point is not the state machine itself (covered day by day in
test_scripted_evaluator.py) but that a *march* of the right length lands on the right answer.

Feed age is the second axis because the march start is clamped to `created_at`, so a younger
feed marches fewer days. Where that matters it is called out per cell: a criterion needs 180
clean days to serve probation, and a feed younger than that simply cannot finish it inside
its own march however clean it is.

Day 0 of each scenario is that feed's own march start, not the window start.

**The criterion under test is not the real Official.** Every cell runs with `EVALUATORS`
patched to a single `ScriptedEvaluator`, which files its rows under the `official` name but
carries a 30-day grace period and the standard 180-day probation — for the duration of the
test only. The real `OfficialEvaluator` has neither and would flip the same day the flag
moves, making every row of this table identical and the age axis meaningless. The whole
matrix is about the debouncing mechanisms, so it has to supply a criterion that has them;
see test_scripted_evaluator.py.
"""

import unittest
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from unittest.mock import patch

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import FeedReliabilitySeal, SealCriterion
from tasks.seal_of_reliability.backfill.seal_backfill import backfill_seals
from shared.common.seal_criteria import (
    PROBATION_PERIOD,
    CriterionStatus,
    SealCriterionName,
)
from test_scripted_evaluator import (
    TEST_GRACE,
    Script,
    ScriptedEvaluator,
    cleanup,
    seed_feed,
)
from test_shared.test_utils.database_utils import default_db_url

PREFIX = "seal_mx_"

WINDOW_DAYS = 365
END = date(2026, 6, 1)
START = END - timedelta(days=WINDOW_DAYS)

GRACE_DAYS = TEST_GRACE.days  # 30
PROBATION_DAYS = PROBATION_PERIOD.days  # 180

# How long before `END` each band's feed was created. The march start is the later of the
# window start and the creation date, so only `old` is clamped by the window.
BANDS = {
    "old": 800,  # older than the window: marches all 366 days
    "middle": 270,  # inside the window, comfortably past the probation period
    "young": 90,  # inside the window, and shorter than probation
}

PASS = CriterionStatus.PASS.value
FAIL = CriterionStatus.FAIL.value

# Each pattern is a function of the march length, returning the failing day offsets.
PATTERNS = {
    # Fails from the very first day and never recovers.
    "all_fail": lambda n: range(0, n),
    # Passes from the very first day and never fails.
    "all_pass": lambda n: (),
    # One bad first day, clean ever after. The first evaluation gets no grace, so it
    # confirms — and recovery from a confirmed failure opens probation on day 1.
    "fail_first_then_clean": lambda n: (0,),
    # Clean, then fails from day 5 to the end. Confirms once the streak outlasts grace.
    "clean_then_fails_to_the_end": lambda n: range(5, n),
    # A single failing day, well inside the grace period.
    "absorbed_blip": lambda n: (20,),
    # A confirmed failure repaired too late for probation to be served by `end_date`.
    "late_recovery": lambda n: range(n - 40, n - 4),
    # The same failure repaired early enough that probation *may* be served, depending on
    # how many days the feed's march actually has left.
    "early_recovery": lambda n: range(5, 5 + GRACE_DAYS + 6),
}

# (pattern, band) -> (confirmed_status, probation_open, has_seal)
EXPECTED = {
    ("all_fail", "old"): (FAIL, True, False),
    ("all_fail", "middle"): (FAIL, True, False),
    ("all_fail", "young"): (FAIL, True, False),
    ("all_pass", "old"): (PASS, False, True),
    ("all_pass", "middle"): (PASS, False, True),
    ("all_pass", "young"): (PASS, False, True),
    # Probation opens on day 1 and needs 180 clean days. Only the young feed runs out of
    # march before it can serve them.
    ("fail_first_then_clean", "old"): (PASS, False, True),
    ("fail_first_then_clean", "middle"): (PASS, False, True),
    ("fail_first_then_clean", "young"): (PASS, True, False),
    ("clean_then_fails_to_the_end", "old"): (FAIL, True, False),
    ("clean_then_fails_to_the_end", "middle"): (FAIL, True, False),
    ("clean_then_fails_to_the_end", "young"): (FAIL, True, False),
    ("absorbed_blip", "old"): (PASS, False, True),
    ("absorbed_blip", "middle"): (PASS, False, True),
    ("absorbed_blip", "young"): (PASS, False, True),
    ("late_recovery", "old"): (PASS, True, False),
    ("late_recovery", "middle"): (PASS, True, False),
    ("late_recovery", "young"): (PASS, True, False),
    ("early_recovery", "old"): (PASS, False, True),
    ("early_recovery", "middle"): (PASS, False, True),
    # Same repair, same clean run afterwards — but 90 days of march cannot contain a
    # 180-day probation, so the young feed ends still serving it.
    ("early_recovery", "young"): (PASS, True, False),
}


def _created_at(age_days: int) -> datetime:
    return datetime.combine(
        END - timedelta(days=age_days), datetime.min.time(), tzinfo=timezone.utc
    )


def _march_start(age_days: int) -> date:
    return max(START, END - timedelta(days=age_days))


def _march_length(age_days: int) -> int:
    return (END - _march_start(age_days)).days + 1


class TestBackfillEndStateMatrix(unittest.TestCase):
    """One real backfill per cell, asserting the state it leaves behind."""

    @with_db_session(db_url=default_db_url)
    def setUp(self, db_session):
        cleanup(db_session, PREFIX)

    @with_db_session(db_url=default_db_url)
    def tearDown(self, db_session):
        cleanup(db_session, PREFIX)

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def _seed(stable_id, age_days, db_session=None):
        seed_feed(db_session, stable_id, _created_at(age_days))
        db_session.commit()

    @staticmethod
    @with_db_session(db_url=default_db_url)
    def _final_state(stable_id, db_session=None):
        criterion = db_session.execute(
            select(SealCriterion.__table__).where(
                SealCriterion.__table__.c.feed_id == stable_id,
                SealCriterion.__table__.c.criterion == SealCriterionName.OFFICIAL.value,
            )
        ).one()
        seal = db_session.execute(
            select(FeedReliabilitySeal.__table__).where(
                FeedReliabilitySeal.__table__.c.feed_id == stable_id
            )
        ).one()
        return (
            criterion.confirmed_status,
            criterion.probation_start is not None,
            bool(seal.has_seal),
        )

    def _run_cell(self, pattern_name: str, band: str):
        age = BANDS[band]
        length = _march_length(age)
        stable_id = f"{PREFIX}{band}_{pattern_name}"[:255]

        self._seed(stable_id, age)
        script = Script.from_offsets(
            _march_start(age), failing=PATTERNS[pattern_name](length)
        )
        with patch(
            "tasks.seal_of_reliability.seal_updater.EVALUATORS",
            [ScriptedEvaluator(script)],
        ):
            backfill_seals(
                stable_feed_ids=[stable_id],
                start_date=START,
                end_date=END,
                dry_run=False,
            )
        return self._final_state(stable_id)

    def test_every_cell(self):
        for (pattern_name, band), expected in sorted(EXPECTED.items()):
            with self.subTest(pattern=pattern_name, band=band):
                self.assertEqual(
                    self._run_cell(pattern_name, band),
                    expected,
                    f"{pattern_name} / {band}: expected "
                    f"(confirmed, probation_open, has_seal) = {expected}",
                )

    def test_the_bands_really_do_march_different_lengths(self):
        """Guards the matrix: if the clamp broke, every band would march the same window."""
        self.assertEqual(_march_length(BANDS["old"]), WINDOW_DAYS + 1)
        self.assertEqual(_march_length(BANDS["middle"]), BANDS["middle"] + 1)
        self.assertEqual(_march_length(BANDS["young"]), BANDS["young"] + 1)
        self.assertLess(_march_length(BANDS["young"]), PROBATION_DAYS)


class TestProbationBoundaryAcrossAges(unittest.TestCase):
    """The exact age at which a feed becomes able to serve probation inside its own march.

    A bad first day opens probation on day 1, which clears on the first passing day at or
    after day 1 + 180. So the feed needs a march reaching day 181 — one created 181 days
    before `end_date` clears it on the very last day, and one created 180 days before does
    not. Nothing else in the suite pins this.
    """

    @with_db_session(db_url=default_db_url)
    def setUp(self, db_session):
        cleanup(db_session, PREFIX)

    @with_db_session(db_url=default_db_url)
    def tearDown(self, db_session):
        cleanup(db_session, PREFIX)

    def _seal_after_bad_first_day(self, age_days: int) -> bool:
        stable_id = f"{PREFIX}boundary_{age_days}"
        TestBackfillEndStateMatrix._seed(stable_id, age_days)
        script = Script.from_offsets(_march_start(age_days), failing=[0])
        with patch(
            "tasks.seal_of_reliability.seal_updater.EVALUATORS",
            [ScriptedEvaluator(script)],
        ):
            backfill_seals(
                stable_feed_ids=[stable_id],
                start_date=START,
                end_date=END,
                dry_run=False,
            )
        return TestBackfillEndStateMatrix._final_state(stable_id)[2]

    def test_one_day_short_of_serving_probation(self):
        self.assertFalse(self._seal_after_bad_first_day(PROBATION_DAYS))

    def test_exactly_long_enough_to_serve_probation(self):
        self.assertTrue(self._seal_after_bad_first_day(PROBATION_DAYS + 1))


class TestMarchEndingInsideTheGracePeriod(unittest.TestCase):
    """A march can run out before a failure streak outlasts its grace period.

    A feed failing every observed day since day 5 still ends holding the seal, because the
    30-day grace period has not expired by `end_date`. Correct, and the one case where a
    shorter march is *more* generous rather than less.
    """

    @with_db_session(db_url=default_db_url)
    def setUp(self, db_session):
        cleanup(db_session, PREFIX)

    @with_db_session(db_url=default_db_url)
    def tearDown(self, db_session):
        cleanup(db_session, PREFIX)

    def test_a_newborn_feed_keeps_the_seal_mid_streak(self):
        age = 20  # marches 21 days; the streak from day 5 is 15 days old at the end
        stable_id = f"{PREFIX}newborn"
        TestBackfillEndStateMatrix._seed(stable_id, age)
        script = Script.from_offsets(
            _march_start(age), failing=range(5, _march_length(age))
        )
        with patch(
            "tasks.seal_of_reliability.seal_updater.EVALUATORS",
            [ScriptedEvaluator(script)],
        ):
            backfill_seals(
                stable_feed_ids=[stable_id],
                start_date=START,
                end_date=END,
                dry_run=False,
            )

        confirmed, probation_open, has_seal = TestBackfillEndStateMatrix._final_state(
            stable_id
        )
        self.assertEqual(confirmed, PASS, "the streak is still inside the grace period")
        self.assertFalse(probation_open)
        self.assertTrue(has_seal)
        self.assertLess(_march_length(age), 5 + GRACE_DAYS)


if __name__ == "__main__":
    unittest.main()
