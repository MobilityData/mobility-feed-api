import base64
import json
import os
import unittest
from unittest import mock
from unittest.mock import patch, MagicMock

import numpy as np
import pandas
from cloudevents.http import CloudEvent
from faker import Faker
from geoalchemy2 import WKTElement
from sqlalchemy.orm import Session

from database_gen.sqlacodegen_models import Gtfsdataset
from extract_location.src.bounding_box_extractor import (
    create_polygon_wkt_element,
    update_dataset_bounding_box,
)
from extract_location.src.location_extractor import (
    reverse_coord,
    reverse_coords,
    LocationInfo,
    update_location,
)
from extract_location.src.main import (
    extract_location,
    extract_location_pubsub,
    extract_location_batch,
)
from extract_location.src.stops_utils import get_gtfs_feed_bounds_and_points
from test_utils.database_utils import default_db_url

faker = Faker()


class TestExtractBoundingBox(unittest.TestCase):
    def test_reverse_coord(self):
        lat, lon = 34.0522, -118.2437  # Coordinates for Los Angeles, California, USA
        result = reverse_coord(lat, lon)

        self.assertEqual(result, ("US", "United States", "California", "Los Angeles"))

    @patch("requests.get")
    def test_reverse_coords(self, mock_get):
        # Mocking the response from the API for multiple calls
        mock_response = MagicMock()
        mock_response.json.side_effect = [
            {
                "address": {
                    "country_code": "us",
                    "country": "United States",
                    "state": "California",
                    "city": "Los Angeles",
                }
            },
            {
                "address": {
                    "country_code": "us",
                    "country": "United States",
                    "state": "California",
                    "city": "San Francisco",
                }
            },
            {
                "address": {
                    "country_code": "us",
                    "country": "United States",
                    "state": "California",
                    "city": "Los Angeles",
                }
            },
        ]
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        points = [(34.0522, -118.2437), (37.7749, -122.4194)]
        location_info = reverse_coords(points)

        self.assertEqual(location_info.country_codes, ["US", "US"])
        self.assertEqual(location_info.countries, ["United States", "United States"])
        self.assertEqual(location_info.most_common_subdivision_name, "California")
        self.assertEqual(location_info.most_common_municipality, "Los Angeles")

    def test_update_location(self):
        # Setup mock database session and models
        mock_session = MagicMock(spec=Session)
        mock_dataset = MagicMock()
        mock_dataset.stable_id = "123"
        mock_dataset.feed = MagicMock()

        mock_session.query.return_value.filter.return_value.one_or_none.return_value = (
            mock_dataset
        )

        location_info = LocationInfo(
            country_codes=["us"],
            countries=["United States"],
            most_common_subdivision_name="California",
            most_common_municipality="Los Angeles",
        )
        dataset_id = "123"

        update_location(location_info, dataset_id, mock_session)

        # Verify if dataset and feed locations are set correctly
        mock_session.add.assert_called_once_with(mock_dataset)
        mock_session.commit.assert_called_once()

        self.assertEqual(mock_dataset.locations[0].country, "United States")
        self.assertEqual(mock_dataset.feed.locations[0].country, "United States")

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

        # Create a mock feed with a compute_bounds method
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

    @patch("extract_location.src.main.Logger")
    @patch("extract_location.src.main.DatasetTraceService")
    def test_extract_location_exception(self, _, __):
        # Data with missing url
        data = {"stable_id": faker.pystr(), "dataset_id": faker.pystr()}
        message_data = base64.b64encode(json.dumps(data).encode("utf-8")).decode(
            "utf-8"
        )

        # Creating attributes for CloudEvent, including required fields
        attributes = {
            "type": "com.example.someevent",
            "source": "https://example.com/event-source",
        }

        # Constructing the CloudEvent object
        cloud_event = CloudEvent(
            attributes=attributes, data={"message": {"data": message_data}}
        )

        try:
            extract_location_pubsub(cloud_event)
            self.assertTrue(False)
        except Exception:
            self.assertTrue(True)
        data = {}  # empty data
        message_data = base64.b64encode(json.dumps(data).encode("utf-8")).decode(
            "utf-8"
        )
        cloud_event = CloudEvent(
            attributes=attributes, data={"message": {"data": message_data}}
        )
        try:
            extract_location_pubsub(cloud_event)
            self.assertTrue(False)
        except Exception:
            self.assertTrue(True)

    @mock.patch.dict(
        os.environ,
        {
            "FEEDS_DATABASE_URL": default_db_url,
            "GOOGLE_APPLICATION_CREDENTIALS": "dummy-credentials.json",
        },
    )
    @patch("extract_location.src.main.get_gtfs_feed_bounds_and_points")
    @patch("extract_location.src.main.update_dataset_bounding_box")
    @patch("extract_location.src.main.Logger")
    @patch("extract_location.src.main.DatasetTraceService")
    def test_extract_location(
        self, __, mock_dataset_trace, update_bb_mock, get_gtfs_feed_bounds_mock
    ):
        get_gtfs_feed_bounds_mock.return_value = (
            np.array(
                [
                    faker.longitude(),
                    faker.latitude(),
                    faker.longitude(),
                    faker.latitude(),
                ]
            ),
            None,
        )
        mock_dataset_trace.save.return_value = None
        mock_dataset_trace.get_by_execution_and_stable_ids.return_value = 0

        data = {
            "stable_id": faker.pystr(),
            "dataset_id": faker.pystr(),
            "url": faker.url(),
        }
        message_data = base64.b64encode(json.dumps(data).encode("utf-8")).decode(
            "utf-8"
        )

        # Creating attributes for CloudEvent, including required fields
        attributes = {
            "type": "com.example.someevent",
            "source": "https://example.com/event-source",
        }

        # Constructing the CloudEvent object
        cloud_event = CloudEvent(
            attributes=attributes, data={"message": {"data": message_data}}
        )
        extract_location_pubsub(cloud_event)
        update_bb_mock.assert_called_once()

    @mock.patch.dict(
        os.environ,
        {
            "FEEDS_DATABASE_URL": default_db_url,
            "MAXIMUM_EXECUTIONS": "1",
            "GOOGLE_APPLICATION_CREDENTIALS": "dummy-credentials.json",
        },
    )
    @patch("extract_location.src.main.get_gtfs_feed_bounds_and_points")
    @patch("extract_location.src.main.update_dataset_bounding_box")
    @patch(
        "extract_location.src.main.DatasetTraceService.get_by_execution_and_stable_ids"
    )
    @patch("extract_location.src.main.Logger")
    @patch("google.cloud.datastore.Client")
    def test_extract_location_max_executions(
        self, _, __, mock_dataset_trace, update_bb_mock, get_gtfs_feed_bounds_mock
    ):
        get_gtfs_feed_bounds_mock.return_value = np.array(
            [faker.longitude(), faker.latitude(), faker.longitude(), faker.latitude()]
        )
        mock_dataset_trace.return_value = [1, 2, 3]

        data = {
            "stable_id": faker.pystr(),
            "dataset_id": faker.pystr(),
            "url": faker.url(),
        }
        message_data = base64.b64encode(json.dumps(data).encode("utf-8")).decode(
            "utf-8"
        )

        # Creating attributes for CloudEvent, including required fields
        attributes = {
            "type": "com.example.someevent",
            "source": "https://example.com/event-source",
        }

        # Constructing the CloudEvent object
        cloud_event = CloudEvent(
            attributes=attributes, data={"message": {"data": message_data}}
        )
        extract_location_pubsub(cloud_event)
        update_bb_mock.assert_not_called()

    @mock.patch.dict(
        os.environ,
        {
            "FEEDS_DATABASE_URL": default_db_url,
            "GOOGLE_APPLICATION_CREDENTIALS": "dummy-credentials.json",
        },
    )
    @patch("extract_location.src.main.get_gtfs_feed_bounds_and_points")
    @patch("extract_location.src.main.update_dataset_bounding_box")
    @patch("extract_location.src.main.DatasetTraceService")
    @patch("extract_location.src.main.Logger")
    def test_extract_location_cloud_event(
        self, _, mock_dataset_trace, update_bb_mock, get_gtfs_feed_bounds_mock
    ):
        get_gtfs_feed_bounds_mock.return_value = (
            np.array(
                [
                    faker.longitude(),
                    faker.latitude(),
                    faker.longitude(),
                    faker.latitude(),
                ]
            ),
            None,
        )
        mock_dataset_trace.save.return_value = None
        mock_dataset_trace.get_by_execution_and_stable_ids.return_value = 0

        file_name = faker.file_name()
        resource_name = (
            f"{faker.uri_path()}/{faker.pystr()}/{faker.pystr()}/{file_name}"
        )
        bucket_name = faker.pystr()

        data = {
            "protoPayload": {"resourceName": resource_name},
            "resource": {"labels": {"bucket_name": bucket_name}},
        }
        cloud_event = MagicMock()
        cloud_event.data = data

        extract_location(cloud_event)
        update_bb_mock.assert_called_once()

    @mock.patch.dict(
        os.environ,
        {
            "FEEDS_DATABASE_URL": default_db_url,
            "GOOGLE_APPLICATION_CREDENTIALS": "dummy-credentials.json",
        },
    )
    @patch("extract_location.src.main.get_gtfs_feed_bounds_and_points")
    @patch("extract_location.src.main.update_dataset_bounding_box")
    @patch("extract_location.src.main.Logger")
    def test_extract_location_cloud_event_error(
        self, _, update_bb_mock, get_gtfs_feed_bounds_mock
    ):
        get_gtfs_feed_bounds_mock.return_value = np.array(
            [faker.longitude(), faker.latitude(), faker.longitude(), faker.latitude()]
        )
        bucket_name = faker.pystr()

        # data with missing protoPayload
        data = {
            "resource": {"labels": {"bucket_name": bucket_name}},
        }
        cloud_event = MagicMock()
        cloud_event.data = data

        extract_location(cloud_event)
        update_bb_mock.assert_not_called()

    @mock.patch.dict(
        os.environ,
        {
            "FEEDS_DATABASE_URL": default_db_url,
            "GOOGLE_APPLICATION_CREDENTIALS": "dummy-credentials.json",
        },
    )
    @patch("extract_location.src.stops_utils.get_gtfs_feed_bounds_and_points")
    @patch("extract_location.src.main.update_dataset_bounding_box")
    @patch("extract_location.src.main.Logger")
    def test_extract_location_exception_2(
        self, _, update_bb_mock, get_gtfs_feed_bounds_mock
    ):
        get_gtfs_feed_bounds_mock.return_value = np.array(
            [faker.longitude(), faker.latitude(), faker.longitude(), faker.latitude()]
        )

        data = {
            "stable_id": faker.pystr(),
            "dataset_id": faker.pystr(),
            "url": faker.url(),
        }
        update_bb_mock.side_effect = Exception(faker.pystr())
        message_data = base64.b64encode(json.dumps(data).encode("utf-8")).decode(
            "utf-8"
        )
        attributes = {
            "type": "com.example.someevent",
            "source": "https://example.com/event-source",
        }

        # Constructing the CloudEvent object
        cloud_event = CloudEvent(
            attributes=attributes, data={"message": {"data": message_data}}
        )

        try:
            extract_location_pubsub(cloud_event)
            assert False
        except Exception:
            assert True

    @mock.patch.dict(
        os.environ,
        {
            "FEEDS_DATABASE_URL": default_db_url,
            "PUBSUB_TOPIC_NAME": "test-topic",
            "PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "dummy-credentials.json",
        },
    )
    @patch("extract_location.src.main.start_db_session")
    @patch("extract_location.src.main.pubsub_v1.PublisherClient")
    @patch("extract_location.src.main.Logger")
    @patch("uuid.uuid4")
    def test_extract_location_batch(
        self, uuid_mock, logger_mock, publisher_client_mock, start_db_session_mock
    ):
        # Mock the database session and query
        mock_session = MagicMock()
        mock_dataset1 = Gtfsdataset(
            feed_id="1",
            stable_id="stable_1",
            hosted_url="http://example.com/1",
            latest=True,
            bounding_box=None,
        )
        mock_dataset2 = Gtfsdataset(
            feed_id="2",
            stable_id="stable_2",
            hosted_url="http://example.com/2",
            latest=True,
            bounding_box=None,
        )
        mock_session.query.return_value.filter.return_value.filter.return_value.all.return_value = [
            mock_dataset1,
            mock_dataset2,
        ]
        uuid_mock.return_value = "batch-uuid"
        start_db_session_mock.return_value = mock_session

        # Mock the Pub/Sub client
        mock_publisher = MagicMock()
        publisher_client_mock.return_value = mock_publisher
        mock_future = MagicMock()
        mock_future.result.return_value = "message_id"
        mock_publisher.publish.return_value = mock_future

        # Call the function
        response = extract_location_batch(None)

        # Assert logs and function responses
        logger_mock.init_logger.assert_called_once()
        mock_publisher.publish.assert_any_call(
            mock.ANY,
            json.dumps(
                {
                    "stable_id": "1",
                    "dataset_id": "stable_1",
                    "url": "http://example.com/1",
                    "execution_id": "batch-uuid",
                }
            ).encode("utf-8"),
        )
        mock_publisher.publish.assert_any_call(
            mock.ANY,
            json.dumps(
                {
                    "stable_id": "2",
                    "dataset_id": "stable_2",
                    "url": "http://example.com/2",
                    "execution_id": "batch-uuid",
                }
            ).encode("utf-8"),
        )
        self.assertEqual(response, ("Batch function triggered for 2 datasets.", 200))

    @mock.patch.dict(
        os.environ,
        {
            "FEEDS_DATABASE_URL": default_db_url,
            "GOOGLE_APPLICATION_CREDENTIALS": "dummy-credentials.json",
        },
    )
    @patch("extract_location.src.main.Logger")
    def test_extract_location_batch_no_topic_name(self, logger_mock):
        response = extract_location_batch(None)
        self.assertEqual(
            response, ("PUBSUB_TOPIC_NAME environment variable not set.", 500)
        )

    @mock.patch.dict(
        os.environ,
        {
            "FEEDS_DATABASE_URL": default_db_url,
            "PUBSUB_TOPIC_NAME": "test-topic",
            "PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "dummy-credentials.json",
        },
    )
    @patch("extract_location.src.main.start_db_session")
    @patch("extract_location.src.main.Logger")
    def test_extract_location_batch_exception(self, logger_mock, start_db_session_mock):
        # Mock the database session to raise an exception
        start_db_session_mock.side_effect = Exception("Database error")

        response = extract_location_batch(None)
        self.assertEqual(response, ("Error while fetching datasets.", 500))
