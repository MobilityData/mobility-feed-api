import unittest
from unittest.mock import patch, MagicMock

from utils.locations import get_feed_location


class TestFeedsLocations(unittest.TestCase):
    @patch("utils.locations.Database")
    @patch("utils.locations.os.getenv")
    @patch("utils.locations.joinedload")
    def test_get_feeds_locations_map(self, _, mock_getenv, mock_database):
        mock_getenv.return_value = "fake_database_url"

        mock_session = MagicMock()
        mock_database.return_value.start_db_session.return_value.__enter__.return_value = (
            mock_session
        )

        mock_feed = MagicMock()
        mock_feed.stable_id = "feed1"
        mock_location1 = MagicMock()
        mock_location2 = MagicMock()
        mock_feed.locations = [mock_location1, mock_location2]

        mock_query = MagicMock()
        mock_query.filter.return_value.filter.return_value.options.return_value.all.return_value = [
            mock_feed
        ]

        mock_session.query.return_value = mock_query
        result = get_feed_location("gtfs", "feed1")

        mock_database.assert_called_once_with(database_url="fake_database_url")
        mock_session.query.assert_called_once()  # Verify that query was called
        mock_query.filter.assert_called_once()  # Verify that filter was applied
        mock_query.filter.return_value.filter.return_value.options.assert_called_once()
        mock_query.filter.return_value.filter.return_value.options.return_value.all.assert_called_once()

        self.assertEqual(result, [mock_location1, mock_location2])  # Verify the mapping

    @patch("utils.locations.Database")
    def test_get_feeds_locations_map_no_feeds(self, mock_database):
        mock_session = MagicMock()
        mock_database.return_value.start_db_session.return_value = mock_session

        mock_query = MagicMock()
        mock_query.filter.return_value.filter.return_value.options.return_value.all.return_value = (
            []
        )

        mock_session.query.return_value = mock_query

        result = get_feed_location("test_data_type", "test_stable_id")

        mock_database.return_value.start_db_session.assert_called_once()
        self.assertEqual(result, [])  # The result should be an empty dictionary
