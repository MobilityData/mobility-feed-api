import unittest
from unittest.mock import MagicMock

from locations import get_feed_location, Location


class TestFeedsLocations(unittest.TestCase):
    def test_get_feeds_locations_map(self):
        mock_database = MagicMock()

        mock_session = MagicMock()
        mock_database.return_value.start_db_session.return_value.__enter__.return_value = (
            mock_session
        )

        mock_feed = MagicMock()
        mock_feed.stable_id = "feed1"
        mock_location1 = Location(
            country_code="US",
            country="United States",
            subdivision_name="California",
            municipality="San Francisco",
        )
        mock_location2 = Location(
            country_code="US",
            country="United States",
            subdivision_name="California",
            municipality="Los Angeles",
        )
        mock_feed.locations = [mock_location1, mock_location2]

        mock_query = MagicMock()
        mock_query.filter.return_value.options.return_value.all.return_value = [
            mock_feed
        ]

        mock_session.query.return_value = mock_query
        result = get_feed_location("feed1", db_session=mock_session)

        mock_session.query.assert_called_once()  # Verify that query was called
        mock_query.filter.assert_called_once()  # Verify that filter was applied
        mock_query.filter.return_value.options.assert_called_once()
        mock_query.filter.return_value.options.return_value.all.assert_called_once()

        self.assertEqual(result, [mock_location1, mock_location2])  # Verify the mapping

    def test_get_feeds_locations_map_no_feeds(self):
        mock_session = MagicMock()

        mock_query = MagicMock()
        mock_query.filter.return_value.options.return_value.all.return_value = []

        mock_session.query.return_value = mock_query

        result = get_feed_location("test_stable_id", db_session=mock_session)

        self.assertEqual(result, [])  # The result should be an empty dictionary
