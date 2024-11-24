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
import os
import uuid
from datetime import datetime

import functions_framework
from google.cloud import pubsub_v1
from google.cloud.pubsub_v1 import PublisherClient
from google.cloud.pubsub_v1.futures import Future
from sqlalchemy import or_
from sqlalchemy.orm import Session
from database_gen.sqlacodegen_models import Gtfsfeed, Gtfsdataset
from dataset_service.main import BatchExecutionService, BatchExecution
from helpers.database import Database

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
        print(
            f"Error publishing feed {stable_id} to Pub/Sub topic {topic_path}: {future.exception()}"
        )
    else:
        print(f"Published stable_id={stable_id}.")


def publish(publisher: PublisherClient, topic_path: str, data_bytes: bytes) -> Future:
    """
    Publishes the given data to the Pub/Sub topic.
    """
    return publisher.publish(topic_path, data=data_bytes)


def get_non_deprecated_feeds(session: Session):
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
            Gtfsdataset.id.label("dataset_id"),
            Gtfsdataset.hash.label("dataset_hash"),
        )
        .select_from(Gtfsfeed)
        .outerjoin(Gtfsdataset, (Gtfsdataset.feed_id == Gtfsfeed.id))
        .filter(Gtfsfeed.status != "deprecated")
        .filter(or_(Gtfsdataset.id.is_(None), Gtfsdataset.latest.is_(True)))
    )
    # Limit the query to 10 feeds (or FEEDS_LIMIT param) for testing purposes and lower environments
    if os.getenv("ENVIRONMENT", "").lower() in ("dev", "test", "qa"):
        limit = os.getenv("FEEDS_LIMIT")
        query = query.limit(10 if limit is None else int(limit))
    results = query.all()
    print(f"Retrieved {len(results)} feeds.")

    return results


@functions_framework.http
def batch_datasets(request):
    """
    HTTP Function entry point queries the datasets and publishes them to a Pub/Sub topic to be processed.
    This function requires the following environment variables to be set:
        PUBSUB_TOPIC_NAME: name of the Pub/Sub topic to publish to
        FEEDS_DATABASE_URL: database URL
        PROJECT_ID: GCP project ID
    :param request: HTTP request object
    :return: HTTP response object
    """
    db = Database(database_url=os.getenv("FEEDS_DATABASE_URL"))
    try:
        with db.start_db_session() as session:
            feeds = get_non_deprecated_feeds(session)
    except Exception as error:
        print(f"Error retrieving feeds: {error}")
        raise Exception(f"Error retrieving feeds: {error}")
    finally:
        pass

    print(f"Retrieved {len(feeds)} feeds.")
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
            "dataset_id": feed.dataset_id,
            "dataset_hash": feed.dataset_hash,
            "authentication_type": feed.authentication_type,
            "authentication_info_url": feed.authentication_info_url,
            "api_key_parameter_name": feed.api_key_parameter_name,
        }
        data_str = json.dumps(payload)
        print(f"Publishing {data_str} to {topic_path}.")
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
    return f"Publish completed. Published {len(feeds)} feeds to {pubsub_topic_name}."
