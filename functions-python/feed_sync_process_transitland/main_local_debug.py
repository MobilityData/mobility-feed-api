# Code to be able to debug locally without affecting the runtime cloud function
#
# Requirements:
# - Google Cloud SDK installed
# - Make sure to have the following environment variables set in your .env.local file
# - Local database in running state
# - Follow the instructions in the README.md file
#
# Usage:
# - python feed_sync_process_transitland/main_local_debug.py

import base64
import json
import logging
from dataclasses import dataclass
from dotenv import load_dotenv
from feed_sync_process_transitland.src.main import process_feed_event
import src.main
from unittest.mock import Mock
from google.cloud import pubsub_v1

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("feed_processor")
handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

logger.addHandler(handler)
logger.setLevel(logging.INFO)

src.main.logger = logger

load_dotenv(dotenv_path=".env.local_test")


@dataclass
class CloudEvent:
    attributes: dict
    data: dict


# mock publisher client
class MockPublisherClient:
    def topic_path(self, project_id, topic_id):
        return f"projects/{project_id}/topics/{topic_id}"

    def publish(self, topic_path, data):
        logger.info(
            f"[LOCAL DEBUG] Would publish to {topic_path}: {data.decode('utf-8')}"
        )
        return Mock()  # Returns a mock future


# Mock real publisher
pubsub_v1.PublisherClient = MockPublisherClient


def process_event_safely(cloud_event, description=""):
    """Wrapper to handle event processing with better error handling"""
    try:
        logger.info(f"\nProcessing {description}:")
        logger.info("-" * 50)
        result = process_feed_event(cloud_event)
        logger.info(f"Process result: {result}")
    except Exception as e:
        logger.error(f"Error processing {description}: {str(e)}")
        return False
    return True


if __name__ == "__main__":
    logger.info("Starting local debug session...")

    # Define cloud event attributes
    attributes = {
        "type": "com.google.cloud.pubsub.topic.publish",
        "source": "//pubsub.googleapis.com/projects/sample-project/topics/sample-topic",
    }

    # New Feed
    feed_payload = {
        "external_id": "test-feed-1",
        "feed_id": "feed1",
        "feed_url": "https://example.com/test-feed",
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

    data = {
        "message": {
            "data": base64.b64encode(json.dumps(feed_payload).encode("utf-8")).decode(
                "utf-8"
            )
        }
    }

    # Process new feed event
    cloud_event = CloudEvent(attributes, data)
    new_feed_success = process_event_safely(cloud_event, "new feed event")

    # Update Feed (only if new feed was successful)
    if new_feed_success:
        update_payload = feed_payload.copy()
        update_payload["feed_url"] = "http://example.com/test-feed-updated"
        update_payload["payload_type"] = "update"

        update_data = {
            "message": {
                "data": base64.b64encode(
                    json.dumps(update_payload).encode("utf-8")
                ).decode("utf-8")
            }
        }

        cloud_event_update = CloudEvent(attributes, update_data)
        process_event_safely(cloud_event_update, "update feed event")

    logger.info("Local debug session completed.")
