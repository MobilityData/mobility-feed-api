"""Unit tests for locations helper module."""

import unittest
from unittest.mock import MagicMock

from geoalchemy2 import WKTElement
from geoalchemy2.shape import from_shape
from shapely.geometry.point import Point
from shapely.geometry.polygon import Polygon

from locations import (
    translate_feed_locations,
    get_country_code,
    create_or_get_location,
    to_shapely,
    select_highest_level_polygon,
    select_lowest_level_polygon,
    get_country_code_from_polygons,
)
from unittest.mock import patch

from shared.database_gen.sqlacodegen_models import Location, Feed, Geopolygon


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

    def test_to_shapely_wkt_element(self):
        wkt_element = WKTElement("POINT (1 2)", srid=4326)
        result = to_shapely(wkt_element)
        self.assertIsInstance(result, Point)
        self.assertEqual(result.x, 1)
        self.assertEqual(result.y, 2)

    def test_to_shapely_wkb_element(self):
        shapely_point = Point(1, 2)
        wkb_element = from_shape(shapely_point, srid=4326)
        result = to_shapely(wkb_element)
        self.assertIsInstance(result, Point)
        self.assertEqual(result.x, 1)
        self.assertEqual(result.y, 2)

    def test_to_shapely_wkt_string(self):
        wkt_string = "POINT (1 2)"
        result = to_shapely(wkt_string)
        self.assertIsInstance(result, Point)
        self.assertEqual(result.x, 1)
        self.assertEqual(result.y, 2)

    def test_to_shapely_shapely_geometry(self):
        shapely_polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        result = to_shapely(shapely_polygon)
        self.assertIs(result, shapely_polygon)

    def test_to_shapely_invalid_input(self):
        invalid_input = 12345
        result = to_shapely(invalid_input)
        self.assertEqual(result, invalid_input)

    def test_select_highest_level_polygon_mpty_list_returns_none(self):
        result = select_highest_level_polygon([])
        assert result is None

    def test_select_highest_level_polygon_single_polygon(self):
        g1 = Geopolygon(osm_id=1, admin_level=5)
        result = select_highest_level_polygon([g1])
        assert result == g1

    def test_select_highest_level_polygon_multiple_polygons_selects_highest(self):
        g1 = Geopolygon(osm_id=1, admin_level=3)
        g2 = Geopolygon(osm_id=2, admin_level=7)
        g3 = Geopolygon(osm_id=3, admin_level=5)
        result = select_highest_level_polygon([g1, g2, g3])
        assert result == g2

    def test_select_highest_level_polygon_null_admin_level_treated_lowest(self):
        g1 = Geopolygon(osm_id=1, admin_level=None)
        g2 = Geopolygon(osm_id=2, admin_level=4)
        result = select_highest_level_polygon([g1, g2])
        assert result == g2

    def test_select_highest_level_polygon_all_null_admin_levels(self):
        g1 = Geopolygon(osm_id=1, admin_level=None)
        g2 = Geopolygon(osm_id=2, admin_level=None)
        result = select_highest_level_polygon([g1, g2])
        # Should return one of them, but not None
        assert result in [g1, g2]

    def test_select_highest_level_polygon_ties_highest_admin_level(self):
        g1 = Geopolygon(osm_id=1, admin_level=6)
        g2 = Geopolygon(osm_id=2, admin_level=6)
        result = select_highest_level_polygon([g1, g2])
        # Either polygon with admin_level=6 is valid
        assert result.admin_level == 6

    def test_select_lowest_level_polygon_empty_list_returns_none(self):
        self.assertIsNone(select_lowest_level_polygon([]))

    def test_select_lowest_level_polygon_single_polygon_is_returned(self):
        g1 = Geopolygon(osm_id=1, admin_level=5)
        self.assertEqual(g1, select_lowest_level_polygon([g1]))

    def test_select_lowest_level_polygon_chooses_smallest_numeric_level(self):
        g1 = Geopolygon(osm_id=1, admin_level=7)
        g2 = Geopolygon(osm_id=2, admin_level=3)
        g3 = Geopolygon(osm_id=3, admin_level=5)
        result = select_lowest_level_polygon([g1, g2, g3])
        self.assertEqual(g2, result)
        self.assertEqual(3, result.admin_level)

    def test_select_lowest_level_polygon_ignores_none_when_numbers_exist(self):
        g1 = Geopolygon(osm_id=1, admin_level=None)
        g2 = Geopolygon(osm_id=2, admin_level=4)
        result = select_lowest_level_polygon([g1, g2])
        self.assertEqual(g2, result)
        self.assertEqual(4, result.admin_level)

    def test_select_lowest_level_polygon_all_none_returns_one_of_inputs(self):
        g1 = Geopolygon(osm_id=1, admin_level=None)
        g2 = Geopolygon(osm_id=2, admin_level=None)
        result = select_lowest_level_polygon([g1, g2])
        self.assertIn(result, (g1, g2))
        self.assertIsNone(result.admin_level)

    def test_select_lowest_level_polygon_ties_return_one_with_that_level(self):
        g1 = Geopolygon(osm_id=1, admin_level=2)
        g2 = Geopolygon(osm_id=2, admin_level=2)
        result = select_lowest_level_polygon([g1, g2])
        self.assertEqual(2, result.admin_level)

    def test_get_country_code_from_polygons_returns_none_for_empty_list(self):
        self.assertIsNone(get_country_code_from_polygons([]))

    def test_get_country_code_from_polygons_ignores_polygons_without_country_code(self):
        # Only one polygon has an ISO code -> it should be chosen regardless of admin_level
        polys = [
            Geopolygon(osm_id=1, admin_level=5, iso_3166_1_code=None),
            Geopolygon(osm_id=2, admin_level=3, iso_3166_1_code=""),  # falsy -> ignored
            Geopolygon(osm_id=3, admin_level=7, iso_3166_1_code="CA"),
        ]
        self.assertEqual("CA", get_country_code_from_polygons(polys))

    def test_get_country_code_from_polygons_returns_none_when_no_iso_codes_present(
        self,
    ):
        polys = [
            Geopolygon(osm_id=1, admin_level=3, iso_3166_1_code=None),
            Geopolygon(osm_id=2, admin_level=2, iso_3166_1_code=""),
        ]
        self.assertIsNone(get_country_code_from_polygons(polys))

    def test_get_country_code_from_polygons_picks_lowest_admin_level(self):
        # Among those with ISO codes, choose the one with the smallest admin_level
        polys = [
            Geopolygon(osm_id=1, admin_level=7, iso_3166_1_code="US"),
            Geopolygon(osm_id=2, admin_level=3, iso_3166_1_code="CA"),
            Geopolygon(osm_id=3, admin_level=5, iso_3166_1_code="MX"),
        ]
        self.assertEqual(
            "CA", get_country_code_from_polygons(polys)
        )  # admin_level=3 is lowest

    def test_get_country_code_from_polygons_tie_returns_any_with_that_level(self):
        # If two have the same lowest admin_level, either is fine.
        polys = [
            Geopolygon(osm_id=1, admin_level=2, iso_3166_1_code="US"),
            Geopolygon(osm_id=2, admin_level=2, iso_3166_1_code="CA"),
            Geopolygon(osm_id=3, admin_level=4, iso_3166_1_code="MX"),
        ]
        result = get_country_code_from_polygons(polys)
        self.assertIn(result, {"US", "CA"})

    def test_get_country_code_from_polygons_none_admin_levels_are_low_priority_when_numbers_exist(
        self,
    ):
        # If select_lowest_level_polygon treats None as "lowest priority",
        # polygons with numeric admin_level should win over None.
        polys = [
            Geopolygon(osm_id=1, admin_level=None, iso_3166_1_code="US"),
            Geopolygon(osm_id=2, admin_level=4, iso_3166_1_code="CA"),
        ]
        self.assertEqual("CA", get_country_code_from_polygons(polys))

    def test_get_country_code_from_polygons_all_none_admin_levels_returns_one_with_code(
        self,
    ):
        # When all eligible have admin_level=None, any with an ISO code is acceptable.
        polys = [
            Geopolygon(osm_id=1, admin_level=None, iso_3166_1_code="US"),
            Geopolygon(osm_id=2, admin_level=None, iso_3166_1_code="CA"),
        ]
        result = get_country_code_from_polygons(polys)
        self.assertIn(result, {"US", "CA"})
