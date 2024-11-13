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

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Create logger instance
logger = logging.getLogger("feed_processor")
handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


src.main.logger = logger

# Load environment variables from .env.local
load_dotenv(dotenv_path=".env.local_test")


@dataclass
class CloudEvent:
    attributes: dict
    data: dict


if __name__ == "__main__":
    logger.info("Starting local debug session...")

    # Define cloud event attributes
    attributes = {
        "type": "com.google.cloud.pubsub.topic.publish",
        "source": "//pubsub.googleapis.com/projects/sample-project/topics/sample-topic",
    }

    feed_payload = {
        "external_id": "test-feed-1",
        "feed_id": "feed1",
        "feed_url": "http://example.com/test-feed",
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

    # Create and process cloud event
    cloud_event = CloudEvent(attributes, data)
    logger.info("\nProcessing new feed event:")
    logger.info("-" * 50)
    process_feed_event(cloud_event)

    logger.info("\nProcessing update feed event:")
    logger.info("-" * 50)
    update_payload = feed_payload.copy()
    update_payload["feed_url"] = "http://example.com/test-feed-updated"
    update_payload["payload_type"] = "update"

    update_data = {
        "message": {
            "data": base64.b64encode(json.dumps(update_payload).encode("utf-8")).decode(
                "utf-8"
            )
        }
    }

    cloud_event_update = CloudEvent(attributes, update_data)
    process_feed_event(cloud_event_update)

    logger.info("Local debug session completed.")
