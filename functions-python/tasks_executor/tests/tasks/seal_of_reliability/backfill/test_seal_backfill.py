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
"""Tests for the Seal of Reliability backfill (#1763): parameters, window, and plan.

The day march is not implemented, so these cover the invocation surface — what the payload
resolves to, which feeds are selected, and that a non-dry run refuses rather than reporting
a success that wrote nothing.
"""

import json
import os
import unittest
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from unittest.mock import patch

from sqlalchemy import delete, insert, select

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Feed,
    FeedReliabilitySeal,
    Gtfsfeed,
    SealCriterion,
    SealCriterionSnapshot,
)
from tasks.seal_of_reliability.backfill.backfill_seal_of_reliability import (
    _parse_day,
    backfill_seal_of_reliability_handler,
    get_parameters,
)
from tasks.seal_of_reliability.backfill.simulation import TRACED_STATE_FIELDS
from tasks.seal_of_reliability.seal_updater import SNAPSHOT_STATE_COLUMNS
from tasks.seal_of_reliability.backfill.seal_backfill import (
    DEFAULT_DAYS_BACK,
    backfill_seals,
    day_start,
    days_between,
    march_start_for,
    resolve_window,
    yesterday_utc,
)
from shared.common.seal_criteria import SealCriterionName
from tasks.seal_of_reliability.seal_updater import update_seals
from test_scripted_evaluator import Script, ScriptedEvaluator
from test_shared.test_utils.database_utils import default_db_url

PREFIX = "seal_bf_"
OLD = f"{PREFIX}old"  # created well before any window we test
YOUNG = f"{PREFIX}young"  # created inside the window, so its march is clamped
DEPRECATED = f"{PREFIX}deprecated"  # not seal-eligible
ALREADY = f"{PREFIX}already"  # already has seal state

END = date(2026, 6, 1)
START = date(2025, 6, 1)

NOW = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
OLD_CREATED = NOW - timedelta(days=800)
YOUNG_CREATED = NOW - timedelta(days=90)


@dataclass
class _FeedStub:
    """Just enough of a feed row for `march_start_for`, which reads only `created_at`."""

    created_at: Optional[datetime]


class TestParseDay(unittest.TestCase):
    def test_plain_iso_date(self):
        self.assertEqual(_parse_day("2026-01-31", "start_date"), date(2026, 1, 31))

    def test_timestamp_is_accepted_and_truncated(self):
        """An operator pasting the nightly task's `now` should not hit a parse error.

        The march is day-granular, so the time of day is dropped either way.
        """
        for value in ("2026-01-31T12:00:00", "2026-01-31T12:00:00+00:00"):
            with self.subTest(value=value):
                self.assertEqual(_parse_day(value, "end_date"), date(2026, 1, 31))

    def test_absent_stays_none(self):
        self.assertIsNone(_parse_day(None, "start_date"))

    def test_garbage_names_the_field(self):
        with self.assertRaises(ValueError) as caught:
            _parse_day("last tuesday", "start_date")
        self.assertIn("start_date", str(caught.exception))


class TestGetParameters(unittest.TestCase):
    def test_defaults(self):
        (
            stable_feed_ids,
            start_date,
            end_date,
            days_back,
            dry_run,
            limit,
            criteria,
            batch_size,
            only_missing,
            snapshot_mode,
            resume_from_snapshot,
            max_reported_feeds,
            simulate,
            trace,
            collapse_trace,
        ) = get_parameters({"stable_feed_ids": ["a"]})

        self.assertEqual(stable_feed_ids, ["a"])
        self.assertIsNone(start_date)
        self.assertIsNone(end_date)
        self.assertEqual(days_back, DEFAULT_DAYS_BACK)
        self.assertTrue(dry_run, "a backfill must not write unless asked to")
        self.assertIsNone(limit)
        self.assertIsNone(criteria)
        self.assertEqual(batch_size, 200)
        self.assertTrue(only_missing, "#1763 backfills feeds that have no state yet")
        self.assertEqual(snapshot_mode, "final")
        self.assertFalse(resume_from_snapshot)
        self.assertEqual(max_reported_feeds, 50)
        self.assertIsNone(simulate)
        self.assertFalse(trace, "a run must not pay for a trace unless asked")
        self.assertTrue(collapse_trace, "a year of days is unreadable row by row")

    def test_empty_payload_does_not_raise_here(self):
        """Validation belongs to the engine, so the parser stays a plain reader."""
        self.assertIsNone(get_parameters({})[0])


class TestResolveWindow(unittest.TestCase):
    def test_both_given_are_kept(self):
        self.assertEqual(resolve_window(START, END, DEFAULT_DAYS_BACK), (START, END))

    def test_end_defaults_to_yesterday(self):
        _, resolved_end = resolve_window(START, None, DEFAULT_DAYS_BACK)
        self.assertEqual(resolved_end, yesterday_utc())

    def test_start_defaults_to_days_back_from_end(self):
        resolved_start, _ = resolve_window(None, END, 365)
        self.assertEqual(resolved_start, END - timedelta(days=365))

    def test_start_after_end_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            resolve_window(END + timedelta(days=1), END, DEFAULT_DAYS_BACK)
        self.assertIn("after end_date", str(caught.exception))

    def test_non_positive_days_back_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve_window(None, END, 0)


