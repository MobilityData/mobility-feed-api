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
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Feed,
    GtfsDatasetChangelog,
    Gtfsdataset,
    Gtfsfeed,
)
from tasks.changelog.backfill_changelog import (
    DEFAULT_DATASETS_PER_FEED,
    DEFAULT_LIMIT,
    backfill_changelog,
    backfill_changelog_handler,
)
from test_shared.test_utils.database_utils import default_db_url

PATCH_DISPATCH = (
    "tasks.changelog.backfill_changelog.create_http_gtfs_datasets_comparer_task"
)
# Scope every query to our own feeds so the shared conftest seed data does not
# affect counts (and so we never wipe it).
SCOPE = ["stable_a", "stable_b"]


@with_db_session(db_url=default_db_url)
def seed(db_session: Session):
    """Seed two published GTFS feeds with dataset history.

    feed_a: 3 datasets (a0 oldest -> a2 newest), one existing changelog (a0->a1).
    feed_b: 1 dataset (no pairs possible).

    Only our own rows are touched: existing feed_a/feed_b are deleted first
    (FK cascade removes their datasets and changelogs), then re-inserted.
    """
    db_session.query(Feed).filter(Feed.id.in_(["feed_a", "feed_b"])).delete(
        synchronize_session=False
    )
    db_session.commit()
    now = datetime.now(timezone.utc)

    feed_a = Gtfsfeed(
        id="feed_a",
        stable_id="stable_a",
        data_type="gtfs",
        status="active",
        operational_status="published",
        created_at=now,
    )
    feed_b = Gtfsfeed(
        id="feed_b",
        stable_id="stable_b",
        data_type="gtfs",
        status="active",
        operational_status="published",
        created_at=now,
    )
    db_session.add_all([feed_a, feed_b])
    db_session.flush()

    for i in range(3):
        db_session.add(
            Gtfsdataset(
                id=f"a{i}",
                stable_id=f"stable_a{i}",
                feed_id="feed_a",
                downloaded_at=now - timedelta(days=10 - i),
            )
        )
    db_session.add(
        Gtfsdataset(
            id="b0",
            stable_id="stable_b0",
            feed_id="feed_b",
            downloaded_at=now - timedelta(days=5),
        )
    )
    db_session.flush()

    # Existing changelog for the oldest pair (a0 -> a1) => must be skipped.
    db_session.add(
        GtfsDatasetChangelog(
            feed_id="feed_a",
            base_dataset_id="a0",
            new_dataset_id="a1",
            changelog_url="https://example.com/changelog.json",
            diff_summary={},
        )
    )
    db_session.commit()


class TestBackfillChangelogHandler(unittest.TestCase):
    @patch("tasks.changelog.backfill_changelog.backfill_changelog")
    def test_handler_default_params(self, mock_backfill):
        mock_backfill.return_value = {"message": "ok"}
        backfill_changelog_handler({})
        mock_backfill.assert_called_once_with(
            dry_run=True,
            limit=DEFAULT_LIMIT,
            datasets_per_feed=DEFAULT_DATASETS_PER_FEED,
            stable_feed_ids=None,
            feeds_not_updated_days=None,
            force=False,
        )

    @patch("tasks.changelog.backfill_changelog.backfill_changelog")
    def test_handler_custom_params(self, mock_backfill):
        mock_backfill.return_value = {"message": "ok"}
        backfill_changelog_handler(
            {
                "dry_run": False,
                "limit": 5,
                "datasets_per_feed": 4,
                "stable_feed_ids": ["stable_a"],
                "feeds_not_updated_days": 30,
                "force": True,
            }
        )
        mock_backfill.assert_called_once_with(
            dry_run=False,
            limit=5,
            datasets_per_feed=4,
            stable_feed_ids=["stable_a"],
            feeds_not_updated_days=30,
            force=True,
        )


