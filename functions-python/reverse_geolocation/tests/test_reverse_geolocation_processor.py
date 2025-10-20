import json
import logging
import unittest
import uuid
from unittest.mock import patch, MagicMock

import pandas as pd
import shapely
from faker import Faker
from flask import Request
from geoalchemy2 import WKTElement
from sqlalchemy.orm import Session

from location_group_utils import GeopolygonAggregate, ERROR_STATUS_CODE
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Geopolygon,
    Gtfsdataset,
    Gtfsrealtimefeed,
    Feed,
)
from shared.database_gen.sqlacodegen_models import (
    Gtfsfeed,
    Feedlocationgrouppoint,
    Osmlocationgroup,
)
from shared.helpers.locations import ReverseGeocodingStrategy
from test_shared.test_utils.database_utils import (
    default_db_url,
)

faker = Faker()
logger = logging.getLogger(__name__)


class TestReverseGeolocationProcessor(unittest.TestCase):
    @patch("parse_request.requests")
    def test_parse_request_parameters(self, requests_mock):
        from parse_request import parse_request_parameters

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
            "public": "True",
            "strategy": "per-point",
        }
        (
            stops_df,
            stable_id,
            dataset_id,
            data_type,
            urls,
            public,
            strategy,
            use_cache,
            maximum_executions,
        ) = parse_request_parameters(request)
        self.assertEqual("test_stable_id", stable_id)
        self.assertEqual("test_dataset_id", dataset_id)
        self.assertEqual((2, 4), stops_df.shape)
        self.assertEqual("gtfs", data_type)
        self.assertEqual(["test_url"], urls)
        self.assertEqual(True, public)
        self.assertEqual("per-point", strategy)
        self.assertEqual(True, use_cache)
        self.assertEqual(1, maximum_executions)

        # Exception should be raised
        requests_mock.get.return_value.content = None
        with self.assertRaises(ValueError):
            parse_request_parameters(request)
        request.get_json.return_value = {}
        with self.assertRaises(ValueError):
            parse_request_parameters(request)

    @patch("parse_request.requests")
    def test_parse_request_parameters_gbfs_station_information(self, requests_mock):
        from parse_request import parse_request_parameters

        # Mocked station information response
        requests_mock.get.return_value.json.return_value = {
            "data": {
                "stations": [
                    {"station_id": "s1", "lat": 1.0, "lon": 2.0},
                    {"station_id": "s2", "lat": 3.0, "lon": 4.0},
                ]
            }
        }

        request = MagicMock()
        request.get_json.return_value = {
            "stable_id": "stable123",
            "station_information_url": "http://dummy.url",
            "data_type": "gbfs",
        }

        (
            df,
            stable_id,
            dataset_id,
            data_type,
            urls,
            public,
            strategy,
            use_cache,
            maximum_executions,
        ) = parse_request_parameters(request)

        self.assertEqual("stable123", stable_id)
        self.assertEqual(None, dataset_id)
        self.assertEqual("gbfs", data_type)
        self.assertEqual("http://dummy.url", urls[0])
        self.assertEqual((2, 2), df.shape)
        self.assertEqual("per-polygon", strategy)
        self.assertEqual(True, public)
        # Cache is disabled for GBFS data by default
        self.assertEqual(False, use_cache)
        self.assertEqual(1, maximum_executions)

    @patch("parse_request.requests")
    def test_parse_request_parameters_gbfs_vehicle_status(self, requests_mock):
        from parse_request import parse_request_parameters

        # Mocked vehicle status response
        requests_mock.get.return_value.json.return_value = {
            "data": {
                "vehicles": [
                    {"vehicle_id": "v1", "lat": 10.0, "lon": 20.0},
                    {"vehicle_id": "v2", "lat": 30.0, "lon": 40.0},
                ]
            }
        }

        request = MagicMock()
        request.get_json.return_value = {
            "stable_id": "stable456",
            "vehicle_status_url": "http://dummy.vehicle",
            "data_type": "gbfs",
            "public": "False",
            "maximum_executions": 10,
        }

        (
            df,
            stable_id,
            dataset_id,
            data_type,
            urls,
            public,
            strategy,
            use_cache,
            maximum_executions,
        ) = parse_request_parameters(request)

        self.assertEqual("stable456", stable_id)
        self.assertEqual(None, dataset_id)
        self.assertEqual("gbfs", data_type)
        self.assertEqual("http://dummy.vehicle", urls[0])
        self.assertEqual((2, 2), df.shape)
        self.assertEqual("per-polygon", strategy)
        self.assertEqual(False, public)
        # Cache is disabled for GBFS data by default
        self.assertEqual(False, use_cache)
        self.assertEqual(10, maximum_executions)

    @patch("parse_request.requests")
    def test_parse_request_parameters_invalid_request(self, requests_mock):
        from parse_request import parse_request_parameters

        # Case 1: content returns None
        requests_mock.get.return_value.content = None
        request = MagicMock()
        request.get_json.return_value = {
            "stable_id": "bad",
            "dataset_id": "bad",
            "stops_url": "bad",
        }
        with self.assertRaises(ValueError):
            parse_request_parameters(request)

        # Case 2: missing JSON keys
        request.get_json.return_value = {}
        with self.assertRaises(ValueError):
            parse_request_parameters(request)

    @with_db_session(db_url=default_db_url)
    def test_get_cached_geopolygons_empty_df(self, db_session):
        from reverse_geolocation_processor import get_geopolygons_with_geometry

        with self.assertRaises(ValueError):
            get_geopolygons_with_geometry(
                "test-stable-id", pd.DataFrame(), False, logger
            )

    @with_db_session(db_url=default_db_url)
    def test_get_cached_geopolygons_no_cached_stop(self, db_session):
        from reverse_geolocation_processor import get_geopolygons_with_geometry

        stops_df = pd.DataFrame(
            {
                "stop_id": [1, 2],
                "stop_name": ["stop1", "stop2"],
                "stop_lat": [1.0, 2.0],
                "stop_lon": [1.0, 2.0],
            }
        )
        stable_id = faker.uuid4(cast_to=str)
        feed_id = faker.uuid4(cast_to=str)
        feed = Gtfsfeed(
            id=feed_id,
            stable_id=stable_id,
        )
        db_session.add(feed)
        db_session.commit()
        location_groups, results_df = get_geopolygons_with_geometry(
            feed, stops_df, False, logger
        )
        self.assertDictEqual(location_groups, {})
        self.assertEqual(results_df.shape, (2, 6))  # Added geometry columns

    @with_db_session(db_url=default_db_url)
    def test_get_cached_geopolygons_w_cached_stop(self, db_session):
        from reverse_geolocation_processor import get_geopolygons_with_geometry

        stops_df = pd.DataFrame(
            {
                "stop_id": [1, 2],
                "stop_name": ["stop1", "stop2"],
                "stop_lat": [1, 2],
                "stop_lon": [1, 2],
            }
        )
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
        db_session.add(feed)
        db_session.commit()
        location_groups, results_df = get_geopolygons_with_geometry(
            feed, stops_df, True, logger
        )
        self.assertEqual(len(location_groups), 1)
        self.assertEqual(results_df.shape, (1, 6))  # Added geometry columns

    @with_db_session(db_url=default_db_url)
    @patch("reverse_geolocation_processor.get_storage_client")
    @patch("os.getenv")
    def test_create_geojson_aggregate(
        self, mock_getenv, mock_storage_client, db_session
    ):
        from reverse_geolocation_processor import create_geojson_aggregate

        # Mock the specific environment variable
        mock_getenv.side_effect = (
            lambda var_name: "test_bucket"
            if var_name in ["DATASETS_BUCKET_NAME_GTFS", "DATASETS_BUCKET_NAME_GBFS"]
            else None
        )

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

        feed = Feed(
            id=faker.uuid4(cast_to=str),
            stable_id="test_stable_id",
            data_type="gtfs",
            gtfsdatasets=[
                Gtfsdataset(
                    id=faker.uuid4(cast_to=str),
                    stable_id=faker.uuid4(cast_to=str),
                    feed=Gtfsfeed(
                        id=faker.uuid4(cast_to=str),
                        stable_id="test_stable_id",
                    ),
                )
            ],
        )
        # Call the function
        create_geojson_aggregate(
            location_groups=[aggregate],
            total_stops=20,
            bounding_box=bounding_box,
            data_type="gtfs",
            feed=feed,
            gtfs_dataset=feed.gtfsdatasets[0],
            extraction_urls=["test_extraction_url"],
            logger=logger,
            db_session=db_session,
        )

        # Assertions on blob upload
        mock_blob.upload_from_string.assert_called_once()
        uploaded_data = mock_blob.upload_from_string.call_args[0][0]
        geojson_data = json.loads(uploaded_data)

        self.assertEqual(geojson_data["type"], "FeatureCollection")
        self.assertEqual(len(geojson_data["features"]), 1)
        feature = geojson_data["features"][0]
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

    @with_db_session(db_url=default_db_url)
    def test_update_dataset_bounding_box_success(self, db_session):
        from reverse_geolocation_processor import update_dataset_bounding_box

        # Create sample dataset
        feed_id = faker.uuid4(cast_to=str)
        feed = Gtfsfeed(
            id=feed_id,
            data_type="gtfs",
            stable_id=faker.uuid4(cast_to=str),
        )
        dataset_id = faker.uuid4(cast_to=str)
        dataset = Gtfsdataset(
            id=dataset_id,
            stable_id=dataset_id,
            bounding_box=None,
            feed=feed,
        )
        db_session.add(dataset)
        db_session.commit()

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
            feed, dataset, stops_df, db_session=db_session
        )

        # Expected bounding box: POLYGON((30 10, 40 10, 40 20, 30 20, 30 10))
        expected_polygon = shapely.geometry.Polygon(
            [(30, 10), (40, 10), (40, 20), (30, 20), (30, 10)]
        )

        # Assert the bounding box is correct
        self.assertTrue(bounding_box.equals(expected_polygon))

        # Fetch the updated dataset from DB and verify bounding box
        updated_dataset = (
            db_session.query(Gtfsdataset)
            .filter(Gtfsdataset.stable_id == dataset_id)
            .one()
        )
        self.assertIsNotNone(updated_dataset.bounding_box)
        self.assertIn("POLYGON", str(updated_dataset.bounding_box))

    @with_db_session(db_url=default_db_url)
    def test_update_dataset_bounding_box_exception(self, db_session):
        from reverse_geolocation_processor import update_dataset_bounding_box

        stops_df = pd.DataFrame(
            {
                "stop_id": [1, 2, 3, 4],
                "stop_lat": [10.0, 20.0, 20.0, 10.0],
                "stop_lon": [30.0, 30.0, 40.0, 40.0],
            }
        )

        with self.assertRaises(Exception):
            update_dataset_bounding_box(
                MagicMock(), faker.uuid4(cast_to=str), stops_df, db_session=db_session
            )

    @patch("reverse_geolocation_processor.parse_request_parameters")
    @patch("reverse_geolocation_processor.update_dataset_bounding_box")
    @patch("reverse_geolocation_processor.reverse_geolocation")
    @patch("reverse_geolocation_processor.create_geojson_aggregate")
    @patch("reverse_geolocation_processor.check_maximum_executions")
    @patch("reverse_geolocation_processor.get_execution_id")
    @patch("reverse_geolocation_processor.load_dataset")
    @patch("reverse_geolocation_processor.load_feed")
    @patch("reverse_geolocation_processor.record_execution_trace")
    def test_valid_request(
        self,
        _,
        mock_load_feed,
        mock_load_dataset,
        mock_get_execution_id,
        mock_check_maximum_executions,
        mock_create_geojson_aggregate,
        mock_reverse_geolocation,
        mock_update_bounding_box,
        mock_parse_request_parameters,
    ):
        from reverse_geolocation_processor import reverse_geolocation_process

        mock_get_execution_id.return_value = "test_execution_id"
        mock_check_maximum_executions.return_value = None
        # Mocking the parsed request parameters
        mock_parse_request_parameters.return_value = (
            pd.DataFrame({"stop_lat": [1.0], "stop_lon": [1.0]}),
            "test_stable_id",
            "test_dataset_id",
            "gtfs",
            ["test_url"],
            True,
            "per-point",
            False,
            1,
        )
        mock_update_bounding_box.return_value = MagicMock()
        mock_reverse_geolocation.return_value = {"group_id": MagicMock()}
        mock_create_geojson_aggregate.return_value = MagicMock()
        mock_load_feed.return_value = MagicMock()
        mock_load_dataset.return_value = MagicMock()
        # Mocking a Flask request
        request = MagicMock(spec=Request)
        # Call the function
        response, status_code = reverse_geolocation_process(request)

        # Assertions
        self.assertEqual(200, status_code)
        self.assertIn("Processed 1 stops", response)
        mock_parse_request_parameters.assert_called_once()
        mock_update_bounding_box.assert_called_once()
        mock_reverse_geolocation.assert_called_once()
        mock_create_geojson_aggregate.assert_called_once()

    @patch("reverse_geolocation_processor.parse_request_parameters")
    def test_invalid_request(self, mock_parse_request_parameters):
        from reverse_geolocation_processor import reverse_geolocation_process

        # Mocking parse_request_parameters to raise a ValueError
        mock_parse_request_parameters.side_effect = ValueError("Invalid request")

        # Mocking a Flask request
        request = MagicMock(spec=Request)

        # Call the function
        response, status_code = reverse_geolocation_process(request)

        # Assertions
        self.assertEqual(status_code, ERROR_STATUS_CODE)
        self.assertEqual(response, "Invalid request")
        mock_parse_request_parameters.assert_called_once()

    @patch("reverse_geolocation_processor.parse_request_parameters")
    @patch("reverse_geolocation_processor.update_dataset_bounding_box")
    @patch("reverse_geolocation_processor.reverse_geolocation")
    @patch("reverse_geolocation_processor.check_maximum_executions")
    @patch("reverse_geolocation_processor.get_execution_id")
    @patch("reverse_geolocation_processor.load_dataset")
    @patch("reverse_geolocation_processor.load_feed")
    @patch("reverse_geolocation_processor.record_execution_trace")
    def test_exception_handling(
        self,
        _,
        mock_load_feed,
        mock_load_dataset,
        mock_check_get_execution_id,
        mock_check_maximum_executions,
        mock_reverse_geolocation,
        mock_update_bounding_box,
        mock_parse_request_parameters,
    ):
        from reverse_geolocation_processor import reverse_geolocation_process

        mock_check_get_execution_id.return_value = "test_execution_id"
        mock_check_maximum_executions.return_value = None
        # mock_dataset_service.get_by_execution_and_stable_ids.return_value = 0
        # Mocking the parsed request parameters
        mock_parse_request_parameters.return_value = (
            pd.DataFrame({"stop_lat": [1.0], "stop_lon": [1.0]}),
            "test_stable_id",
            "test_dataset_id",
            "gtfs",
            ["test_url"],
            True,
            "per-point",
            False,
            1,
        )
        mock_load_dataset.return_value = MagicMock()
        mock_load_feed.return_value = MagicMock()
        mock_update_bounding_box.side_effect = Exception("Unexpected error")

        # Mocking a Flask request
        request = MagicMock(spec=Request)

        # Call the function
        response, status_code = reverse_geolocation_process(request)

        # Assertions
        self.assertEqual(status_code, ERROR_STATUS_CODE)
        self.assertIn("Unexpected error", response)
        mock_parse_request_parameters.assert_called_once()
        mock_update_bounding_box.assert_called_once()
        mock_reverse_geolocation.assert_not_called()

    @patch("reverse_geolocation_processor.parse_request_parameters")
    @patch("reverse_geolocation_processor.check_maximum_executions")
    @patch("reverse_geolocation_processor.get_execution_id")
    @patch("reverse_geolocation_processor.record_execution_trace")
    def test_valid_request_empty_stops(
        self,
        _,
        mock_get_execution_id,
        mock_check_maximum_executions,
        mock_parse_request_parameters,
    ):
        from reverse_geolocation_processor import reverse_geolocation_process

        mock_get_execution_id.return_value = "test_execution_id"
        mock_check_maximum_executions.return_value = None
        # Mocking the parsed request parameters
        mock_parse_request_parameters.return_value = (
            pd.DataFrame({"stop_lat": [], "stop_lon": []}),
            "test_stable_id",
            "test_dataset_id",
            "gtfs",
            ["test_url"],
            True,
            "per-point",
            False,
            1,
        )

        # Mocking a Flask request
        request = MagicMock(spec=Request)

        # Call the function
        response, status_code = reverse_geolocation_process(request)

        # Assertions
        self.assertEqual(status_code, ERROR_STATUS_CODE)
        self.assertIn("No stops found in the feed", response)
        mock_parse_request_parameters.assert_called_once()

    @patch("reverse_geolocation_processor.get_geopolygons_with_geometry")
    @patch("reverse_geolocation_processor.extract_location_aggregates_per_point")
    @patch("reverse_geolocation_processor.update_feed_location")
    @patch("reverse_geolocation_processor.load_feed")
    def test_valid_per_point_strategy(
        self,
        mock_load_feed,
        mock_update_feed_location,
        mock_extract_per_point,
        mock_get_geopolygons,
    ):
        from reverse_geolocation_processor import reverse_geolocation

        # Mock feed and database session
        mock_feed_instance = MagicMock()
        mock_load_feed.return_value = mock_feed_instance

        # Mock geopolygons
        mock_get_geopolygons.return_value = (
            {},
            pd.DataFrame({"stop_lat": [1.0], "stop_lon": [1.0]}),
        )

        # Call the function
        result = reverse_geolocation(
            strategy=ReverseGeocodingStrategy.PER_POINT,
            stable_id="test_stable_id",
            stops_df=pd.DataFrame({"stop_lat": [1.0], "stop_lon": [1.0]}),
            logger=MagicMock(),
            data_type="gtfs",
            use_cache=True,
            db_session=MagicMock(spec=Session),
        )

        # Assertions
        self.assertEqual(result, {})
        mock_get_geopolygons.assert_called_once()
        mock_extract_per_point.assert_called_once()
        mock_update_feed_location.assert_called_once()

    @patch("reverse_geolocation_processor.get_geopolygons_with_geometry")
    @patch("reverse_geolocation_processor.update_feed_location")
    @patch("reverse_geolocation_processor.load_feed")
    @patch("reverse_geolocation_processor.extract_location_aggregates_per_polygon")
    def test_valid_per_polygon_strategy(
        self,
        mock_extract_per_polygon,
        mock_load_feed,
        mock_update_feed_location,
        mock_get_geopolygons,
    ):
        from reverse_geolocation_processor import reverse_geolocation

        # Mock feed and database session
        mock_feed_instance = MagicMock()
        mock_load_feed.query.return_value = mock_feed_instance

        # Mock geopolygons
        mock_get_geopolygons.return_value = (
            {},
            pd.DataFrame({"stop_lat": [1.0], "stop_lon": [1.0]}),
        )
        mock_extract_per_polygon.return_value = ()
        # Call the function
        result = reverse_geolocation(
            strategy=ReverseGeocodingStrategy.PER_POLYGON,
            stable_id="test_stable_id",
            stops_df=pd.DataFrame({"stop_lat": [1.0], "stop_lon": [1.0]}),
            data_type="gtfs",
            logger=MagicMock(),
            use_cache=True,
            db_session=MagicMock(spec=Session),
        )

        # Assertions
        self.assertEqual(result, {})
        mock_get_geopolygons.assert_called_once()
        mock_update_feed_location.assert_called_once()
        mock_extract_per_polygon.assert_called_once()

    @with_db_session(db_url=default_db_url)
    def test_invalid_strategy(
        self,
        db_session: Session,
    ):
        from reverse_geolocation_processor import reverse_geolocation

        id = str(uuid.uuid4())
        feed = Gtfsfeed(
            id=id,
            stable_id=f"test_feed{id}",
            status="active",
            gtfsdatasets=[],
            locations=[],
        )
        db_session.add(feed)
        db_session.commit()

        # Call the function
        result = reverse_geolocation(
            strategy="invalid_strategy",
            stable_id=f"test_feed{id}",
            stops_df=pd.DataFrame({"stop_lat": [1.0], "stop_lon": [1.0]}),
            logger=MagicMock(),
            data_type=feed.data_type,
            use_cache=True,
            db_session=db_session,
        )
        db_session.commit()
        # Assertions
        self.assertEqual(
            ("Invalid strategy: invalid_strategy", ERROR_STATUS_CODE), result
        )

    @with_db_session(db_url=default_db_url)
    def test_load_feed_missing_feed(self, db_session):
        from reverse_geolocation_processor import reverse_geolocation

        # Call the function and expect a ValueError
        with self.assertRaises(ValueError) as context:
            reverse_geolocation(
                strategy=ReverseGeocodingStrategy.PER_POINT,
                stable_id="missing_stable_id",
                stops_df=pd.DataFrame({"stop_lat": [1.0], "stop_lon": [1.0]}),
                data_type="gtfs",
                logger=MagicMock(),
                use_cache=True,
                db_session=db_session,
            )

        self.assertIn("No feed found for stable ID", str(context.exception))

    @with_db_session(db_url=default_db_url)
    def test_update_feed_location_success(self, db_session):
        from reverse_geolocation_processor import update_feed_location

        id = str(uuid.uuid4())
        feed = Gtfsfeed(
            id=id,
            data_type="gtfs",
            stable_id=f"test_feed{id}",
            status="active",
            gtfsdatasets=[],
            locations=[],
            gtfs_rt_feeds=[
                Gtfsrealtimefeed(
                    id=f"test_rt_feed{id}",
                )
            ],
        )
        group = Osmlocationgroup(
            group_id=f"group_1{id}",
            group_name="group_name",
            osms=[
                Geopolygon(
                    osm_id=faker.random_int(),
                    admin_level=2,
                    geometry=WKTElement(
                        "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326
                    ),
                    iso_3166_1_code="CA",
                    name="Canada",
                ),
                Geopolygon(
                    osm_id=faker.random_int(),
                    admin_level=4,
                    geometry=WKTElement(
                        "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326
                    ),
                    iso_3166_2_code="CA-QC",
                    name="Quebec",
                ),
            ],
        )
        db_session.add(feed)
        db_session.add(group)
        db_session.commit()

        location_group = GeopolygonAggregate(group, stops_count=1)
        cache_location_groups = {f"group_1{id}": location_group}

        # Call the function
        update_feed_location(
            cache_location_groups=cache_location_groups,
            feed=feed,
            logger=logger,
            db_session=db_session,
        )

        self.assertEqual(1, len(feed.locations))
        self.assertEqual("CA", feed.locations[0].country_code)
        self.assertEqual(1, len(feed.gtfs_rt_feeds[0].locations))
        self.assertEqual("CA", feed.gtfs_rt_feeds[0].locations[0].country_code)
