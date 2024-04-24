import json
import os
import uuid
from typing import List

from database_gen.sqlacodegen_models import Feed
from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.futures import Future

pubsub_topic_name = os.getenv("PUBSUB_TOPIC_NAME", "datasets-batch-topic-dev")
project_id = os.getenv("PROJECT_ID", "mobility-feeds-dev")
pubsub_client = pubsub_v1.PublisherClient()


def get_topic_path():
    if pubsub_topic_name is None or project_id is None:
        raise ValueError("PUBSUB_TOPIC_NAME and PROJECT_ID must be set in the environment")
    return pubsub_client.topic_path(project_id, pubsub_topic_name)


def publish_callback(future: Future, stable_id: str, topic_path: str):
    """
    Callback function for when the message is published to Pub/Sub.
    This function logs the result of the publishing operation.
    """
    if future.exception():
        print(f"Error publishing feed {stable_id} to Pub/Sub topic {topic_path}: {future.exception()}")
    else:
        print(f"Published stable_id={stable_id}.")


def publish(feed: Feed, topic_path: str):
    payload = {
        "execution_id": f"batch-uuid-{uuid.uuid4()}",
        "producer_url": feed.producer_url,
        "feed_stable_id": feed.stable_id,
        "feed_id": feed.id,
        "dataset_id": None,  # The feed is not associated with a dataset
        "dataset_hash": None,
        "authentication_type": feed.authentication_type,
        "authentication_info_url": feed.authentication_info_url,
        "api_key_parameter_name": feed.api_key_parameter_name,
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    future = pubsub_client.publish(topic_path, data=data_bytes)
    future.add_done_callback(lambda _: publish_callback(future, feed.stable_id, topic_path))


def publish_all(feeds: List[Feed]):
    topic_path = get_topic_path()
    for feed in feeds:
        publish(feed, topic_path)