class TestMarchStart(unittest.TestCase):
    def test_feed_older_than_the_window_starts_at_the_window(self):
        feed = _FeedStub(created_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(march_start_for(feed, START), START)

    def test_feed_younger_than_the_window_starts_at_its_creation(self):
        """A feed with no history before its creation gets an exact cold start, not a guess."""
        created = datetime(2025, 9, 15, 8, 30, tzinfo=timezone.utc)
        feed = _FeedStub(created_at=created)
        self.assertEqual(march_start_for(feed, START), date(2025, 9, 15))

    def test_naive_created_at_is_read_as_utc(self):
        feed = _FeedStub(created_at=datetime(2025, 9, 15, 8, 30))
        self.assertEqual(march_start_for(feed, START), date(2025, 9, 15))

    def test_missing_created_at_falls_back_to_the_window(self):
        self.assertEqual(march_start_for(_FeedStub(created_at=None), START), START)


def _seed_feed(db_session, feed_id, created_at, status="active"):
    db_session.add(
        Gtfsfeed(
            id=feed_id,
            stable_id=feed_id,
            data_type="gtfs",
            status=status,
            operational_status="published",
            official=True,
            created_at=created_at,
            producer_url=f"https://example.com/{feed_id}.zip",
        )
    )
    db_session.flush()


def _cleanup(db_session):
    """Delete from `feed`, not `gtfsfeed`.

    Gtfsfeed is a joined-table subclass, so deleting the subclass leaves the parent row and
    the next insert collides on feed_pkey. The seal tables are ON DELETE CASCADE.
    """
    db_session.execute(delete(Feed).where(Feed.stable_id.like(f"{PREFIX}%")))
    db_session.commit()


class BackfillDbTestCase(unittest.TestCase):
    @with_db_session(db_url=default_db_url)
    def setUp(self, db_session):
        _cleanup(db_session)
        _seed_feed(db_session, OLD, OLD_CREATED)
        _seed_feed(db_session, YOUNG, YOUNG_CREATED)
        _seed_feed(db_session, DEPRECATED, OLD_CREATED, status="deprecated")
        _seed_feed(db_session, ALREADY, OLD_CREATED)
        db_session.execute(
            insert(SealCriterion.__table__).values(
                feed_id=ALREADY, criterion="official"
            )
        )
        db_session.commit()

    @with_db_session(db_url=default_db_url)
    def tearDown(self, db_session):
        _cleanup(db_session)


class TestBackfillPlan(BackfillDbTestCase):
    def test_dry_run_reports_the_resolved_window(self):
        report = backfill_seals(
            stable_feed_ids=[OLD], start_date=START, end_date=END, dry_run=True
        )
        self.assertTrue(report["dry_run"])
        self.assertEqual(report["criterion_rows_written"], 0)
        self.assertEqual(report["start_date"], START.isoformat())
        self.assertEqual(report["end_date"], END.isoformat())
        self.assertEqual(report["days"], (END - START).days + 1)
        self.assertEqual(report["total_feeds"], 1)

    def test_each_feed_marches_from_its_own_start(self):
        """The window start is run-wide; the march start is per feed."""
        report = backfill_seals(
            stable_feed_ids=[OLD, YOUNG], start_date=START, end_date=END, dry_run=True
        )
        by_id = {entry["stable_id"]: entry for entry in report["feeds"]}

        self.assertEqual(by_id[OLD]["march_start"], START.isoformat())
        self.assertEqual(by_id[YOUNG]["march_start"], YOUNG_CREATED.date().isoformat())
        self.assertLess(by_id[YOUNG]["days"], by_id[OLD]["days"])

    def test_march_start_is_also_the_stable_anchor(self):
        report = backfill_seals(
            stable_feed_ids=[YOUNG], start_date=START, end_date=END, dry_run=True
        )
        entry = report["feeds"][0]
        self.assertEqual(entry["tracking_start"], entry["march_start"])

    def test_ineligible_feeds_are_left_out(self):
        report = backfill_seals(
            stable_feed_ids=[OLD, DEPRECATED],
            start_date=START,
            end_date=END,
            dry_run=True,
        )
        self.assertEqual(
            [entry["stable_id"] for entry in report["feeds"]],
            [OLD],
        )

    def test_only_missing_skips_a_feed_that_already_has_state(self):
        report = backfill_seals(
            stable_feed_ids=[OLD, ALREADY],
            start_date=START,
            end_date=END,
            dry_run=True,
        )
        self.assertEqual(report["total_feeds"], 1)
        self.assertEqual(report["skipped_already_backfilled"], 1)
        self.assertEqual([entry["stable_id"] for entry in report["feeds"]], [OLD])

    def test_only_missing_false_re_backfills(self):
        report = backfill_seals(
            stable_feed_ids=[OLD, ALREADY],
            start_date=START,
            end_date=END,
            dry_run=True,
            only_missing=False,
        )
        self.assertEqual(report["total_feeds"], 2)
        self.assertEqual(report["skipped_already_backfilled"], 0)


class TestPerFeedMarchLength(BackfillDbTestCase):
    """Two feeds of different ages, one run: each marches its own number of days.

    `TestBackfillPlan.test_each_feed_marches_from_its_own_start` pins the *plan*, which is
    arithmetic on `windows`. This pins the march, which is a different mechanism: `_march`
    walks one day range for the whole batch — from the earliest march start in the run — and
    admits each feed only once `windows[feed.id][0] <= today`. With one feed that filter can
    never exclude anything, so it takes two feeds of different ages to exercise it at all.
    """

    OLD_DAYS = (END - START).days + 1
    YOUNG_DAYS = (END - YOUNG_CREATED.date()).days + 1

    def _marched_rows(self, **kwargs):
        """stable_id -> its uncollapsed trace rows, from a dry run that marches anyway.

        Everything passes, and the stand-in's verdict is a function of the day alone, so any
        difference between the two feeds is the clamp's doing and nothing else.
        """
        with patch(
            "tasks.seal_of_reliability.seal_updater.EVALUATORS",
            [ScriptedEvaluator(Script())],
        ):
            report = backfill_seals(
                stable_feed_ids=[OLD, YOUNG],
                start_date=START,
                end_date=END,
                dry_run=True,
                trace=True,
                collapse_trace=False,
                **kwargs,
            )
        by_feed = {}
        for row in report["trace"]:
            by_feed.setdefault(row["stable_id"], []).append(row)
        return by_feed

    def _assert_each_feed_marched_its_own_window(self, by_feed):
        self.assertEqual(sorted(by_feed), sorted([OLD, YOUNG]))
        for stable_id, expected_days, march_start in (
            (OLD, self.OLD_DAYS, START),
            (YOUNG, self.YOUNG_DAYS, YOUNG_CREATED.date()),
        ):
            rows = sorted(by_feed[stable_id], key=lambda row: row["day"])
            self.assertEqual(
                [row["day"] for row in rows],
                list(range(expected_days)),
                f"{stable_id} marched {len(rows)} day(s), expected {expected_days}",
            )
            # Day 0 is the feed's own march start; the last day is the run's end_date. The
            # two feeds share the second and not the first.
            self.assertEqual(rows[0]["evaluated_at"], march_start.isoformat())
            self.assertEqual(rows[-1]["evaluated_at"], END.isoformat())
        self.assertLess(len(by_feed[YOUNG]), len(by_feed[OLD]))

    def test_each_feed_marches_its_own_number_of_days(self):
        self._assert_each_feed_marched_its_own_window(self._marched_rows())

    def test_the_clamp_holds_with_the_feeds_in_separate_batches(self):
        """A batch walks from the *run's* earliest march start, not its own."""
        self._assert_each_feed_marched_its_own_window(self._marched_rows(batch_size=1))


class TestBackfillValidation(BackfillDbTestCase):
    def test_empty_feed_list_is_rejected(self):
        with self.assertRaises(ValueError):
            backfill_seals(stable_feed_ids=[], dry_run=True)

    def test_unknown_snapshot_mode_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            backfill_seals(
                stable_feed_ids=[OLD], dry_run=True, snapshot_mode="occasionally"
            )
        self.assertIn("occasionally", str(caught.exception))

    def test_unknown_criteria_are_rejected(self):
        with self.assertRaises(ValueError) as caught:
            backfill_seals(stable_feed_ids=[OLD], dry_run=True, criteria=["punctual"])
        self.assertIn("punctual", str(caught.exception))

    def test_dry_run_writes_nothing(self):
        backfill_seals(
            stable_feed_ids=[OLD], start_date=START, end_date=END, dry_run=True
        )
        self.assertEqual(criterion_rows(OLD), {})
        self.assertIsNone(seal_row(OLD))

    def test_handler_threads_the_payload_through(self):
        report = backfill_seal_of_reliability_handler(
            {
                "stable_feed_ids": [OLD],
                "start_date": START.isoformat(),
                "end_date": END.isoformat(),
                "snapshot_mode": "all",
                "resume_from_snapshot": True,
            }
        )
        self.assertEqual(report["snapshot_mode"], "all")
        self.assertTrue(report["resume_from_snapshot"])
        self.assertEqual(report["start_date"], START.isoformat())


MARCHED = f"{PREFIX}marched"
REPLAYED = f"{PREFIX}replayed"

# The march tests below run with EVALUATORS patched to a single ScriptedEvaluator. It files
# its rows under the `official` criterion but carries a 30-day grace period and the standard
# 180-day probation, for the duration of each test only — the real OfficialEvaluator has
# neither. Those two mechanisms are what a backfill has to reconstruct, and no implemented
# criterion has them yet; see test_scripted_evaluator.py.
#
# A short window, so the equivalence test replays a tractable number of days through the
# database. The failing run is long enough to outlast that 30-day grace period, so the
# comparison covers a confirmed failure and the probation that follows it.
MARCH_START = date(2026, 1, 1)
MARCH_END = date(2026, 3, 15)

STATE_COLUMNS = (
    "observed_status",
    "confirmed_status",
    "evaluated_at",
    "last_verdict_at",
    "first_observed_failure_at",
    "last_observed_failure_at",
    "last_confirmed_failure_at",
    "probation_start",
)


def _script_for(offsets_from_march_start):
    """A Script whose failing days are offsets from MARCH_START."""
    return Script.from_offsets(MARCH_START, failing=offsets_from_march_start)


@with_db_session(db_url=default_db_url)
def criterion_rows(stable_id, db_session=None):
    rows = db_session.execute(
        select(SealCriterion.__table__).where(
            SealCriterion.__table__.c.feed_id == stable_id
        )
    ).all()
    return {row.criterion: row for row in rows}


@with_db_session(db_url=default_db_url)
def seal_row(stable_id, db_session=None):
    return db_session.execute(
        select(FeedReliabilitySeal.__table__).where(
            FeedReliabilitySeal.__table__.c.feed_id == stable_id
        )
    ).one_or_none()


@with_db_session(db_url=default_db_url)
def snapshot_days(stable_id, db_session=None):
    rows = db_session.execute(
        select(SealCriterionSnapshot.__table__.c.snapshot_date).where(
            SealCriterionSnapshot.__table__.c.feed_id == stable_id
        )
    ).all()
    return sorted({row.snapshot_date for row in rows})


def trace_day(report, day):
    """The marched day `day`, found inside the collapsed trace.

    A day mid-stretch resolves to that stretch's `first` row: every field asserted on here is
    part of the signature it collapsed on, so it is identical across the stretch.
    """
    for entry in report["trace"]:
        first = entry["first"]
        last = entry.get("last", first)
        if first["day"] <= day <= last["day"]:
            return last if day == last["day"] else first
    raise AssertionError(f"day {day} is not in the trace")


def trace_last(report):
    """The final marched day of the trace."""
    entry = report["trace"][-1]
    return entry.get("last", entry["first"])


class MarchTestCase(unittest.TestCase):
    """Two identically-aged feeds: one marched in memory, one replayed through the database."""

    @with_db_session(db_url=default_db_url)
    def setUp(self, db_session):
        _cleanup(db_session)
        _seed_feed(db_session, MARCHED, OLD_CREATED)
        _seed_feed(db_session, REPLAYED, OLD_CREATED)
        db_session.commit()

    @with_db_session(db_url=default_db_url)
    def tearDown(self, db_session):
        _cleanup(db_session)

    @staticmethod
    def registry(script):
        """Patch the registry `_resolve_evaluators` reads, which is the one both paths use."""
        return patch(
            "tasks.seal_of_reliability.seal_updater.EVALUATORS",
            [ScriptedEvaluator(script)],
        )

    @staticmethod
    def march(stable_id, script, **kwargs):
        with MarchTestCase.registry(script):
            return backfill_seals(
                stable_feed_ids=[stable_id],
                start_date=MARCH_START,
                end_date=MARCH_END,
                dry_run=False,
                **kwargs,
            )

    @staticmethod
    def replay_through_db(stable_id, script):
        """The same days, evaluated one `update_seals` call at a time.

        Uses the same midnight-UTC timestamps the march uses, so any difference in the final
        state is the march's doing and not a difference in `now`.
        """
        with MarchTestCase.registry(script):
            for day in days_between(MARCH_START, MARCH_END):
                update_seals(
                    stable_feed_ids=[stable_id], dry_run=False, now=day_start(day)
                )

    def state_of(self, stable_id):
        row = criterion_rows(stable_id)[SealCriterionName.OFFICIAL.value]
        return {column: getattr(row, column) for column in STATE_COLUMNS}


class TestMarchMatchesTheDatabaseReplay(MarchTestCase):
    def test_a_clean_run_agrees(self):
        script = _script_for([])
        self.march(MARCHED, script)
        self.replay_through_db(REPLAYED, script)
        self.assertEqual(self.state_of(MARCHED), self.state_of(REPLAYED))

    def test_a_confirmed_failure_and_its_probation_agree(self):
        """The case the backfill exists for: state that depends on the whole path."""
        script = _script_for(range(10, 46))
        self.march(MARCHED, script)
        self.replay_through_db(REPLAYED, script)

        marched = self.state_of(MARCHED)
        self.assertEqual(marched, self.state_of(REPLAYED))
        self.assertIsNotNone(
            marched["last_confirmed_failure_at"],
            "the 36-day streak must have outlasted the 30-day grace period",
        )
        self.assertIsNotNone(
            marched["probation_start"], "and recovery must have opened probation"
        )

    def test_an_absorbed_blip_agrees(self):
        script = _script_for([20])
        self.march(MARCHED, script)
        self.replay_through_db(REPLAYED, script)

        marched = self.state_of(MARCHED)
        self.assertEqual(marched, self.state_of(REPLAYED))
        self.assertIsNone(
            marched["last_confirmed_failure_at"],
            "one day is well inside the grace period",
        )


class TestMarchWrites(MarchTestCase):
    def test_only_the_final_day_is_snapshotted_by_default(self):
        self.march(MARCHED, _script_for([20]))
        self.assertEqual(snapshot_days(MARCHED), [MARCH_END])

    def test_snapshot_mode_all_records_every_day(self):
        self.march(MARCHED, _script_for([20]), snapshot_mode="all")
        self.assertEqual(snapshot_days(MARCHED), days_between(MARCH_START, MARCH_END))

    def test_snapshot_mode_none_records_nothing(self):
        self.march(MARCHED, _script_for([20]), snapshot_mode="none")
        self.assertEqual(snapshot_days(MARCHED), [])

    def test_the_seal_row_created_at_is_the_march_start(self):
        """Left at its DEFAULT now(), Stable would fail on every simulated day."""
        self.march(MARCHED, _script_for([]))
        self.assertEqual(
            seal_row(MARCHED).created_at.astimezone(timezone.utc).date(), MARCH_START
        )

    def test_created_at_survives_a_re_backfill(self):
        """Insert-only: a re-run must not reset a countdown already running."""
        self.march(MARCHED, _script_for([]))
        first = seal_row(MARCHED).created_at

        with self.registry(_script_for([])):
            backfill_seals(
                stable_feed_ids=[MARCHED],
                start_date=MARCH_START + timedelta(days=30),
                end_date=MARCH_END,
                dry_run=False,
                only_missing=False,
            )
        self.assertEqual(seal_row(MARCHED).created_at, first)

    def test_seal_earned_at_is_the_end_of_the_window(self):
        report = self.march(MARCHED, _script_for([]))
        self.assertEqual(report["seals_granted"], 1)
        self.assertEqual(
            seal_row(MARCHED).seal_earned_at.astimezone(timezone.utc).date(), MARCH_END
        )

    def test_the_report_counts_what_was_written(self):
        report = self.march(MARCHED, _script_for([20]))
        self.assertEqual(report["criterion_rows_written"], 1)
        self.assertEqual(report["snapshot_rows_written"], 1)
        self.assertEqual(report["granted_stable_ids"], [MARCHED])
        self.assertFalse(report["dry_run"])


class TestResumeFromSnapshot(MarchTestCase):
    def test_a_resume_starts_from_the_stored_snapshot(self):
        """Seeded from the day before, the march inherits an open probation.

        Without the seed the same window is a clean cold start, so the difference is
        entirely the snapshot's doing.
        """
        # A first march that ends on probation, snapshotting every day.
        self.march(MARCHED, _script_for(range(10, 46)), snapshot_mode="all")
        self.assertIsNotNone(self.state_of(MARCHED)["probation_start"])

        # Resume the tail of the window, with no failures in it at all.
        with self.registry(_script_for([])):
            backfill_seals(
                stable_feed_ids=[MARCHED],
                start_date=MARCH_START + timedelta(days=60),
                end_date=MARCH_END,
                dry_run=False,
                only_missing=False,
                resume_from_snapshot=True,
            )

        self.assertIsNotNone(
            self.state_of(MARCHED)["probation_start"],
            "the probation carried over from the seeded snapshot",
        )

    def test_without_the_flag_the_same_window_cold_starts(self):
        self.march(MARCHED, _script_for(range(10, 46)), snapshot_mode="all")

        with self.registry(_script_for([])):
            backfill_seals(
                stable_feed_ids=[MARCHED],
                start_date=MARCH_START + timedelta(days=60),
                end_date=MARCH_END,
                dry_run=False,
                only_missing=False,
            )

        self.assertIsNone(
            self.state_of(MARCHED)["probation_start"],
            "a cold start carries no probation forward",
        )


class TestSimulateAndTrace(MarchTestCase):
    """Forced per-day statuses, and the day-by-day trace they are there to make visible."""

    def simulate(self, stable_id, **kwargs):
        with self.registry(_script_for([])):
            return backfill_seals(
                stable_feed_ids=[stable_id],
                start_date=MARCH_START,
                end_date=MARCH_END,
                dry_run=True,
                **kwargs,
            )

    def test_a_simulated_run_never_writes(self):
        """The reason simulate forces dry_run: a forced verdict in seal_criterion would be
        indistinguishable from an earned one."""
        report = self.simulate(MARCHED, simulate={"official": {"fail": [0, 1]}})
        self.assertEqual(criterion_rows(MARCHED), {})
        self.assertIsNone(seal_row(MARCHED))
        self.assertEqual(report["criterion_rows_written"], 0)

    def test_writing_with_a_simulation_is_refused(self):
        """No environment permits it: the row would be indistinguishable from an earned one."""
        with self.assertRaises(ValueError) as caught:
            with self.registry(_script_for([])):
                backfill_seals(
                    stable_feed_ids=[MARCHED],
                    start_date=MARCH_START,
                    end_date=MARCH_END,
                    dry_run=False,
                    only_missing=False,
                    simulate={"official": {"fail": [0]}},
                )
        self.assertIn("dry_run", str(caught.exception))
        self.assertEqual(criterion_rows(MARCHED), {}, "and nothing was written")

    def test_a_forced_failure_reaches_the_state_machine(self):
        """Day 0 is the first evaluation, so it gets no grace and confirms immediately."""
        report = self.simulate(
            MARCHED, simulate={"official": {"fail": [0]}}, trace=True
        )
        day_zero = trace_day(report, 0)
        self.assertEqual(day_zero["observed_status"], "fail")
        self.assertEqual(day_zero["confirmed_status"], "fail")
        self.assertTrue(day_zero["simulated"])

    def test_unnamed_days_fall_through_to_the_real_evaluator(self):
        """A simulation is real data with overrides, not a synthetic run."""
        report = self.simulate(
            MARCHED, simulate={"official": {"fail": [0]}}, trace=True
        )
        day_one = trace_day(report, 1)
        self.assertEqual(day_one["observed_status"], "pass")
        self.assertFalse(day_one["simulated"])

    def test_a_streak_past_the_grace_period_confirms_then_serves_probation(self):
        """Days 1-39 fail, then the feed recovers — the whole arc in one trace.

        The stand-in's grace period is 30 days and the streak starts on day 1, so day 31 is
        the first confirmed failure. Recovery on day 40 clears the status but opens
        probation, which 34 remaining days cannot serve.
        """
        report = self.simulate(
            MARCHED,
            simulate={"official": {"fail": list(range(1, 40))}},
            trace=True,
        )
        self.assertEqual(
            trace_day(report, 30)["confirmed_status"], "pass", "last day of grace"
        )
        self.assertEqual(
            trace_day(report, 31)["confirmed_status"], "fail", "grace outlasted"
        )

        last = trace_last(report)
        self.assertEqual(last["observed_status"], "pass")
        self.assertEqual(last["confirmed_status"], "pass", "recovered")
        self.assertEqual(last["phase"], "on_probation")
        self.assertIsNotNone(last["probation_start"])

    def test_a_trace_row_carries_every_seal_criterion_field(self):
        """The trace is the stored row plus provenance, not a summary of it.

        Derived from SealCriterionState, so a field added there appears here without anyone
        remembering to widen the trace — and this fails if it ever stops being derived.
        """
        from dataclasses import fields as dataclass_fields

        from tasks.seal_of_reliability.state_machine import SealCriterionState

        report = self.simulate(
            MARCHED, simulate={"official": {"fail": [1]}}, trace=True
        )
        row = trace_day(report, 0)

        expected = {f.name for f in dataclass_fields(SealCriterionState)} - {
            "feed_id",
            "criterion",
        }
        self.assertTrue(
            expected.issubset(row),
            f"trace is missing state fields: {sorted(expected - set(row))}",
        )
        for name in ("day", "phase", "simulated", "reason", "criterion"):
            self.assertIn(name, row)
        self.assertNotIn(
            "date", row, "dropped: evaluated_at is the same day by construction"
        )

    def test_the_carried_state_tracks_the_streak(self):
        """first_observed_failure_at is set while failing and cleared on recovery."""
        report = self.simulate(
            MARCHED, simulate={"official": {"fail": [1, 2]}}, trace=True
        )
        days = {day: trace_day(report, day) for day in (0, 1, 2, 3)}

        self.assertIsNone(days[0]["first_observed_failure_at"])
        self.assertEqual(days[1]["first_observed_failure_at"], days[1]["evaluated_at"])
        self.assertEqual(
            days[2]["first_observed_failure_at"],
            days[1]["evaluated_at"],
            "the streak keeps its start",
        )
        self.assertIsNone(days[3]["first_observed_failure_at"], "cleared on recovery")
        self.assertEqual(
            days[3]["last_observed_failure_at"],
            days[2]["evaluated_at"],
            "but the history is never cleared",
        )

    def test_the_trace_accounts_for_every_marched_day(self):
        """Collapsed stretches tile the march: contiguous, in order, none missing."""
        report = self.simulate(MARCHED, trace=True)
        marched = (MARCH_END - MARCH_START).days + 1

        next_expected = 0
        for entry in report["trace"]:
            first = entry["first"]
            last = entry.get("last", first)
            self.assertEqual(first["day"], next_expected, "stretches are contiguous")
            self.assertEqual(entry["days"], last["day"] - first["day"] + 1)
            next_expected = last["day"] + 1
        self.assertEqual(next_expected, marched, "every marched day is accounted for")

    def test_the_trace_is_offset_from_the_feed_own_march_start(self):
        """Day 0 is the feed's first evaluated day, not the window start."""
        report = self.simulate(MARCHED, trace=True)
        first = trace_day(report, 0)
        self.assertEqual(first["day"], 0)
        self.assertEqual(first["evaluated_at"], MARCH_START.isoformat())

    def test_an_unknown_criterion_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.simulate(MARCHED, simulate={"punctual": {"fail": [0]}})
        self.assertIn("punctual", str(caught.exception))

    def test_an_unknown_status_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.simulate(MARCHED, simulate={"official": {"broken": [0]}})
        self.assertIn("broken", str(caught.exception))

    def test_a_negative_offset_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.simulate(MARCHED, simulate={"official": {"fail": [-1]}})
        self.assertIn("negative", str(caught.exception))

    def test_an_offset_past_the_march_is_rejected(self):
        """A typo like day 400 in a short window would otherwise silently do nothing."""
        with self.assertRaises(ValueError) as caught:
            self.simulate(MARCHED, simulate={"official": {"fail": [9999]}})
        self.assertIn("9999", str(caught.exception))

    def test_the_report_echoes_what_was_simulated(self):
        report = self.simulate(
            MARCHED, simulate={"official": {"fail": [2], "unknown": [4]}}
        )
        # String keys: the echo shares its dict with grace_days/probation_days, and jsonify
        # sorts keys, which raises on a dict mixing str and int.
        self.assertEqual(report["simulated"]["official"], {"2": "fail", "4": "unknown"})

    def test_a_plain_dry_run_still_stops_at_the_plan(self):
        """Only simulate or trace makes a dry run pay for the march."""
        report = self.simulate(MARCHED)
        self.assertNotIn("trace", report)


class TestSimulatedPolicy(MarchTestCase):
    """Lending a criterion a grace period and probation it does not have.

    The stand-in already has both, so these use `grace_days`/`probation_days` to *remove*
    and to *change* them — the same mechanism that lets Official, which has neither, show
    debouncing in a simulation.
    """

    def simulate(self, **kwargs):
        with self.registry(_script_for([])):
            return backfill_seals(
                stable_feed_ids=[MARCHED],
                start_date=MARCH_START,
                end_date=MARCH_END,
                dry_run=True,
                trace=True,
                **kwargs,
            )

    @staticmethod
    def _day(report, day):
        return trace_day(report, day)

    def test_a_lent_grace_period_absorbs_a_failure(self):
        """Without an override this criterion confirms on day 1; with 14 days it holds."""
        report = self.simulate(simulate={"official": {"grace_days": 14, "fail": [1]}})
        day_one = self._day(report, 1)
        self.assertEqual(day_one["observed_status"], "fail")
        self.assertEqual(day_one["confirmed_status"], "pass", "held by the lent grace")
        self.assertEqual(day_one["phase"], "in_grace_period")

    def test_a_removed_grace_period_confirms_immediately(self):
        """null means the criterion has none, which is Official's real behaviour."""
        report = self.simulate(simulate={"official": {"grace_days": None, "fail": [1]}})
        self.assertEqual(self._day(report, 1)["confirmed_status"], "fail")

    def test_the_lent_grace_period_expires_on_schedule(self):
        report = self.simulate(
            simulate={"official": {"grace_days": 14, "fail": list(range(1, 20))}}
        )
        self.assertEqual(
            self._day(report, 14)["confirmed_status"], "pass", "last day inside grace"
        )
        self.assertEqual(
            self._day(report, 15)["confirmed_status"], "fail", "grace outlasted"
        )

    def test_a_lent_probation_opens_on_recovery(self):
        report = self.simulate(
            simulate={
                "official": {
                    "grace_days": None,
                    "probation_days": 180,
                    "fail": [1],
                }
            }
        )
        recovered = self._day(report, 2)
        self.assertEqual(recovered["confirmed_status"], "pass")
        self.assertEqual(recovered["phase"], "on_probation")

    def test_a_removed_probation_never_opens_one(self):
        report = self.simulate(
            simulate={
                "official": {
                    "grace_days": None,
                    "probation_days": None,
                    "fail": [1],
                }
            }
        )
        recovered = self._day(report, 2)
        self.assertEqual(recovered["confirmed_status"], "pass")
        self.assertEqual(recovered["phase"], "steady")
        self.assertIsNone(recovered["probation_start"])

    def test_a_shorter_probation_is_served_sooner(self):
        report = self.simulate(
            simulate={
                "official": {"grace_days": None, "probation_days": 5, "fail": [1]}
            }
        )
        # Probation opens on day 2 and clears once five days have passed.
        self.assertEqual(self._day(report, 6)["phase"], "on_probation")
        self.assertEqual(self._day(report, 7)["phase"], "steady")

    def test_omitting_the_keys_keeps_the_criterion_own_policy(self):
        """The stand-in's own 30-day grace, untouched — a streak from day 1 confirms on 31."""
        report = self.simulate(simulate={"official": {"fail": list(range(1, 40))}})
        self.assertEqual(self._day(report, 30)["confirmed_status"], "pass")
        self.assertEqual(self._day(report, 31)["confirmed_status"], "fail")

    def test_the_report_echoes_the_lent_policy(self):
        report = self.simulate(
            simulate={
                "official": {"grace_days": 14, "probation_days": 180, "fail": [1]}
            }
        )
        echoed = report["simulated"]["official"]
        self.assertEqual(echoed["grace_days"], 14)
        self.assertEqual(echoed["probation_days"], 180)
        self.assertEqual(echoed["1"], "fail")
        # This echo is the shape that used to 500: offsets and policy keys in one dict, which
        # only fails once Flask serializes it, so assert it survives that too.
        self.assertEqual(json.loads(json.dumps(echoed, sort_keys=True)), echoed)

    def test_a_negative_period_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.simulate(simulate={"official": {"grace_days": -1}})
        self.assertIn("negative", str(caught.exception))

    def test_a_non_numeric_period_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.simulate(simulate={"official": {"probation_days": "a fortnight"}})
        self.assertIn("probation_days", str(caught.exception))

    def test_a_lent_policy_never_writes_in_production(self):
        """Same rule as forced verdicts: a fabricated policy must not reach real tables."""
        with patch.dict(os.environ, {"ENVIRONMENT": "prod"}), self.assertRaises(
            ValueError
        ):
            with self.registry(_script_for([])):
                backfill_seals(
                    stable_feed_ids=[MARCHED],
                    start_date=MARCH_START,
                    end_date=MARCH_END,
                    dry_run=False,
                    simulate={"official": {"grace_days": 14}},
                )


class TestSimulatedBaseline(MarchTestCase):
    """`default` is what every unnamed day observes; named days are exceptions on top.

    Without it they fall through to the evaluator, which says nothing useful where the source
    data is absent — as `fresh_coverage` is on a local database.
    """

    def simulate(self, **kwargs):
        # The stand-in passes every day, so a `fail` baseline can only come from the payload.
        with self.registry(_script_for([])):
            return backfill_seals(
                stable_feed_ids=[MARCHED],
                start_date=MARCH_START,
                end_date=MARCH_END,
                dry_run=True,
                trace=True,
                **kwargs,
            )

    def test_a_baseline_replaces_the_evaluator_on_every_unnamed_day(self):
        report = self.simulate(simulate={"official": {"default": "fail"}})
        for day in (0, 1, 5):
            row = trace_day(report, day)
            self.assertEqual(row["observed_status"], "fail", f"day {day}")
            self.assertTrue(row["simulated"])
            self.assertIn("by default", row["reason"])

    def test_a_named_day_overrides_the_baseline(self):
        report = self.simulate(simulate={"official": {"default": "fail", "pass": [2]}})
        self.assertEqual(trace_day(report, 1)["observed_status"], "fail")
        day_two = trace_day(report, 2)
        self.assertEqual(day_two["observed_status"], "pass", "the exception wins")
        self.assertIn("on day 2", day_two["reason"])

    def test_without_a_baseline_unnamed_days_still_fall_through(self):
        report = self.simulate(simulate={"official": {"fail": [2]}})
        self.assertFalse(trace_day(report, 1)["simulated"], "the evaluator answered")

    def test_the_report_echoes_the_baseline(self):
        report = self.simulate(simulate={"official": {"default": "fail", "pass": [2]}})
        echoed = report["simulated"]["official"]
        self.assertEqual(echoed["default"], "fail")
        self.assertEqual(echoed["2"], "pass")

    def test_an_unknown_baseline_status_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.simulate(simulate={"official": {"default": "excellent"}})
        self.assertIn("default", str(caught.exception))

    def test_a_baseline_alone_is_enough_to_march(self):
        """No named day, so nothing to range-check — the baseline still forces the march."""
        report = self.simulate(simulate={"official": {"default": "unknown"}})
        self.assertEqual(trace_day(report, 0)["observed_status"], "unknown")


class TestTraceStandsInForTheSnapshots(MarchTestCase):
    """A trace has to answer what a snapshot would have, because simulate cannot write.

    Both come from the same per-day state in `_march`, so they agree by construction — pinned
    here, since it is the only reason a traced dry run substitutes for stored rows.
    """

    def test_the_trace_carries_every_stored_column(self):
        """A column the snapshot stores and the trace omits would be unanswerable."""
        missing = set(SNAPSHOT_STATE_COLUMNS) - set(TRACED_STATE_FIELDS)
        self.assertEqual(
            missing, set(), f"trace omits stored column(s): {sorted(missing)}"
        )

    @staticmethod
    def _rendered(value):
        """A snapshot value in the trace's shape: status names, timestamps as their day."""
        if hasattr(value, "value"):
            return value.value
        if hasattr(value, "date"):
            return value.date().isoformat()
        return value

    @with_db_session(db_url=default_db_url)
    def test_every_traced_day_matches_its_stored_snapshot(self, db_session=None):
        """A real march, so it may write: every day compared, uncollapsed against stored."""
        report = self.march(
            MARCHED,
            _script_for(range(10, 46)),
            snapshot_mode="all",
            trace=True,
            collapse_trace=False,
        )
        rows = {
            row.snapshot_date.isoformat(): row
            for row in db_session.execute(select(SealCriterionSnapshot.__table__)).all()
        }
        self.assertTrue(rows, "the march wrote no snapshots to compare against")
        self.assertEqual(
            len(report["trace"]), len(rows), "one traced day per stored snapshot"
        )

        for traced in report["trace"]:
            row = rows.get(traced["evaluated_at"])
            self.assertIsNotNone(
                row, f"no snapshot for the traced day {traced['evaluated_at']}"
            )
            for column in SNAPSHOT_STATE_COLUMNS:
                self.assertEqual(
                    traced[column],
                    self._rendered(getattr(row, column)),
                    f"{column} differs on {traced['evaluated_at']}",
                )

    def test_an_uncollapsed_trace_reports_every_marched_day(self):
        report = self.march(
            MARCHED,
            _script_for([20]),
            snapshot_mode="none",
            trace=True,
            collapse_trace=False,
        )
        self.assertFalse(report["trace_collapsed"])
        self.assertEqual(
            len(report["trace"]), (MARCH_END - MARCH_START).days + 1, "one row per day"
        )
        self.assertEqual([row["day"] for row in report["trace"]][:3], [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
