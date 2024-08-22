import unittest
from unittest.mock import patch, MagicMock

from validation_to_ndjson.src.utils.locations import get_feed_location


class TestFeedsLocations(unittest.TestCase):
    @patch("validation_to_ndjson.src.utils.locations.start_db_session")
    @patch("validation_to_ndjson.src.utils.locations.os.getenv")
    @patch("validation_to_ndjson.src.utils.locations.joinedload")
    def test_get_feeds_locations_map(self, _, mock_getenv, mock_start_db_session):
        mock_getenv.return_value = "fake_database_url"

        mock_session = MagicMock()
        mock_start_db_session.return_value = mock_session

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

        mock_start_db_session.assert_called_once_with("fake_database_url")
        mock_session.query.assert_called_once()  # Verify that query was called
        mock_query.filter.assert_called_once()  # Verify that filter was applied
        mock_query.filter.return_value.filter.return_value.options.assert_called_once()
        mock_query.filter.return_value.filter.return_value.options.return_value.all.assert_called_once()

        self.assertEqual(result, [mock_location1, mock_location2])  # Verify the mapping

    @patch("validation_to_ndjson.src.utils.locations.start_db_session")
    def test_get_feeds_locations_map_no_feeds(self, mock_start_db_session):
        mock_session = MagicMock()
        mock_start_db_session.return_value = mock_session

        mock_query = MagicMock()
        mock_query.filter.return_value.filter.return_value.options.return_value.all.return_value = (
            []
        )

        mock_session.query.return_value = mock_query

        result = get_feed_location("test_data_type", "test_stable_id")

        mock_start_db_session.assert_called_once()
        self.assertEqual(result, [])  # The result should be an empty dictionary
