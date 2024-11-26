"""Unit tests for locations helper module."""

import unittest
from unittest.mock import MagicMock
from database_gen.sqlacodegen_models import Feed, Location
from helpers.locations import (
    translate_feed_locations,
    get_country_code,
    create_or_get_location,
)


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
