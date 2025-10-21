#
#   MobilityData 2023
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Optional

import functions_framework
from google.cloud import pubsub_v1
from google.cloud.pubsub_v1 import PublisherClient
from google.cloud.pubsub_v1.futures import Future
from sqlalchemy.orm import Session

from shared.database_gen.sqlacodegen_models import Gtfsfeed, Gtfsdataset
from shared.dataset_service.dataset_service_commons import BatchExecution
from shared.dataset_service.main import BatchExecutionService
from shared.database.database import with_db_session
from shared.helpers.logger import init_logger

init_logger()
pubsub_topic_name = os.getenv("PUBSUB_TOPIC_NAME")
project_id = os.getenv("PROJECT_ID")


def get_pubsub_client():
    """
    Returns a Pub/Sub client.
    """
    return pubsub_v1.PublisherClient()


def publish_callback(future: Future, stable_id: str, topic_path: str):
    """
    Callback function for when the message is published to Pub/Sub.
    This function logs the result of the publishing operation.
    """
    if future.exception():
        logging.error(
            f"Error publishing feed {stable_id} to Pub/Sub topic {topic_path}: {future.exception()}"
        )
    else:
        logging.info(f"Published stable_id={stable_id}.")


def publish(publisher: PublisherClient, topic_path: str, data_bytes: bytes) -> Future:
    """
    Publishes the given data to the Pub/Sub topic.
    """
    return publisher.publish(topic_path, data=data_bytes)


def get_non_deprecated_feeds(
    session: Session, feed_stable_ids: Optional[list[str]] = None
):
    """
    Returns a list of non deprecated feeds
    :return: list of feeds
    """
    #  Query the database for Gtfs feeds with status different from deprecated
    query = (
        session.query(
            Gtfsfeed.stable_id,
            Gtfsfeed.producer_url,
            Gtfsfeed.id.label("feed_id"),
            Gtfsfeed.authentication_type,
            Gtfsfeed.authentication_info_url,
            Gtfsfeed.api_key_parameter_name,
            Gtfsfeed.status,
            Gtfsdataset.stable_id.label("dataset_stable_id"),
            Gtfsdataset.hash.label("dataset_hash"),
        )
        .select_from(Gtfsfeed)
        .outerjoin(Gtfsdataset, (Gtfsfeed.latest_dataset_id == Gtfsdataset.id))
        .filter(Gtfsfeed.status != "deprecated")
    )
    if feed_stable_ids:
        # If feed_stable_ids are provided, filter the query by stable IDs
        query = query.filter(Gtfsfeed.stable_id.in_(feed_stable_ids))
    # Limit the query to 10 feeds (or FEEDS_LIMIT param) for testing purposes and lower environments
    if os.getenv("ENVIRONMENT", "").lower() in ("dev", "test", "qa"):
        limit = os.getenv("FEEDS_LIMIT")
        query = query.limit(10 if limit is None else int(limit))
    results = query.all()
    return results


@with_db_session
@functions_framework.http
def batch_datasets(request, db_session: Session):
    """
    HTTP Function entry point queries the datasets and publishes them to a Pub/Sub topic to be processed.
    This function requires the following environment variables to be set:
        PUBSUB_TOPIC_NAME: name of the Pub/Sub topic to publish to
        FEEDS_DATABASE_URL: database URL
        PROJECT_ID: GCP project ID
    :param request: HTTP request object
    :param db_session: database session object
    :return: HTTP response object
    """
    feed_stable_ids = None
    try:
        request_json = request.get_json()
        feed_stable_ids = request_json.get("feed_stable_ids") if request_json else None
    except Exception:
        logging.info(
            "No feed_stable_ids provided in the request, processing all feeds."
        )

    try:
        feeds = get_non_deprecated_feeds(db_session, feed_stable_ids=feed_stable_ids)
    except Exception as error:
        logging.error(f"Error retrieving feeds: {error}")
        raise Exception(f"Error retrieving feeds: {error}")
    finally:
        pass

    logging.info(f"Retrieved {len(feeds)} feeds.")
    publisher = get_pubsub_client()
    topic_path = publisher.topic_path(project_id, pubsub_topic_name)
    trace_id = request.headers.get("X-Cloud-Trace-Context")
    execution_id = (
        f"batch-trace-{trace_id}" if trace_id else f"batch-uuid-{uuid.uuid4()}"
    )
    timestamp = datetime.now()
    for feed in feeds:
        payload = {
            "execution_id": execution_id,
            "producer_url": feed.producer_url,
            "feed_stable_id": feed.stable_id,
            "feed_id": feed.feed_id,
            "dataset_stable_id": feed.dataset_stable_id,
            "dataset_hash": feed.dataset_hash,
            "authentication_type": feed.authentication_type,
            "authentication_info_url": feed.authentication_info_url,
            "api_key_parameter_name": feed.api_key_parameter_name,
        }
        data_str = json.dumps(payload)
        logging.debug(f"Publishing {data_str} to {topic_path}.")
        future = publish(publisher, topic_path, data_str.encode("utf-8"))
        future.add_done_callback(
            lambda _: publish_callback(future, feed.stable_id, topic_path)
        )
    BatchExecutionService().save(
        BatchExecution(
            execution_id=execution_id,
            feeds_total=len(feeds),
            timestamp=timestamp,
        )
    )
    message = f"Publish completed. Published {len(feeds)} feeds to {pubsub_topic_name}."
    logging.info(message)
    return message
