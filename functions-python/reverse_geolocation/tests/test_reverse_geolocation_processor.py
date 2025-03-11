import json
import unittest
from unittest.mock import patch, MagicMock

import pandas as pd
import shapely
from faker import Faker
from geoalchemy2 import WKTElement

from location_group_utils import GeopolygonAggregate
from shared.database_gen.sqlacodegen_models import (
    Geopolygon,
    Location,
    Gtfsdataset,
    t_feedsearch,
)
from shared.database_gen.sqlacodegen_models import (
    Gtfsfeed,
    Feedlocationgrouppoint,
    Osmlocationgroup,
)
from test_shared.test_utils.database_utils import (
    default_db_url,
    get_testing_session,
    clean_testing_db,
)

faker = Faker()


class TestReverseGeolocationProcessor(unittest.TestCase):
    @patch("reverse_geolocation_processor.requests")
    def test_parse_request_parameters(self, requests_mock):
        from reverse_geolocation_processor import parse_request_parameters

        # No exception should be raised
        requests_mock.get.return_value.content = (
            b"stop_id,stop_name,stop_lat,stop_lon\n1,stop1,1.0,1.0\n2,stop2,2.0,"
            b"2.0\n"
        )
        request = MagicMock()
        request.get_json.return_value = {
            "stable_id": "test_stable_id",
            "dataset_id": "test_dataset_id",
            "stops_url": "test_url",
        }
        stops_df, stable_id, dataset_id = parse_request_parameters(request)
        self.assertEqual(stable_id, "test_stable_id")
        self.assertEqual(dataset_id, "test_dataset_id")
        self.assertEqual(stops_df.shape, (2, 4))

        # Exception should be raised
        requests_mock.get.return_value.content = None
        with self.assertRaises(ValueError):
            parse_request_parameters(request)
        request.get_json.return_value = {}
        with self.assertRaises(ValueError):
            parse_request_parameters(request)

    @patch.dict(
        "os.environ",
        {"FEEDS_DATABASE_URL": default_db_url},
    )
    def test_get_cached_geopolygons_empty_df(self):
        from reverse_geolocation_processor import get_cached_geopolygons

        with self.assertRaises(ValueError):
            get_cached_geopolygons("test-stable-id", pd.DataFrame())

    @patch.dict(
        "os.environ",
        {"FEEDS_DATABASE_URL": default_db_url},
    )
    def test_get_cached_geopolygons_no_feed(self):
        from reverse_geolocation_processor import get_cached_geopolygons

        stops_df = pd.DataFrame(
            {
                "stop_id": [1, 2],
                "stop_name": ["stop1", "stop2"],
                "stop_lat": [1.0, 2.0],
                "stop_lon": [1.0, 2.0],
            }
        )
        with self.assertRaises(ValueError):
            get_cached_geopolygons("test-stable-id", stops_df)

    @patch.dict(
        "os.environ",
        {"FEEDS_DATABASE_URL": default_db_url},
    )
    def test_get_cached_geopolygons_no_cached_stop(self):
        from reverse_geolocation_processor import get_cached_geopolygons

        stops_df = pd.DataFrame(
            {
                "stop_id": [1, 2],
                "stop_name": ["stop1", "stop2"],
                "stop_lat": [1.0, 2.0],
                "stop_lon": [1.0, 2.0],
            }
        )
        clean_testing_db()
        stable_id = faker.uuid4(cast_to=str)
        feed_id = faker.uuid4(cast_to=str)
        feed = Gtfsfeed(
            id=feed_id,
            stable_id=stable_id,
        )
        session = get_testing_session()
        session.add(feed)
        session.commit()
        result_feed_id, location_groups, results_df = get_cached_geopolygons(
            stable_id, stops_df
        )
        self.assertEqual(result_feed_id, feed_id)
        self.assertDictEqual(location_groups, {})
        self.assertEqual(results_df.shape, (2, 6))  # Added geometry columns

    @patch.dict(
        "os.environ",
        {"FEEDS_DATABASE_URL": default_db_url},
    )
    def test_get_cached_geopolygons_w_cached_stop(self):
        from reverse_geolocation_processor import get_cached_geopolygons

        stops_df = pd.DataFrame(
            {
                "stop_id": [1, 2],
                "stop_name": ["stop1", "stop2"],
                "stop_lat": [1, 2],
                "stop_lon": [1, 2],
            }
        )
        clean_testing_db()
        stable_id = faker.uuid4(cast_to=str)
        feed_id = faker.uuid4(cast_to=str)
        country_name = faker.country()
        country_code = faker.country_code()
        group = Osmlocationgroup(
            group_id=faker.uuid4(cast_to=str),
            group_name=f"{country_name}",
            osms=[
                Geopolygon(
                    osm_id=faker.random_int(),
                    admin_level=2,
                    geometry=WKTElement(
                        "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326
                    ),
                    iso_3166_1_code=country_code,
                )
            ],
        )
        stop_1 = Feedlocationgrouppoint(
            geometry=WKTElement("POINT (1.0 1.0)", srid=4326), group=group
        )
        stop_2 = Feedlocationgrouppoint(
            geometry=WKTElement("POINT (3.0 3.0)", srid=4326), group=group
        )
        feed = Gtfsfeed(
            id=feed_id, stable_id=stable_id, feedlocationgrouppoints=[stop_1, stop_2]
        )
        session = get_testing_session()
        session.add(feed)
        session.commit()
        result_feed_id, location_groups, results_df = get_cached_geopolygons(
            stable_id, stops_df
        )
        self.assertEqual(result_feed_id, feed_id)
        self.assertEqual(len(location_groups), 1)
        self.assertEqual(results_df.shape, (1, 6))  # Added geometry columns

    @patch.dict(
        "os.environ",
        {"FEEDS_DATABASE_URL": default_db_url},
    )
    def test_extract_location_group(self):
        from reverse_geolocation_processor import extract_location_aggregate

        clean_testing_db()
        geopolygon_country_lvl = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.country(),
            admin_level=2,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
            iso_3166_1_code=faker.country_code(),
        )
        geopolygon_subdivision_lvl = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.city(),
            admin_level=3,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
            iso_3166_2_code=faker.country_code(),
        )
        feed_id = faker.uuid4(cast_to=str)
        feed = Gtfsfeed(id=feed_id, stable_id=faker.uuid4(cast_to=str))
        session = get_testing_session()
        session.add(geopolygon_country_lvl)
        session.add(geopolygon_subdivision_lvl)
        session.add(feed)
        session.commit()
        stop_wkt = WKTElement("POINT (0.5 0.5)", srid=4326)
        aggregate = extract_location_aggregate(feed_id, stop_wkt, session)
        self.assertTrue(
            aggregate.iso_3166_1_code == geopolygon_country_lvl.iso_3166_1_code
        )
        self.assertTrue(
            aggregate.iso_3166_2_code == geopolygon_subdivision_lvl.iso_3166_2_code
        )

    @patch.dict(
        "os.environ",
        {"FEEDS_DATABASE_URL": default_db_url},
    )
    def test_extract_location_duplicate_admin_level(self):
        from reverse_geolocation_processor import extract_location_aggregate

        clean_testing_db()
        geopolygon_country_lvl = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.country(),
            admin_level=2,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
            iso_3166_1_code=faker.country_code(),
        )
        geopolygon_subdivision_lvl = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.city(),
            admin_level=2,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
            iso_3166_2_code=faker.country_code(),
        )
        feed_id = faker.uuid4(cast_to=str)
        feed = Gtfsfeed(id=feed_id, stable_id=faker.uuid4(cast_to=str))
        session = get_testing_session()
        session.add(geopolygon_country_lvl)
        session.add(geopolygon_subdivision_lvl)
        session.add(feed)
        session.commit()
        stop_wkt = WKTElement("POINT (0.5 0.5)", srid=4326)
        aggregate = extract_location_aggregate(feed_id, stop_wkt, session)
        self.assertIsNone(aggregate)

    @patch.dict(
        "os.environ",
        {"FEEDS_DATABASE_URL": default_db_url},
    )
    def test_extract_location_not_enough_geopolygons(self):
        from reverse_geolocation_processor import extract_location_aggregate

        clean_testing_db()
        geopolygon_country_lvl = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.country(),
            admin_level=2,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
            iso_3166_1_code=faker.country_code(),
        )
        feed_id = faker.uuid4(cast_to=str)
        feed = Gtfsfeed(id=feed_id, stable_id=faker.uuid4(cast_to=str))
        session = get_testing_session()
        session.add(geopolygon_country_lvl)
        session.add(feed)
        session.commit()
        stop_wkt = WKTElement("POINT (0.5 0.5)", srid=4326)
        aggregate = extract_location_aggregate(feed_id, stop_wkt, session)
        self.assertIsNone(aggregate)

    @patch.dict(
        "os.environ",
        {"FEEDS_DATABASE_URL": default_db_url},
    )
    def test_extract_location_missing_iso_codes(self):
        from reverse_geolocation_processor import extract_location_aggregate

        clean_testing_db()
        geopolygon_country_lvl = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.country(),
            admin_level=2,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
            iso_3166_1_code=faker.country_code(),
        )
        geopolygon_subdivision_lvl = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.city(),
            admin_level=3,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
        )
        feed_id = faker.uuid4(cast_to=str)
        feed = Gtfsfeed(id=feed_id, stable_id=faker.uuid4(cast_to=str))
        session = get_testing_session()
        session.add(geopolygon_country_lvl)
        session.add(geopolygon_subdivision_lvl)
        session.add(feed)
        session.commit()
        stop_wkt = WKTElement("POINT (0.5 0.5)", srid=4326)
        aggregate = extract_location_aggregate(feed_id, stop_wkt, session)
        self.assertIsNone(aggregate)

    @patch.dict(
        "os.environ",
        {"FEEDS_DATABASE_URL": default_db_url},
    )
    def test_create_feed_osm_location(self):
        from reverse_geolocation_processor import get_or_create_feed_osm_location_group

        clean_testing_db()
        feed_id = faker.uuid4(cast_to=str)
        feed = Gtfsfeed(id=feed_id, stable_id=faker.uuid4(cast_to=str))
        session = get_testing_session()
        session.add(feed)
        session.commit()
        stops_count = faker.random_int()
        aggregate = GeopolygonAggregate(
            Osmlocationgroup(
                group_id=faker.uuid4(cast_to=str),
                group_name=faker.country(),
                osms=[
                    Geopolygon(
                        osm_id=faker.random_int(),
                        admin_level=2,
                        geometry=WKTElement(
                            "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326
                        ),
                        iso_3166_1_code=faker.country_code(),
                    )
                ],
            ),
            stops_count=stops_count,
        )
        feed_osm_location = get_or_create_feed_osm_location_group(
            feed_id, aggregate, session
        )
        self.assertIsNotNone(feed_osm_location)
        self.assertEqual(feed_osm_location.stops_count, stops_count)

    @patch("reverse_geolocation_processor.storage.Client")
    @patch("os.getenv", return_value="test_bucket")
    def test_create_geojson_aggregate(self, _, mock_storage_client):
        from reverse_geolocation_processor import create_geojson_aggregate

        # Mock the storage client and blob
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        # Create sample geopolygons
        osm_id = faker.random_int()
        geopolygon_1 = Geopolygon(
            osm_id=osm_id,
            name=faker.country(),
            admin_level=2,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
            iso_3166_1_code=faker.country_code(),
        )

        group = Osmlocationgroup(
            group_id=str(osm_id), group_name=geopolygon_1.name, osms=[geopolygon_1]
        )

        aggregate = GeopolygonAggregate(group, stops_count=10)

        # Bounding box that fully contains the geopolygon
        bounding_box = shapely.geometry.box(-1, -1, 2, 2)

        # Call the function
        create_geojson_aggregate(
            location_groups=[aggregate],
            total_stops=20,
            stable_id="test_stable_id",
            bounding_box=bounding_box,
        )

        # Assertions on blob upload
        mock_blob.upload_from_string.assert_called_once()
        uploaded_data = mock_blob.upload_from_string.call_args[0][0]
        geojson_data = json.loads(uploaded_data)

        self.assertEqual(geojson_data["type"], "FeatureCollection")
        self.assertEqual(len(geojson_data["features"]), 1)
        feature = geojson_data["features"][0]
        self.assertEqual(feature["properties"]["osm_id"], str(geopolygon_1.osm_id))
        self.assertEqual(
            feature["properties"]["country_code"], geopolygon_1.iso_3166_1_code
        )
        self.assertEqual(feature["properties"]["subdivision_code"], "")
        self.assertEqual(feature["properties"]["stops_in_area"], 10)
        self.assertEqual(
            feature["properties"]["stops_in_area_coverage"], "50.00%"
        )  # 10/20 stops

        # Check if the blob was made public
        mock_blob.make_public.assert_called_once()

    @patch.dict("os.environ", {"FEEDS_DATABASE_URL": default_db_url})
    def test_create_new_location(self):
        from reverse_geolocation_processor import get_or_create_location

        # Clean DB before test
        clean_testing_db()

        # Mock session
        session = get_testing_session()

        # Create sample Geopolygon and GeopolygonAggregate
        geopolygon_country = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.city(),
            admin_level=3,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
            iso_3166_1_code=faker.country_code(),
        )
        geopolygon_subdivision = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.city(),
            admin_level=3,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
            iso_3166_2_code=faker.country_code(),
        )

        group = Osmlocationgroup(
            group_id=faker.uuid4(cast_to=str),
            group_name=f"{geopolygon_country.name}, {geopolygon_subdivision.name}",
            osms=[geopolygon_country, geopolygon_subdivision],
        )

        location_aggregate = GeopolygonAggregate(group, stops_count=5)

        # Call the function
        location = get_or_create_location(location_aggregate, session)

        # Assert location is created
        self.assertIsNotNone(location)
        self.assertEqual(location.id, location_aggregate.location_id())
        self.assertEqual(location.country_code, location_aggregate.iso_3166_1_code)
        self.assertEqual(location.country, location_aggregate.country())
        self.assertEqual(
            location.subdivision_name, location_aggregate.subdivision_name()
        )
        self.assertEqual(location.municipality, location_aggregate.municipality())

    @patch.dict("os.environ", {"FEEDS_DATABASE_URL": default_db_url})
    def test_retrieve_existing_location(self):
        from reverse_geolocation_processor import get_or_create_location

        # Clean DB before test
        clean_testing_db()

        # Mock session
        session = get_testing_session()

        # Create sample Location
        existing_location = Location(
            id=faker.uuid4(cast_to=str),
            country_code=faker.country_code(),
            country=faker.country(),
            subdivision_name=faker.state(),
            municipality=faker.city(),
        )

        session.add(existing_location)
        session.commit()

        # Create GeopolygonAggregate with same location_id
        geopolygon_country = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.city(),
            admin_level=3,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
            iso_3166_1_code=faker.country_code(),
        )
        geopolygon_subdivision = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.city(),
            admin_level=3,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
            iso_3166_2_code=faker.country_code(),
        )

        group = Osmlocationgroup(
            group_id=faker.uuid4(cast_to=str),
            group_name=f"{geopolygon_country.name}, {geopolygon_subdivision.name}",
            osms=[geopolygon_country, geopolygon_subdivision],
        )

        location_aggregate = GeopolygonAggregate(group, stops_count=5)
        location_aggregate.location_id = (
            lambda: existing_location.id
        )  # Mocking location_id method

        # Call the function
        location = get_or_create_location(location_aggregate, session)

        # Assert the existing location was returned
        self.assertIsNotNone(location)
        self.assertEqual(location.id, existing_location.id)
        self.assertEqual(location.country, existing_location.country)

    def test_retrieve_location_exception(self):
        from reverse_geolocation_processor import get_or_create_location

        mock_session = MagicMock()
        mock_session.query.side_effect = Exception("Test exception")
        location = get_or_create_location(None, mock_session)
        self.assertIsNone(location)

    @patch.dict("os.environ", {"FEEDS_DATABASE_URL": default_db_url})
    def test_update_dataset_bounding_box_success(self):
        from reverse_geolocation_processor import update_dataset_bounding_box

        # Clean DB before test
        clean_testing_db()
        session = get_testing_session()

        # Create sample dataset
        feed_id = faker.uuid4(cast_to=str)
        feed = Gtfsfeed(
            id=feed_id,
            stable_id=faker.uuid4(cast_to=str),
        )
        dataset_id = faker.uuid4(cast_to=str)
        dataset = Gtfsdataset(
            id=dataset_id,
            stable_id=dataset_id,
            bounding_box=None,
            feed=feed,
        )
        session.add(dataset)
        session.commit()

        # Prepare stops DataFrame
        stops_df = pd.DataFrame(
            {
                "stop_id": [1, 2, 3, 4],
                "stop_lat": [10.0, 20.0, 20.0, 10.0],
                "stop_lon": [30.0, 30.0, 40.0, 40.0],
            }
        )

        # Call the function
        bounding_box = update_dataset_bounding_box(
            dataset_id, stops_df, db_session=session
        )

        # Expected bounding box: POLYGON((30 10, 40 10, 40 20, 30 20, 30 10))
        expected_polygon = shapely.geometry.Polygon(
            [(30, 10), (40, 10), (40, 20), (30, 20), (30, 10)]
        )

        # Assert the bounding box is correct
        self.assertTrue(bounding_box.equals(expected_polygon))

        # Fetch the updated dataset from DB and verify bounding box
        updated_dataset = (
            session.query(Gtfsdataset).filter(Gtfsdataset.stable_id == dataset_id).one()
        )
        self.assertIsNotNone(updated_dataset.bounding_box)
        self.assertIn("POLYGON", str(updated_dataset.bounding_box))

    @patch.dict("os.environ", {"FEEDS_DATABASE_URL": default_db_url})
    def test_update_dataset_bounding_box_exception(self):
        from reverse_geolocation_processor import update_dataset_bounding_box

        clean_testing_db()
        stops_df = pd.DataFrame(
            {
                "stop_id": [1, 2, 3, 4],
                "stop_lat": [10.0, 20.0, 20.0, 10.0],
                "stop_lon": [30.0, 30.0, 40.0, 40.0],
            }
        )
        session = get_testing_session()

        with self.assertRaises(Exception):
            update_dataset_bounding_box(
                faker.uuid4(cast_to=str), stops_df, db_session=session
            )

    @patch.dict("os.environ", {"FEEDS_DATABASE_URL": default_db_url})
    @patch("reverse_geolocation_processor.refresh_materialized_view")
    @patch("reverse_geolocation_processor.extract_location_aggregate")
    def test_extract_location_aggregates(
        self, mock_extract_location_aggregate, mock_refresh_materialized_view
    ):
        from reverse_geolocation_processor import extract_location_aggregates

        clean_testing_db()
        session = get_testing_session()

        # Create sample feed
        feed_id = faker.uuid4(cast_to=str)
        feed = Gtfsfeed(id=feed_id, stable_id=faker.uuid4(cast_to=str))
        session.add(feed)
        session.commit()

        # Prepare stops DataFrame
        stops_df = pd.DataFrame(
            {
                "stop_id": [1, 2, 3],
                "stop_lat": [2.0, 3.0, 10.0],  # Two inside polygon, one unmatched
                "stop_lon": [2.0, 3.0, 10.0],
            }
        )

        stops_df["geometry"] = stops_df.apply(
            lambda x: WKTElement(f"POINT ({x['stop_lon']} {x['stop_lat']})", srid=4326),
            axis=1,
        )

        # Prepare mock GeopolygonAggregate for matched stops
        geopolygon = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.city(),
            admin_level=3,
            geometry=WKTElement("POLYGON((0 0, 5 0, 5 5, 0 5, 0 0))", srid=4326),
            iso_3166_1_code=faker.country_code(),
        )

        group = Osmlocationgroup(
            group_id=faker.uuid4(cast_to=str),
            group_name=geopolygon.name,
            osms=[geopolygon],
        )

        mock_aggregate = GeopolygonAggregate(group, stops_count=1)
        session.add(group)
        session.commit()

        # Mock extract_location_aggregate behavior
        def side_effect(_, stop_geometry, __):
            if stop_geometry.data == "POINT (10.0 10.0)":  # Simulate unmatched stop
                return None
            return mock_aggregate

        mock_extract_location_aggregate.side_effect = side_effect

        # Prepare location_aggregates dict (empty initially)
        location_aggregates = {}

        # Call the function
        extract_location_aggregates(
            feed_id, stops_df, location_aggregates, db_session=session
        )

        # Assertions

        # Ensure only matched stops are aggregated
        self.assertEqual(len(location_aggregates), 1)
        first_aggregate = list(location_aggregates.values())[0]
        self.assertIsInstance(first_aggregate, GeopolygonAggregate)
        self.assertEqual(first_aggregate.stop_count, 2)  # Two matched stops

        # Verify materialized view was refreshed
        mock_refresh_materialized_view.assert_called_once_with(
            session, t_feedsearch.name
        )
