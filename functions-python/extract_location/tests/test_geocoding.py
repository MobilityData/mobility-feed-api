import unittest
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from reverse_geolocation.geocoded_location import GeocodedLocation
from reverse_geolocation.location_extractor import (
    reverse_coords,
    update_location,
)


class TestGeocoding(unittest.TestCase):
    # Temporry removal. Reinstate before merging
    # def test_reverse_coord(self):
    #     lat, lon = 34.0522, -118.2437  # Coordinates for Los Angeles, California, USA
    #     result = GeocodedLocation.reverse_coord(lat, lon)
    #     self.assertEqual(result, ("US", "United States", "California", "Los Angeles"))

    @patch("requests.get")
    def test_reverse_coords(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "address": {
                "country_code": "us",
                "country": "United States",
                "state": "California",
                "city": "Los Angeles",
            }
        }
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        points = [(34.0522, -118.2437), (37.7749, -122.4194)]
        location_info = reverse_coords(points)
        self.assertEqual(len(location_info), 1)
        location_info = location_info[0]

        self.assertEqual(location_info.country_code, "US")
        self.assertEqual(location_info.country, "United States")
        self.assertEqual(location_info.subdivision_name, "California")
        self.assertEqual(location_info.municipality, "Los Angeles")

    @patch.object(GeocodedLocation, "reverse_coord")
    def test_generate_translation_no_translation(self, mock_reverse_coord):
        mock_reverse_coord.return_value = (
            "US",
            "United States",
            "California",
            "San Francisco",
        )

        location = GeocodedLocation(
            country_code="US",
            country="United States",
            municipality="San Francisco",
            subdivision_name="California",
            stop_coords=(37.7749, -122.4194),
        )

        location.generate_translation(language="en")
        self.assertEqual(len(location.translations), 0)

    @patch.object(GeocodedLocation, "reverse_coord")
    def test_generate_translation(self, mock_reverse_coord):
        mock_reverse_coord.return_value = ("JP", "Japan", "Tokyo", "Shibuya")

        location = GeocodedLocation(
            country_code="JP",
            country="日本",
            municipality="渋谷区",
            subdivision_name="東京都",
            stop_coords=(35.6895, 139.6917),
        )

        self.assertEqual(len(location.translations), 1)
        self.assertEqual(location.translations[0].country, "Japan")
        self.assertEqual(location.translations[0].language, "en")
        self.assertEqual(location.translations[0].municipality, "Shibuya")
        self.assertEqual(location.translations[0].subdivision_name, "Tokyo")

    @patch.object(GeocodedLocation, "reverse_coord")
    def test_no_duplicate_translation(self, mock_reverse_coord):
        mock_reverse_coord.return_value = (
            "US",
            "United States",
            "California",
            "San Francisco",
        )

        location = GeocodedLocation(
            country_code="US",
            country="United States",
            municipality="San Francisco",
            subdivision_name="California",
            stop_coords=(37.7749, -122.4194),
        )

        location.generate_translation(language="en")
        initial_translation_count = len(location.translations)

        location.generate_translation(language="en")
        self.assertEqual(len(location.translations), initial_translation_count)

    @patch.object(GeocodedLocation, "reverse_coord")
    def test_generate_translation_different_language(self, mock_reverse_coord):
        mock_reverse_coord.return_value = (
            "US",
            "États-Unis",
            "Californie",
            "San Francisco",
        )

        location = GeocodedLocation(
            country_code="US",
            country="United States",
            municipality="San Francisco",
            subdivision_name="California",
            stop_coords=(37.7749, -122.4194),
        )

        location.generate_translation(language="fr")
        self.assertEqual(len(location.translations), 2)
        self.assertEqual(location.translations[1].country, "États-Unis")
        self.assertEqual(location.translations[1].language, "fr")
        self.assertEqual(location.translations[1].municipality, "San Francisco")
        self.assertEqual(location.translations[1].subdivision_name, "Californie")

    @patch("reverse_geolocation.geocoded_location.GeocodedLocation.reverse_coord")
    def test_reverse_coords_decision(self, mock_reverse_coord):
        mock_reverse_coord.side_effect = [
            ("US", "United States", "California", "Los Angeles"),
            ("US", "United States", "California", "San Francisco"),
            ("US", "United States", "California", "San Diego"),
            ("US", "United States", "California", "San Francisco"),
            ("US", "United States", "California", "San Francisco"),
            ("US", "United States", "California", "Los Angeles"),
            ("US", "United States", "California", "San Francisco"),
            ("US", "United States", "California", "San Diego"),
            ("US", "United States", "California", "San Francisco"),
            ("US", "United States", "California", "San Francisco"),
        ]

        points = [
            (34.0522, -118.2437),  # Los Angeles
            (37.7749, -122.4194),  # San Francisco
            (32.7157, -117.1611),  # San Diego
            (37.7749, -122.4194),  # San Francisco (duplicate to test counting)
        ]

        location_info = reverse_coords(points, decision_threshold=0.5)
        self.assertEqual(len(location_info), 1)
        location_info = location_info[0]
        self.assertEqual(location_info.country_code, "US")
        self.assertEqual(location_info.country, "United States")
        self.assertEqual(location_info.subdivision_name, "California")
        self.assertEqual(location_info.municipality, "San Francisco")

        location_info = reverse_coords(points, decision_threshold=0.75)
        self.assertEqual(len(location_info), 1)
        location_info = location_info[0]
        self.assertEqual(location_info.country, "United States")
        self.assertEqual(location_info.municipality, None)
        self.assertEqual(location_info.subdivision_name, "California")

    def test_update_location(self):
        mock_session = MagicMock(spec=Session)
        mock_dataset = MagicMock()
        mock_dataset.stable_id = "123"
        mock_dataset.feed = MagicMock()

        mock_session.query.return_value.filter.return_value.one_or_none.return_value = (
            mock_dataset
        )

        location_info = [
            GeocodedLocation(
                country_code="JP",
                country="日本",
                subdivision_name="東京都",
                municipality="渋谷区",
                stop_coords=(35.6895, 139.6917),
            )
        ]
        dataset_id = "123"

        update_location(location_info, dataset_id, mock_session)

        mock_session.add.assert_called_with(mock_dataset)
        mock_session.commit.assert_called_once()

        self.assertEqual(mock_dataset.locations[0].country, "日本")
        self.assertEqual(mock_dataset.feed.locations[0].country, "日本")
