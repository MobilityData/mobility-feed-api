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

import unittest
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, insert

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Feed, Gtfsfeed, SealCriterion
from tasks.seal_of_reliability.backfill.backfill_seal_of_reliability import (
    _parse_day,
    backfill_seal_of_reliability_handler,
    get_parameters,
)
from tasks.seal_of_reliability.backfill.seal_backfill import (
    DEFAULT_DAYS_BACK,
    backfill_seals,
    march_start_for,
    resolve_window,
    yesterday_utc,
)
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
        self.assertFalse(report["implemented"])
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


class TestBackfillValidation(BackfillDbTestCase):
    def test_a_real_run_refuses_rather_than_writing_nothing(self):
        """Until the march exists, reporting success would be worse than failing."""
        with self.assertRaises(NotImplementedError) as caught:
            backfill_seals(
                stable_feed_ids=[OLD], start_date=START, end_date=END, dry_run=False
            )
        self.assertIn("#1763", str(caught.exception))

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


if __name__ == "__main__":
    unittest.main()
