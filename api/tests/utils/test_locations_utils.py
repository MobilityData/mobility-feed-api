"""Unit tests for locations helper module."""
import unittest
from unittest.mock import MagicMock

from unittest.mock import patch

from shared.common.locations_utils import get_country_code, create_or_get_location
from shared.database_gen.sqlacodegen_models import Location


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
        self.session.query.return_value.filter.return_value.first.return_value = mock_location

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
        result = create_or_get_location(self.session, country=None, state_province=None, city_name=None)
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

    def test_get_country_code_fuzzy_match_partial(self):
        """Test getting country code with partial name matches"""
        # Test partial name matches
        self.assertEqual(get_country_code("United"), "US")  # Should match United States
        self.assertEqual(get_country_code("South Korea"), "KR")  # Republic of Korea
        self.assertEqual(get_country_code("North Korea"), "KP")  # Democratic People's Republic of Korea
        self.assertEqual(get_country_code("Great Britain"), "GB")  # Should match United Kingdom

    @patch("shared.common.locations_utils.logging.error")
    def test_get_country_code_empty_string(self, mock_logging):
        """Test getting country code with empty string"""
        self.assertIsNone(get_country_code(""))
        mock_logging.assert_called_with("Could not find country code for: empty string")

    def test_create_or_get_location_partial_info(self):
        """Test creating location with partial information"""
        self.session.query.return_value.filter.return_value.first.return_value = None

        # Test with only country
        result = create_or_get_location(self.session, country="United States", state_province=None, city_name=None)
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
