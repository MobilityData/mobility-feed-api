"""Unit tests for locations helper module."""

import unittest
from unittest.mock import MagicMock
from database_gen.sqlacodegen_models import Feed, Location
from locations import (
    translate_feed_locations,
    get_country_code,
    create_or_get_location,
)
from unittest.mock import patch


class TestLocations(unittest.TestCase):
    """Test cases for location-related functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.session = MagicMock()

    def test_get_country_code_exact_match(self):
        """Test getting country code with exact name match."""
        self.assertEqual(get_country_code("France"), "FR")
        self.assertEqual(get_country_code("United States"), "US")

    def test_get_country_code_fuzzy_match(self):
        """Test getting country code with fuzzy matching."""
        self.assertEqual(get_country_code("USA"), "US")
        self.assertEqual(get_country_code("United Kingdom of Great Britain"), "GB")

    def test_get_country_code_invalid(self):
        """Test getting country code with invalid country name."""
        self.assertIsNone(get_country_code("Invalid Country Name"))

    def test_create_or_get_location_existing(self):
        """Test retrieving existing location."""
        mock_location = Location(
            id="US-California-San Francisco",
            country_code="US",
            country="United States",
            subdivision_name="California",
            municipality="San Francisco",
        )
        self.session.query.return_value.filter.return_value.first.return_value = (
            mock_location
        )

        result = create_or_get_location(
            self.session,
            country="United States",
            state_province="California",
            city_name="San Francisco",
        )

        self.assertEqual(result, mock_location)
        self.session.add.assert_not_called()

    def test_create_or_get_location_new(self):
        """Test creating new location."""
        self.session.query.return_value.filter.return_value.first.return_value = None

        result = create_or_get_location(
            self.session,
            country="United States",
            state_province="California",
            city_name="San Francisco",
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.id, "US-California-San Francisco")
        self.assertEqual(result.country_code, "US")
        self.assertEqual(result.country, "United States")
        self.assertEqual(result.subdivision_name, "California")
        self.assertEqual(result.municipality, "San Francisco")
        self.session.add.assert_called_once()

    def test_create_or_get_location_no_inputs(self):
        """Test with no location information provided."""
        result = create_or_get_location(
            self.session, country=None, state_province=None, city_name=None
        )
        self.assertIsNone(result)

    def test_create_or_get_location_invalid_country(self):
        """Test with invalid country name."""
        result = create_or_get_location(
            self.session,
            country="Invalid Country",
            state_province="State",
            city_name="City",
        )
        self.assertIsNone(result)

    def test_translate_feed_locations(self):
        """Test translating feed locations with all translations available."""
        mock_location = MagicMock(spec=Location)
        mock_location.id = 1
        mock_location.subdivision_name = "Original Subdivision"
        mock_location.municipality = "Original Municipality"
        mock_location.country = "Original Country"

        mock_feed = MagicMock(spec=Feed)
        mock_feed.locations = [mock_location]

        location_translations = {
            1: {
                "subdivision_name_translation": "Translated Subdivision",
                "municipality_translation": "Translated Municipality",
                "country_translation": "Translated Country",
            }
        }

        translate_feed_locations(mock_feed, location_translations)

        self.assertEqual(mock_location.subdivision_name, "Translated Subdivision")
        self.assertEqual(mock_location.municipality, "Translated Municipality")
        self.assertEqual(mock_location.country, "Translated Country")

    def test_translate_feed_locations_with_missing_translations(self):
        """Test translating feed locations with some missing translations."""
        mock_location = MagicMock(spec=Location)
        mock_location.id = 1
        mock_location.subdivision_name = "Original Subdivision"
        mock_location.municipality = "Original Municipality"
        mock_location.country = "Original Country"

        mock_feed = MagicMock(spec=Feed)
        mock_feed.locations = [mock_location]

        location_translations = {
            1: {
                "subdivision_name_translation": None,
                "municipality_translation": None,
                "country_translation": "Translated Country",
            }
        }

        translate_feed_locations(mock_feed, location_translations)

        self.assertEqual(mock_location.subdivision_name, "Original Subdivision")
        self.assertEqual(mock_location.municipality, "Original Municipality")
        self.assertEqual(mock_location.country, "Translated Country")

    def test_translate_feed_locations_with_no_translation(self):
        """Test translating feed locations with no translations available."""
        mock_location = MagicMock(spec=Location)
        mock_location.id = 1
        mock_location.subdivision_name = "Original Subdivision"
        mock_location.municipality = "Original Municipality"
        mock_location.country = "Original Country"

        mock_feed = MagicMock(spec=Feed)
        mock_feed.locations = [mock_location]

        location_translations = {}

        translate_feed_locations(mock_feed, location_translations)

        self.assertEqual(mock_location.subdivision_name, "Original Subdivision")
        self.assertEqual(mock_location.municipality, "Original Municipality")
        self.assertEqual(mock_location.country, "Original Country")

    def test_get_country_code_fuzzy_match_partial(self):
        """Test getting country code with partial name matches"""
        # Test partial name matches
        self.assertEqual(get_country_code("United"), "US")  # Should match United States
        self.assertEqual(get_country_code("South Korea"), "KR")  # Republic of Korea
        self.assertEqual(
            get_country_code("North Korea"), "KP"
        )  # Democratic People's Republic of Korea
        self.assertEqual(
            get_country_code("Great Britain"), "GB"
        )  # Should match United Kingdom

    @patch("locations.logging.error")
    def test_get_country_code_empty_string(self, mock_logging):
        """Test getting country code with empty string"""
        self.assertIsNone(get_country_code(""))
        mock_logging.assert_called_with("Could not find country code for: empty string")

    def test_create_or_get_location_partial_info(self):
        """Test creating location with partial information"""
        self.session.query.return_value.filter.return_value.first.return_value = None

        # Test with only country
        result = create_or_get_location(
            self.session, country="United States", state_province=None, city_name=None
        )
        self.assertEqual(result.id, "US")
        self.assertEqual(result.country_code, "US")
        self.assertEqual(result.country, "United States")
        self.assertIsNone(result.subdivision_name)
        self.assertIsNone(result.municipality)

        # Test with country and state
        result = create_or_get_location(
            self.session,
            country="United States",
            state_province="California",
            city_name=None,
        )
        self.assertEqual(result.id, "US-California")
        self.assertEqual(result.country_code, "US")
        self.assertEqual(result.country, "United States")
        self.assertEqual(result.subdivision_name, "California")
        self.assertIsNone(result.municipality)

    def test_translate_feed_locations_partial_translations(self):
        """Test translating feed locations with partial translations"""
        mock_location = MagicMock(spec=Location)
        mock_location.id = "loc1"
        mock_location.subdivision_name = "Original State"
        mock_location.municipality = "Original City"
        mock_location.country = "Original Country"

        mock_feed = MagicMock(spec=Feed)
        mock_feed.locations = [mock_location]

        # Test with only some fields translated
        translations = {
            "loc1": {
                "subdivision_name_translation": "Translated State",
                "municipality_translation": None,  # No translation
                "country_translation": "Translated Country",
            }
        }

        translate_feed_locations(mock_feed, translations)

        # Verify partial translations
        self.assertEqual(mock_location.subdivision_name, "Translated State")
        self.assertEqual(
            mock_location.municipality, "Original City"
        )  # Should remain unchanged
        self.assertEqual(mock_location.country, "Translated Country")

    def test_translate_feed_locations_multiple_locations(self):
        """Test translating multiple locations in a feed"""
        # Create multiple mock locations
        mock_location1 = MagicMock(spec=Location)
        mock_location1.id = "loc1"
        mock_location1.subdivision_name = "Original State 1"
        mock_location1.municipality = "Original City 1"
        mock_location1.country = "Original Country 1"

        mock_location2 = MagicMock(spec=Location)
        mock_location2.id = "loc2"
        mock_location2.subdivision_name = "Original State 2"
        mock_location2.municipality = "Original City 2"
        mock_location2.country = "Original Country 2"

        mock_feed = MagicMock(spec=Feed)
        mock_feed.locations = [mock_location1, mock_location2]

        # Translations for both locations
        translations = {
            "loc1": {
                "subdivision_name_translation": "Translated State 1",
                "municipality_translation": "Translated City 1",
                "country_translation": "Translated Country 1",
            },
            "loc2": {
                "subdivision_name_translation": "Translated State 2",
                "municipality_translation": "Translated City 2",
                "country_translation": "Translated Country 2",
            },
        }

        translate_feed_locations(mock_feed, translations)

        # Verify translations for first location
        self.assertEqual(mock_location1.subdivision_name, "Translated State 1")
        self.assertEqual(mock_location1.municipality, "Translated City 1")
        self.assertEqual(mock_location1.country, "Translated Country 1")

        # Verify translations for second location
        self.assertEqual(mock_location2.subdivision_name, "Translated State 2")
        self.assertEqual(mock_location2.municipality, "Translated City 2")
        self.assertEqual(mock_location2.country, "Translated Country 2")
