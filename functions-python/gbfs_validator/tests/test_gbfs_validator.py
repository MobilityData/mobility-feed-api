import base64
import copy
import json
import os
import unittest
import uuid
from unittest.mock import patch, MagicMock

from cloudevents.http import CloudEvent

from main import (
    gbfs_validator_pubsub,
    gbfs_validator_batch,
    fetch_all_gbfs_feeds,
)
from test_shared.test_utils.database_utils import default_db_url, reset_database_class


class TestMainFunctions(unittest.TestCase):
    def tearDown(self) -> None:
        reset_database_class()
        return super().tearDown()

    @patch.dict(
        os.environ,
        {
            "FEEDS_DATABASE_URL": default_db_url,
            "BUCKET_NAME": "mock-bucket",
            "MAXIMUM_EXECUTIONS": "1",
            "PUBSUB_TOPIC_NAME": "mock-topic",
            "PROJECT_ID": "mock-project",
            "VALIDATOR_URL": "https://mock-validator-url.com",
        },
    )
    @patch("main.DatasetTraceService")
    @patch("main.GBFSDataProcessor.process_gbfs_data")
    def test_gbfs_validator_pubsub(
        self,
        _,
        mock_dataset_trace_service,
    ):
        # Prepare mocks
        mock_trace_service = MagicMock()
        mock_dataset_trace_service.return_value = mock_trace_service

        # Prepare a mock CloudEvent
        data = {
            "execution_id": str(uuid.uuid4()),
            "stable_id": "mock-stable-id",
            "url": "http://mock-url.com",
            "feed_id": str(uuid.uuid4()),
        }
        base64_data = base64.b64encode(json.dumps(data).encode("utf-8"))
        cloud_event = CloudEvent(
            attributes={
                "type": "com.example.someevent",
                "source": "https://example.com/event-source",
            },
            data={"message": {"data": base64_data}},
        )
        # Call the function
        result = gbfs_validator_pubsub(cloud_event)
        self.assertEqual(result, "GBFS data processed and stored successfully.")

    @patch.dict(
        os.environ,
        {
            "PUBSUB_TOPIC_NAME": "mock-topic",
        },
    )
    @patch("main.pubsub_v1.PublisherClient")
    @patch("main.fetch_all_gbfs_feeds")
    def test_gbfs_validator_batch(
        self, mock_fetch_all_gbfs_feeds, mock_publisher_client
    ):
        # Prepare mocks
        mock_session = MagicMock()
        # mock_database.return_value.start_db_session.return_value = mock_session

        mock_publisher = MagicMock()
        mock_publisher_client.return_value = mock_publisher

        mock_feed = MagicMock()
        mock_feed.stable_id = "mock-stable-id"
        mock_feed.id = str(uuid.uuid4())
        mock_feed.auto_discovery_url = "http://mock-url.com"
        mock_feed.gbfsversions = [MagicMock(version="1.0")]
        mock_feed_2 = copy.deepcopy(mock_feed)
        mock_feed_2.gbfsversions = []
        mock_fetch_all_gbfs_feeds.return_value = [mock_feed, mock_feed_2]

        # Call the function
        result = gbfs_validator_batch(None, db_session=mock_session)
        self.assertEqual(result[1], 200)

        mock_fetch_all_gbfs_feeds.assert_called_once()
        self.assertEqual(mock_publisher.publish.call_count, 2)

    def test_gbfs_validator_batch_missing_topic(self):
        # Call the function
        result = gbfs_validator_batch(None)
        self.assertEqual(result[1], 500)

    def test_fetch_all_gbfs_feeds(self):
        mock_session = MagicMock()
        db = MagicMock()
        db._get_session = MagicMock()
        db._get_session.return_value.return_value = mock_session

        mock_feed = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = [
            mock_feed
        ]

        result = fetch_all_gbfs_feeds(db_session=mock_session)
        self.assertEqual(result, [mock_feed])

    def test_fetch_all_gbfs_feeds_exception(self):
        mock_session = MagicMock()
        db = MagicMock()
        db._get_session = MagicMock()
        db._get_session.return_value.return_value = mock_session

        # Simulate an exception when querying the database
        mock_session.query.side_effect = Exception("Database error")

        with self.assertRaises(Exception) as context:
            fetch_all_gbfs_feeds(mock_session)

        self.assertTrue("Database error" in str(context.exception))

    def test_fetch_all_gbfs_feeds_none_session(self):
        with self.assertRaises(Exception) as context:
            fetch_all_gbfs_feeds(None)

        self.assertTrue("NoneType" in str(context.exception))

    @patch.dict(
        os.environ,
        {
            "PUBSUB_TOPIC_NAME": "mock-topic",
        },
    )
    @patch("main.fetch_all_gbfs_feeds")
    def test_gbfs_validator_batch_fetch_exception(self, mock_fetch_all_gbfs_feeds):
        # Prepare mocks
        mock_fetch_all_gbfs_feeds.side_effect = Exception("Database error")

        # Call the function
        result = gbfs_validator_batch(None)
        self.assertEqual(result[1], 500)

        mock_fetch_all_gbfs_feeds.assert_called_once()

    @patch.dict(
        os.environ,
        {
            "PUBSUB_TOPIC_NAME": "mock-topic",
        },
    )
    @patch("main.pubsub_v1.PublisherClient")
    @patch("main.fetch_all_gbfs_feeds")
    def test_gbfs_validator_batch_publish_exception(
        self, mock_fetch_all_gbfs_feeds, mock_publisher_client
    ):
        # Prepare mocks

        mock_publisher_client.side_effect = Exception("Pub/Sub error")

        mock_feed = MagicMock()
        mock_feed.stable_id = "mock-stable-id"
        mock_feed.id = str(uuid.uuid4())
        mock_feed.auto_discovery_url = "http://mock-url.com"
        mock_feed.gbfsversions = [MagicMock(version="1.0")]
        mock_feed_2 = copy.deepcopy(mock_feed)
        mock_feed_2.gbfsversions = []
        mock_fetch_all_gbfs_feeds.return_value = [mock_feed, mock_feed_2]

        # Call the function
        result = gbfs_validator_batch(None)
        self.assertEqual(result[1], 500)

    @patch.dict(
        os.environ,
        {
            "PUBSUB_TOPIC_NAME": "mock-topic",
        },
    )
    @patch("main.pubsub_v1.PublisherClient")
    @patch("main.fetch_gbfs_feeds_by_ids")
    def test_gbfs_validator_batch_by_feed_ids(
        self, mock_fetch_gbfs_feeds_by_ids, mock_publisher_client
    ):
        # Prepare mocks
        mock_session = MagicMock()
        # mock_database.return_value.start_db_session.return_value = mock_session

        mock_publisher = MagicMock()
        mock_publisher_client.return_value = mock_publisher

        mock_feed = MagicMock()
        mock_feed.stable_id = "mock-stable-id"
        mock_feed.id = str(uuid.uuid4())
        mock_feed.auto_discovery_url = "http://mock-url.com"
        mock_feed.gbfsversions = [MagicMock(version="1.0")]
        mock_feed_2 = copy.deepcopy(mock_feed)
        mock_feed_2.gbfsversions = []
        mock_fetch_gbfs_feeds_by_ids.return_value = [mock_feed, mock_feed_2]
        request = MagicMock()
        request.method = "POST"
        request.is_json = True
        request.get_json.return_value = {"feed_ids": [mock_feed.id, mock_feed_2.id]}
        # Call the function
        result = gbfs_validator_batch(request, db_session=mock_session)
        self.assertEqual(result[1], 200)

        mock_fetch_gbfs_feeds_by_ids.assert_called_once()
        self.assertEqual(mock_publisher.publish.call_count, 2)
