"""
Code to be able to debug locally without affecting the runtime cloud function.

Requirements:
- Google Cloud SDK installed
- Make sure to have the following environment variables set in your .env.local file:
  - PROJECT_ID
  - DATASET_BATCH_TOPIC_NAME
  - FEEDS_DATABASE_URL
- Local database in running state

Usage:
- python feed_sync_process_transitland/main_local_debug.py
"""

import base64
import json
import os
from unittest.mock import MagicMock, patch
import logging
import sys

import pytest
from dotenv import load_dotenv

# Configure local logging first
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger("feed_processor")

# Mock the Google Cloud Logger


class MockLogger:

    """Mock logger class"""

    @staticmethod
    def init_logger():
        return MagicMock()

    def __init__(self, name):
        self.name = name

    def get_logger(self):
        return logger

    def addFilter(self, filter):
        pass


with patch("helpers.logger.Logger", MockLogger):
    from feed_sync_process_transitland.src.main import process_feed_event

# Load environment variables
load_dotenv(dotenv_path=".env.rename_me")


class CloudEvent:
    """Cloud Event data structure."""

    def __init__(self, attributes: dict, data: dict):
        self.attributes = attributes
        self.data = data


@pytest.fixture
def mock_pubsub():
    """Fixture to mock PubSub client"""
    with patch("google.cloud.pubsub_v1.PublisherClient") as mock_publisher:
        publisher_instance = MagicMock()

        def mock_topic_path(project_id, topic_id):
            return f"projects/{project_id}/topics/{topic_id}"

        def mock_publish(topic_path, data):
            logger.info(
                f"[LOCAL DEBUG] Would publish to {topic_path}: {data.decode('utf-8')}"
            )
            future = MagicMock()
            future.result.return_value = "message_id"
            return future

        publisher_instance.topic_path.side_effect = mock_topic_path
        publisher_instance.publish.side_effect = mock_publish
        mock_publisher.return_value = publisher_instance

        yield mock_publisher


def process_event_safely(cloud_event, description=""):
    """Process event with error handling."""
    try:
        logger.info(f"\nProcessing {description}:")
        logger.info("-" * 50)
        result = process_feed_event(cloud_event)
        logger.info(f"Process result: {result}")
        return True
    except Exception as e:
        logger.error(f"Error processing {description}: {str(e)}")
        return False


def main():
    """Main function to run local debug tests"""
    logger.info("Starting local debug session...")

    # Define test event data
    test_payload = {
        "external_id": "test-feed-1",
        "feed_id": "feed1",
        "feed_url": "https://example.com/test-feed-2",
        "execution_id": "local-debug-123",
        "spec": "gtfs",
        "auth_info_url": None,
        "auth_param_name": None,
        "type": None,
        "operator_name": "Test Operator",
        "country": "USA",
        "state_province": "CA",
        "city_name": "Test City",
        "source": "TLD",
        "payload_type": "new",
    }

    # Create cloud event
    cloud_event = CloudEvent(
        attributes={
            "type": "com.google.cloud.pubsub.topic.publish",
            "source": f"//pubsub.googleapis.com/projects/{os.getenv('PROJECT_ID')}/topics/test-topic",
        },
        data={
            "message": {
                "data": base64.b64encode(
                    json.dumps(test_payload).encode("utf-8")
                ).decode("utf-8")
            }
        },
    )

    # Set up mocks
    with patch(
        "google.cloud.pubsub_v1.PublisherClient", new_callable=MagicMock
    ) as mock_publisher, patch("google.cloud.logging.Client", MagicMock()):
        publisher_instance = MagicMock()

        def mock_topic_path(project_id, topic_id):
            return f"projects/{project_id}/topics/{topic_id}"

        def mock_publish(topic_path, data):
            logger.info(
                f"[LOCAL DEBUG] Would publish to {topic_path}: {data.decode('utf-8')}"
            )
            future = MagicMock()
            future.result.return_value = "message_id"
            return future

        publisher_instance.topic_path.side_effect = mock_topic_path
        publisher_instance.publish.side_effect = mock_publish
        mock_publisher.return_value = publisher_instance

        # Process test event
        process_event_safely(cloud_event, "test feed event")

    logger.info("Local debug session completed.")


if __name__ == "__main__":
    main()
