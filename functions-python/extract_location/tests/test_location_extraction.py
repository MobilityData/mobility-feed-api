import base64
import json
import os
import unittest
from unittest import mock
from unittest.mock import patch, MagicMock

import numpy as np
from cloudevents.http import CloudEvent
from faker import Faker

from database_gen.sqlacodegen_models import Gtfsdataset, Feed
from extract_location.src.main import (
    extract_location,
    extract_location_pubsub,
    extract_location_batch,
)
from test_utils.database_utils import default_db_url

faker = Faker()


class TestMainFunctions(unittest.TestCase):
    @patch("extract_location.src.main.Logger")
    @patch("extract_location.src.main.DatasetTraceService")
    def test_extract_location_exception(self, _, __):
        data = {"stable_id": faker.pystr(), "dataset_id": faker.pystr()}
        message_data = base64.b64encode(json.dumps(data).encode("utf-8")).decode(
            "utf-8"
        )

        attributes = {
            "type": "com.example.someevent",
            "source": "https://example.com/event-source",
        }

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

        attributes = {
            "type": "com.example.someevent",
            "source": "https://example.com/event-source",
        }

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

        attributes = {
            "type": "com.example.someevent",
            "source": "https://example.com/event-source",
        }

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
    @patch("extract_location.src.main.Database")
    @patch("extract_location.src.main.pubsub_v1.PublisherClient")
    @patch("extract_location.src.main.Logger")
    @patch("uuid.uuid4")
    def test_extract_location_batch(
        self, uuid_mock, logger_mock, publisher_client_mock, database_mock
    ):
        mock_session = MagicMock()
        mock_dataset1 = Gtfsdataset(
            feed_id="1",
            stable_id="stable_1",
            hosted_url="http://example.com/1",
            latest=True,
            bounding_box=None,
            feed=Feed(stable_id="1"),
        )
        mock_dataset2 = Gtfsdataset(
            feed_id="2",
            stable_id="stable_2",
            hosted_url="http://example.com/2",
            latest=True,
            bounding_box=None,
            feed=Feed(stable_id="2"),
        )
        tmp = (
            mock_session.query.return_value.filter.return_value.filter.return_value.options.return_value
        )
        tmp.all.return_value = [
            mock_dataset1,
            mock_dataset2,
        ]
        uuid_mock.return_value = "batch-uuid"
        database_mock.return_value.start_db_session.return_value.__enter__.return_value = (
            mock_session
        )

        mock_publisher = MagicMock()
        publisher_client_mock.return_value = mock_publisher
        mock_future = MagicMock()
        mock_future.result.return_value = "message_id"
        mock_publisher.publish.return_value = mock_future

        response = extract_location_batch(None)

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
    @patch("extract_location.src.main.Database")
    @patch("extract_location.src.main.Logger")
    def test_extract_location_batch_exception(self, logger_mock, database_mock):
        database_mock.return_value.start_db_session.side_effect = Exception(
            "Database error"
        )

        response = extract_location_batch(None)
        self.assertEqual(response, ("Error while fetching datasets.", 500))
