import unittest
from unittest.mock import patch, MagicMock

import numpy as np
import pandas
from faker import Faker
from geoalchemy2 import WKTElement

from extract_location.src.bounding_box.bounding_box_extractor import (
    create_polygon_wkt_element,
    update_dataset_bounding_box,
)
from extract_location.src.reverse_geolocation.location_extractor import (
    get_unique_countries,
)
from extract_location.src.stops_utils import get_gtfs_feed_bounds_and_points

faker = Faker()


class TestLocationUtils(unittest.TestCase):
    def test_unique_country_codes(self):
        country_codes = ["US", "CA", "US", "MX", "CA", "FR"]
        countries = [
            "United States",
            "Canada",
            "United States",
            "Mexico",
            "Canada",
            "France",
        ]
        points = [
            (34.0522, -118.2437),
            (45.4215, -75.6972),
            (40.7128, -74.0060),
            (19.4326, -99.1332),
            (49.2827, -123.1207),
            (48.8566, 2.3522),
        ]

        expected_unique_country_codes = ["US", "CA", "MX", "FR"]
        expected_unique_countries = ["United States", "Canada", "Mexico", "France"]
        expected_unique_point_mapping = [
            (34.0522, -118.2437),
            (45.4215, -75.6972),
            (19.4326, -99.1332),
            (48.8566, 2.3522),
        ]

        (
            unique_countries,
            unique_country_codes,
            unique_point_mapping,
        ) = get_unique_countries(countries, country_codes, points)

        self.assertEqual(unique_country_codes, expected_unique_country_codes)
        self.assertEqual(unique_countries, expected_unique_countries)
        self.assertEqual(unique_point_mapping, expected_unique_point_mapping)

    def test_create_polygon_wkt_element(self):
        bounds = np.array(
            [faker.longitude(), faker.latitude(), faker.longitude(), faker.latitude()]
        )
        wkt_polygon: WKTElement = create_polygon_wkt_element(bounds)
        self.assertIsNotNone(wkt_polygon)

    def test_update_dataset_bounding_box(self):
        session = MagicMock()
        session.query.return_value.filter.return_value.one_or_none = MagicMock()
        update_dataset_bounding_box(session, faker.pystr(), MagicMock())
        session.commit.assert_called_once()

    def test_update_dataset_bounding_box_exception(self):
        session = MagicMock()
        session.query.return_value.filter.return_value.one_or_none = None
        try:
            update_dataset_bounding_box(session, faker.pystr(), MagicMock())
            assert False
        except Exception:
            assert True

    @patch("gtfs_kit.read_feed")
    def test_get_gtfs_feed_bounds_exception(self, mock_gtfs_kit):
        mock_gtfs_kit.side_effect = Exception(faker.pystr())
        try:
            get_gtfs_feed_bounds_and_points(faker.url(), faker.pystr())
            assert False
        except Exception:
            assert True

    @patch("gtfs_kit.read_feed")
    def test_get_gtfs_feed_bounds_and_points(self, mock_gtfs_kit):
        expected_bounds = np.array(
            [faker.longitude(), faker.latitude(), faker.longitude(), faker.latitude()]
        )

        feed_mock = MagicMock()
        feed_mock.stops = pandas.DataFrame(
            {
                "stop_lat": [faker.latitude() for _ in range(10)],
                "stop_lon": [faker.longitude() for _ in range(10)],
            }
        )
        feed_mock.compute_bounds.return_value = expected_bounds
        mock_gtfs_kit.return_value = feed_mock
        bounds, points = get_gtfs_feed_bounds_and_points(
            faker.url(), "test_dataset_id", num_points=7
        )
        self.assertEqual(len(points), 7)
        for point in points:
            self.assertIsInstance(point, tuple)
            self.assertEqual(len(point), 2)
