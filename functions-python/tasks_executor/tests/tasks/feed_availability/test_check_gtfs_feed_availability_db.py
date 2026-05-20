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

from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from tasks.feed_availability.check_gtfs_feed_availability import get_feeds_query
from test_shared.test_utils.database_utils import default_db_url

EXPECTED_AVAILABILITY_IDS = {"feed_availability_1", "feed_availability_2"}


class TestGetFeedsQueryDB(unittest.TestCase):
    """Integration tests for get_feeds_query against the real test database.

    Seed data (from conftest.py) includes:
      - feed_availability_1: active, published, gtfs, has producer_url  → MATCH
      - feed_availability_2: active, published, gtfs, has producer_url  → MATCH
      - feed_availability_inactive: inactive, published, gtfs, has producer_url → NO MATCH
      - feed_availability_no_url: active, published, gtfs, no producer_url     → NO MATCH
    """

    @with_db_session(db_url=default_db_url)
    def test_returns_only_active_published_feeds_with_url(self, db_session: Session):
        """Only active+published GTFS feeds that have a producer_url are returned."""
        results = get_feeds_query(db_session).all()
        result_ids = {f.id for f in results}
        self.assertTrue(
            EXPECTED_AVAILABILITY_IDS.issubset(result_ids),
            f"Expected {EXPECTED_AVAILABILITY_IDS} to be in results, got {result_ids}",
        )
        # Inactive feed must NOT appear
        self.assertNotIn("feed_availability_inactive", result_ids)
        # Feed without producer_url must NOT appear
        self.assertNotIn("feed_availability_no_url", result_ids)

    @with_db_session(db_url=default_db_url)
    def test_feed_ids_filter_returns_only_requested_feeds(self, db_session: Session):
        """Providing feed_ids restricts results to exactly those feeds."""
        results = get_feeds_query(db_session, feed_ids=["feed_availability_1"]).all()
        result_ids = {f.id for f in results}
        self.assertEqual(result_ids, {"feed_availability_1"})

    @with_db_session(db_url=default_db_url)
    def test_feed_ids_filter_with_multiple_ids(self, db_session: Session):
        """Multiple feed_ids are all returned when they match the base filters."""
        results = get_feeds_query(
            db_session, feed_ids=["feed_availability_1", "feed_availability_2"]
        ).all()
        result_ids = {f.id for f in results}
        self.assertEqual(result_ids, EXPECTED_AVAILABILITY_IDS)

    @with_db_session(db_url=default_db_url)
    def test_feed_ids_filter_excludes_non_matching_ids(self, db_session: Session):
        """feed_ids that don't satisfy base filters (inactive) are excluded."""
        results = get_feeds_query(
            db_session, feed_ids=["feed_availability_inactive"]
        ).all()
        self.assertEqual(len(results), 0)

    @with_db_session(db_url=default_db_url)
    def test_feed_ids_with_unknown_id_returns_empty(self, db_session: Session):
        """An unknown feed_id returns an empty result set."""
        results = get_feeds_query(db_session, feed_ids=["nonexistent_feed"]).all()
        self.assertEqual(len(results), 0)

    @with_db_session(db_url=default_db_url)
    def test_limit_caps_the_result_count(self, db_session: Session):
        """Applying a limit on the returned query caps the number of results."""
        results = get_feeds_query(db_session).limit(1).all()
        self.assertEqual(len(results), 1)

    @with_db_session(db_url=default_db_url)
    def test_returned_feeds_have_producer_url(self, db_session: Session):
        """Every returned feed must have a non-null producer_url."""
        results = get_feeds_query(db_session).all()
        for feed in results:
            self.assertIsNotNone(
                feed.producer_url,
                f"Feed {feed.id} has a null producer_url but should have been filtered out",
            )


if __name__ == "__main__":
    unittest.main()
