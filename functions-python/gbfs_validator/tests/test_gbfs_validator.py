import base64
import copy
import json
import os
import unittest
import uuid
from unittest.mock import patch, MagicMock

from cloudevents.http import CloudEvent

from gbfs_validator.src.main import (
    gbfs_validator_pubsub,
    gbfs_validator_batch,
    fetch_all_gbfs_feeds,
)
from test_utils.database_utils import default_db_url


class TestMainFunctions(unittest.TestCase):
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
    @patch("gbfs_validator.src.main.start_db_session")
    @patch("gbfs_validator.src.main.DatasetTraceService")
    @patch("gbfs_validator.src.main.fetch_gbfs_files")
    @patch("gbfs_validator.src.main.GBFSValidator.create_gbfs_json_with_bucket_paths")
    @patch("gbfs_validator.src.main.GBFSValidator.create_snapshot")
    @patch("gbfs_validator.src.main.GBFSValidator.validate_gbfs_feed")
    @patch("gbfs_validator.src.main.save_snapshot_and_report")
    @patch("gbfs_validator.src.main.Logger")
    @patch("gbfs_validator.src.main.storage.Client")
    def test_gbfs_validator_pubsub(
        self,
        __,
        _,  # mock_logger
        mock_save_snapshot_and_report,
        mock_validate_gbfs_feed,
        mock_create_snapshot,
        mock_create_gbfs_json,
        mock_fetch_gbfs_files,
        mock_dataset_trace_service,
        mock_start_db_session,
    ):
        # Prepare mocks
        mock_session = MagicMock()
        mock_start_db_session.return_value = mock_session

        mock_trace_service = MagicMock()
        mock_dataset_trace_service.return_value = mock_trace_service

        mock_create_snapshot.return_value = MagicMock()

        mock_validate_gbfs_feed.return_value = {
            "report_summary_url": "http://report-summary-url.com",
            "json_report_summary": {"summary": "validation report"},
        }

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
        self.assertEqual(result, "GBFS files processed and stored successfully.")

        mock_fetch_gbfs_files.assert_called_once_with("http://mock-url.com")
        mock_create_gbfs_json.assert_called_once()
        mock_create_snapshot.assert_called_once()
        mock_validate_gbfs_feed.assert_called_once()
        mock_save_snapshot_and_report.assert_called_once()

    @patch.dict(
        os.environ,
        {
            "PUBSUB_TOPIC_NAME": "mock-topic",
        },
    )
    @patch("gbfs_validator.src.main.start_db_session")
    @patch("gbfs_validator.src.main.pubsub_v1.PublisherClient")
    @patch("gbfs_validator.src.main.fetch_all_gbfs_feeds")
    @patch("gbfs_validator.src.main.Logger")
    def test_gbfs_validator_batch(
        self, _, mock_fetch_all_gbfs_feeds, mock_publisher_client, mock_start_db_session
    ):
        # Prepare mocks
        mock_session = MagicMock()
        mock_start_db_session.return_value = mock_session

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
        result = gbfs_validator_batch(None)
        self.assertEqual(result[1], 200)

        mock_fetch_all_gbfs_feeds.assert_called_once()
        self.assertEqual(mock_publisher.publish.call_count, 2)

    @patch("gbfs_validator.src.main.Logger")
    def test_gbfs_validator_batch_missing_topic(self, _):  # mock_logger
        # Call the function
        result = gbfs_validator_batch(None)
        self.assertEqual(result[1], 500)

    @patch("gbfs_validator.src.main.start_db_session")
    @patch("gbfs_validator.src.main.Logger")
    def test_fetch_all_gbfs_feeds(self, _, mock_start_db_session):
        mock_session = MagicMock()
        mock_start_db_session.return_value = mock_session
        mock_feed = MagicMock()
        mock_session.query.return_value.options.return_value.all.return_value = [
            mock_feed
        ]

        result = fetch_all_gbfs_feeds()
        self.assertEqual(result, [mock_feed])

        mock_start_db_session.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("gbfs_validator.src.main.start_db_session")
    @patch("gbfs_validator.src.main.Logger")
    def test_fetch_all_gbfs_feeds_exception(self, _, mock_start_db_session):
        mock_session = MagicMock()
        mock_start_db_session.return_value = mock_session

        # Simulate an exception when querying the database
        mock_session.query.side_effect = Exception("Database error")

        with self.assertRaises(Exception) as context:
            fetch_all_gbfs_feeds()

        self.assertTrue("Database error" in str(context.exception))

        mock_start_db_session.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("gbfs_validator.src.main.start_db_session")
    def test_fetch_all_gbfs_feeds_none_session(self, mock_start_db_session):
        mock_start_db_session.return_value = None

        with self.assertRaises(Exception) as context:
            fetch_all_gbfs_feeds()

        self.assertTrue("NoneType" in str(context.exception))

        mock_start_db_session.assert_called_once()

    @patch.dict(
        os.environ,
        {
            "PUBSUB_TOPIC_NAME": "mock-topic",
        },
    )
    @patch("gbfs_validator.src.main.fetch_all_gbfs_feeds")
    @patch("gbfs_validator.src.main.Logger")
    def test_gbfs_validator_batch_fetch_exception(self, _, mock_fetch_all_gbfs_feeds):
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
    @patch("gbfs_validator.src.main.start_db_session")
    @patch("gbfs_validator.src.main.pubsub_v1.PublisherClient")
    @patch("gbfs_validator.src.main.fetch_all_gbfs_feeds")
    @patch("gbfs_validator.src.main.Logger")
    def test_gbfs_validator_batch_publish_exception(
        self, _, mock_fetch_all_gbfs_feeds, mock_publisher_client, mock_start_db_session
    ):
        # Prepare mocks
        mock_session = MagicMock()
        mock_start_db_session.return_value = mock_session

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

        mock_fetch_all_gbfs_feeds.assert_called_once()
        mock_publisher_client.assert_called_once()