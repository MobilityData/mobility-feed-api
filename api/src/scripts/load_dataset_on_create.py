import json
import os
import threading
import uuid
from typing import List
from concurrent import futures

from google.auth import default
from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.futures import Future

from database_gen.sqlacodegen_models import Feed
from utils.logger import Logger

# Lazy create so we won't try to connect to google cloud when the file is imported.
pubsub_client = None

lock = threading.Lock()
logger = Logger("load_dataset_on_create").get_logger()


def get_pubsub_client():
    with lock:
        global pubsub_client
        if pubsub_client is None:
            pubsub_client = pubsub_v1.PublisherClient()

    return pubsub_client


def get_topic_path():
    env = os.getenv("ENV", "dev")
    pubsub_topic_name = f"datasets-batch-topic-{env}"
    project_id = f"mobility-feeds-{env}"  # Cannot use GOOGLE_CLOUD_PROJECT because it points to QA for DEV
    return get_pubsub_client().topic_path(project_id, pubsub_topic_name)


def publish_callback(future: Future, stable_id: str, topic_path: str):
    """
    Callback function for when the message is published to Pub/Sub.
    This function logs the result of the publishing operation.
    @param future: Future object representing the result of the publishing operation
    @param stable_id: The stable_id of the feed that was published
    @param topic_path: The path to the Pub/Sub topic
    """
    if future.exception():
        logger.info(f"Error publishing feed {stable_id} to Pub/Sub topic {topic_path}: {future.exception()}")
    else:
        logger.info(f"Published stable_id = {stable_id}.")


def publish(feed: Feed, topic_path: str) -> Future:
    """
    Publishes a feed to the Pub/Sub topic.
    :param feed: The feed to publish
    :param topic_path: The path to the Pub/Sub topic
    :return: The Future object representing the result of the publishing operation
    """
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
    future = get_pubsub_client().publish(topic_path, data=data_bytes)
    future.add_done_callback(lambda _: publish_callback(future, feed.stable_id, topic_path))
    return future


def publish_all(feeds: List[Feed]):
    """
    Publishes a list of feeds to the Pub/Sub topic.
    :param feeds: The list of feeds to publish
    """
    topic_path = get_topic_path()
    logger.info(f"Publishing {len(feeds)} feeds to Pub/Sub topic {topic_path}...")
    credentials, project = default()
    logger.info(f"Authenticated project: {project}")
    logger.info(f"Service Account Email: {credentials.service_account_email}")
    publish_futures = []
    for feed in feeds:
        logger.info(f"Publishing feed {feed.stable_id} to Pub/Sub topic {topic_path}...")
        future = publish(feed, topic_path)
        publish_futures.append(future)
    futures.wait(publish_futures, return_when=futures.ALL_COMPLETED)
    logger.info(f"Published {len(feeds)} feeds to Pub/Sub topic {topic_path}.")
