import unittest
from unittest.mock import MagicMock
from database_gen.sqlacodegen_models import Feed, Location
from helpers.locations import translate_feed_locations


class TestTranslateFeedLocations(unittest.TestCase):
    def test_translate_feed_locations(self):
        # Mock a location object with specific attributes
        mock_location = MagicMock(spec=Location)
        mock_location.id = 1
        mock_location.subdivision_name = "Original Subdivision"
        mock_location.municipality = "Original Municipality"
        mock_location.country = "Original Country"

        # Mock a feed object with locations
        mock_feed = MagicMock(spec=Feed)
        mock_feed.locations = [mock_location]

        # Define a translation dictionary
        location_translations = {
            1: {
                "subdivision_name_translation": "Translated Subdivision",
                "municipality_translation": "Translated Municipality",
                "country_translation": "Translated Country",
            }
        }

        # Call the translate_feed_locations function
        translate_feed_locations(mock_feed, location_translations)

        # Assert that the location's attributes were updated with translations
        self.assertEqual(mock_location.subdivision_name, "Translated Subdivision")
        self.assertEqual(mock_location.municipality, "Translated Municipality")
        self.assertEqual(mock_location.country, "Translated Country")

    def test_translate_feed_locations_with_missing_translations(self):
        # Mock a location object with specific attributes
        mock_location = MagicMock(spec=Location)
        mock_location.id = 1
        mock_location.subdivision_name = "Original Subdivision"
        mock_location.municipality = "Original Municipality"
        mock_location.country = "Original Country"

        # Mock a feed object with locations
        mock_feed = MagicMock(spec=Feed)
        mock_feed.locations = [mock_location]

        # Define a translation dictionary with missing translations
        location_translations = {
            1: {
                "subdivision_name_translation": None,
                "municipality_translation": None,
                "country_translation": "Translated Country",
            }
        }

        # Call the translate_feed_locations function
        translate_feed_locations(mock_feed, location_translations)

        # Assert that the location's attributes were updated correctly
        self.assertEqual(
            mock_location.subdivision_name, "Original Subdivision"
        )  # No translation
        self.assertEqual(
            mock_location.municipality, "Original Municipality"
        )  # No translation
        self.assertEqual(mock_location.country, "Translated Country")  # Translated

    def test_translate_feed_locations_with_no_translation(self):
        # Mock a location object with specific attributes
        mock_location = MagicMock(spec=Location)
        mock_location.id = 1
        mock_location.subdivision_name = "Original Subdivision"
        mock_location.municipality = "Original Municipality"
        mock_location.country = "Original Country"

        # Mock a feed object with locations
        mock_feed = MagicMock(spec=Feed)
        mock_feed.locations = [mock_location]

        # Define an empty translation dictionary
        location_translations = {}

        # Call the translate_feed_locations function
        translate_feed_locations(mock_feed, location_translations)

        # Assert that the location's attributes remain unchanged
        self.assertEqual(mock_location.subdivision_name, "Original Subdivision")
        self.assertEqual(mock_location.municipality, "Original Municipality")
        self.assertEqual(mock_location.country, "Original Country")
