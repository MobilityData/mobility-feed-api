import os
from shared.database_gen.sqlacodegen_models import Feed
import logging
import json
from google.cloud import pubsub_v1

PROJECT_ID = os.getenv("PROJECT_ID")
DATASET_BATCH_TOPIC = os.getenv("DATASET_PROCESSING_TOPIC_NAME")


def trigger_dataset_download(
    feed: Feed, execution_id: str, publisher: pubsub_v1.PublisherClient
) -> None:
    """Publishes the feed to the configured Pub/Sub topic."""
    topic_path = publisher.topic_path(PROJECT_ID, DATASET_BATCH_TOPIC)
    logging.debug("Publishing to Pub/Sub topic: %s", topic_path)

    message_data = {
        "execution_id": execution_id,
        "producer_url": feed.producer_url,
        "feed_stable_id": feed.stable_id,
        "feed_id": feed.id,
        "dataset_id": None,
        "dataset_hash": None,
        "authentication_type": feed.authentication_type,
        "authentication_info_url": feed.authentication_info_url,
        "api_key_parameter_name": feed.api_key_parameter_name,
    }

    try:
        # Convert to JSON string
        json_message = json.dumps(message_data)
        future = publisher.publish(topic_path, data=json_message.encode("utf-8"))
        future.add_done_callback(
            lambda _: logging.info(
                "Published feed %s to dataset batch topic", feed.stable_id
            )
        )
        future.result()
        logging.info("Message published for feed %s", feed.stable_id)
    except Exception as e:
        logging.error("Error publishing to dataset batch topic: %s", str(e))
        raise