class TestBackfillChangelog(unittest.TestCase):
    def setUp(self):
        seed()

    @patch(PATCH_DISPATCH)
    def test_dry_run_enumerates_without_dispatch(self, mock_dispatch):
        result = backfill_changelog(dry_run=True, stable_feed_ids=SCOPE)
        mock_dispatch.assert_not_called()
        self.assertTrue(result["dry_run"])
        # feed_a has 3 datasets -> 2 pairs; a0->a1 already done -> 1 to dispatch.
        self.assertEqual(result["feeds_processed"], 1)
        self.assertEqual(result["pairs_found"], 2)
        self.assertEqual(result["pairs_already_done"], 1)
        self.assertEqual(result["pairs_dispatched"], 1)
        self.assertEqual(
            result["dispatched"],
            [
                {
                    "feed_stable_id": "stable_a",
                    "base_dataset_stable_id": "stable_a1",
                    "new_dataset_stable_id": "stable_a2",
                }
            ],
        )

    @patch(PATCH_DISPATCH)
    def test_dispatches_missing_pair(self, mock_dispatch):
        result = backfill_changelog(dry_run=False, stable_feed_ids=SCOPE)
        self.assertEqual(result["pairs_dispatched"], 1)
        mock_dispatch.assert_called_once_with(
            feed_stable_id="stable_a",
            base_dataset_stable_id="stable_a1",
            new_dataset_stable_id="stable_a2",
            disallow_overwrite=True,
        )

    @patch(PATCH_DISPATCH)
    def test_force_dispatch_allows_overwrite(self, mock_dispatch):
        # force=True must dispatch every pair with disallow_overwrite=False so the
        # comparer regenerates even existing changelogs.
        result = backfill_changelog(dry_run=False, force=True, stable_feed_ids=SCOPE)
        self.assertEqual(result["pairs_dispatched"], 2)
        for call in mock_dispatch.call_args_list:
            self.assertFalse(call.kwargs["disallow_overwrite"])

    @patch(PATCH_DISPATCH)
    def test_idempotent_when_all_pairs_done(self, mock_dispatch):
        # Add the missing changelog so no pair remains.
        @with_db_session(db_url=default_db_url)
        def add_remaining(db_session: Session):
            db_session.add(
                GtfsDatasetChangelog(
                    feed_id="feed_a",
                    base_dataset_id="a1",
                    new_dataset_id="a2",
                    changelog_url="https://example.com/c2.json",
                    diff_summary={},
                )
            )
            db_session.commit()

        add_remaining()
        result = backfill_changelog(dry_run=False, stable_feed_ids=SCOPE)
        mock_dispatch.assert_not_called()
        self.assertEqual(result["pairs_dispatched"], 0)
        self.assertEqual(result["pairs_already_done"], 2)

    @patch(PATCH_DISPATCH)
    def test_datasets_per_feed_limits_pairs(self, mock_dispatch):
        # Only consider the 2 most recent datasets (a1, a2) -> single pair a1->a2.
        result = backfill_changelog(
            dry_run=True, datasets_per_feed=2, stable_feed_ids=SCOPE
        )
        self.assertEqual(result["pairs_found"], 1)
        self.assertEqual(result["pairs_dispatched"], 1)

    @patch(PATCH_DISPATCH)
    def test_stable_feed_ids_filter(self, mock_dispatch):
        result = backfill_changelog(dry_run=True, stable_feed_ids=["stable_b"])
        # feed_b has a single dataset -> no pairs.
        self.assertEqual(result["feeds_processed"], 0)
        self.assertEqual(result["pairs_found"], 0)

    @patch(PATCH_DISPATCH)
    def test_unknown_stable_feed_id_raises(self, mock_dispatch):
        with self.assertRaises(ValueError):
            backfill_changelog(dry_run=True, stable_feed_ids=["does_not_exist"])

    @patch(PATCH_DISPATCH)
    def test_feeds_not_updated_days_skips_recent(self, mock_dispatch):
        # feed_a newest dataset is ~7 days old; a 30-day cutoff skips it as "recent".
        result = backfill_changelog(
            dry_run=True, feeds_not_updated_days=30, stable_feed_ids=SCOPE
        )
        self.assertEqual(result["feeds_processed"], 0)
        self.assertEqual(result["feeds_skipped_recent"], 1)
        # With a 1-day cutoff the feed is old enough to be processed.
        result = backfill_changelog(
            dry_run=True, feeds_not_updated_days=1, stable_feed_ids=SCOPE
        )
        self.assertEqual(result["feeds_processed"], 1)

    @patch(PATCH_DISPATCH)
    def test_force_redispatches_existing_pairs(self, mock_dispatch):
        # With force=True the already-done a0->a1 pair is dispatched too.
        result = backfill_changelog(dry_run=True, force=True, stable_feed_ids=SCOPE)
        self.assertTrue(result["force"])
        self.assertEqual(result["pairs_found"], 2)
        self.assertEqual(result["pairs_already_done"], 0)
        self.assertEqual(result["pairs_dispatched"], 2)

    @patch(PATCH_DISPATCH)
    def test_min_datasets_filter_excludes_short_feeds(self, mock_dispatch):
        # feed_b (1 dataset) is excluded from processing, only feed_a remains.
        result = backfill_changelog(dry_run=True, stable_feed_ids=SCOPE)
        self.assertEqual(result["feeds_processed"], 1)

    @patch(PATCH_DISPATCH)
    def test_existing_feed_with_few_datasets_not_reported_missing(self, mock_dispatch):
        # stable_b exists but has <2 datasets: it must not raise "not found".
        result = backfill_changelog(dry_run=True, stable_feed_ids=["stable_b"])
        self.assertEqual(result["feeds_processed"], 0)
        self.assertEqual(result["pairs_found"], 0)

    @patch(PATCH_DISPATCH)
    def test_invalid_datasets_per_feed_raises(self, mock_dispatch):
        with self.assertRaises(ValueError):
            backfill_changelog(dry_run=True, datasets_per_feed=1)


if __name__ == "__main__":
    unittest.main()
