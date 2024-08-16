import json
import logging
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any

import functions_framework
import requests
from cloudevents.http import CloudEvent
from google.cloud import pubsub_v1
from google.cloud import storage
from sqlalchemy.orm import joinedload

from database_gen.sqlacodegen_models import Gbfsfeed
from helpers.database import start_db_session
from helpers.logger import Logger
from helpers.parser import jsonify_pubsub
from dataset_service.main import DatasetTraceService, DatasetTrace, Status, PipelineStage, MaxExecutionsReachedError

logging.basicConfig(level=logging.INFO)

BUCKET_NAME = os.getenv("BUCKET_NAME", "mobilitydata-gbfs-snapshots-dev")


def fetch_all_gbfs_feeds() -> List[Gbfsfeed]:
    """
    Fetch all GBFS feeds from the database.
    @return: A list of all GBFS feeds.
    """
    session = None
    try:
        session = start_db_session(os.getenv("FEEDS_DATABASE_URL"))
        gbfs_feeds = (
            session.query(Gbfsfeed)
            .options(joinedload(Gbfsfeed.gbfsversions))
            .all()
        )
        return gbfs_feeds
    except Exception as e:
        logging.error(f"Error fetching all GBFS feeds: {e}")
        raise e
    finally:
        if session:
            session.close()


def fetch_gbfs_files(url: str) -> Dict[str, Any]:
    """Fetch the GBFS files from the autodiscovery URL."""
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def upload_gbfs_file_to_bucket(bucket: storage.Bucket, file_url: str, destination_blob_name: str) -> str:
    """Upload a GBFS file to a Cloud Storage bucket."""
    response = requests.get(file_url)
    response.raise_for_status()
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_string(response.content)
    blob.make_public()
    return blob.public_url


def create_gbfs_json_with_bucket_paths(bucket: storage.Bucket, gbfs_data: Dict[str, Any], stable_id: str) -> None:
    """Create a new gbfs.json with paths pointing to Cloud Storage and upload it."""
    new_gbfs_data = gbfs_data.copy()
    today = datetime.now().strftime("%Y-%m-%d")

    for feed_key, feed in new_gbfs_data["data"].items():
        if isinstance(feed["feeds"], dict):
            # Case when 'feeds' is a dictionary keyed by language
            for feed_language, feed_info in feed["feeds"].items():
                old_url = feed_info["url"]
                blob_name = f"{stable_id}/{stable_id}-{today}/{feed_info['name']}_{feed_language}.json"
                new_url = upload_gbfs_file_to_bucket(bucket, old_url, blob_name)
                feed_info["url"] = new_url
        elif isinstance(feed["feeds"], list):
            # Case when 'feeds' is a list without language codes
            for feed_info in feed["feeds"]:
                old_url = feed_info["url"]
                blob_name = f"{stable_id}/{stable_id}-{today}/{feed_info['name']}.json"
                new_url = upload_gbfs_file_to_bucket(bucket, old_url, blob_name)
                feed_info["url"] = new_url
        else:
            logging.warning(f"Unexpected format in feed: {feed_key}")

    # Save the new gbfs.json in the bucket
    new_gbfs_data["last_updated"] = today
    new_gbfs_blob = bucket.blob(f"{stable_id}/{stable_id}-{today}/gbfs.json")
    new_gbfs_blob.upload_from_string(json.dumps(new_gbfs_data), content_type="application/json")
    new_gbfs_blob.make_public()


@functions_framework.cloud_event
def gbfs_validator_pubsub(cloud_event: CloudEvent):
    """
    Main function triggered by a Pub/Sub message to validate a GBFS feed.
    @param cloud_event: The CloudEvent containing the Pub/Sub message.
    """
    Logger.init_logger()
    data = cloud_event.data
    logging.info(f"Function triggered with Pub/Sub event data: {data}")
    try:
        maximum_executions = int(os.getenv("MAXIMUM_EXECUTIONS", 1))
    except ValueError:
        maximum_executions = 1
    logging.info(f"Maximum allowed executions: {maximum_executions}")

    message_json = jsonify_pubsub(data)
    if message_json is None:
        return "Invalid Pub/Sub message data."
    logging.info(f"Parsed message data: {message_json}")
    try:
        execution_id, stable_id, url, latest_version = (
            message_json["execution_id"],
            message_json["stable_id"],
            message_json["url"],
            message_json["latest_version"],
        )
    except KeyError:
        return (
            "Invalid Pub/Sub message data. "
            "Missing required field(s) execution_id, stable_id, url, or latest_version."
        )
    logging.info(f"Execution ID: {execution_id}")
    logging.info(f"Stable ID: {stable_id}")
    logging.info(f"URL: {url}")
    logging.info(f"Latest version: {latest_version}")

    trace_service = DatasetTraceService()
    trace_id = str(uuid.uuid4())
    trace = DatasetTrace(
        trace_id=trace_id,
        stable_id=stable_id,
        execution_id=execution_id,
        status=Status.PROCESSING,
        timestamp=datetime.now(),
        pipeline_stage=PipelineStage.GBFS_VALIDATION,
    )
    try:
        trace_service.validate_and_save(trace, maximum_executions)
    except ValueError as e:
        logging.error(f"Error saving trace: {e}")
        return "Error saving trace."
    except MaxExecutionsReachedError:
        logging.error(f"Maximum executions reached for {stable_id}.")
        return "Maximum executions reached."

    # Step 2: Store all gbfs files and generate new gbfs.json
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        gbfs_data = fetch_gbfs_files(url)
    except Exception as e:
        logging.error(f"Error fetching data from autodiscovery URL: {e}")
        return "Error fetching data from autodiscovery URL."
    try:
        create_gbfs_json_with_bucket_paths(bucket, gbfs_data, stable_id)
    except Exception as e:
        logging.error(f"Error generating new gbfs.json: {e}")
        return "Error generating new gbfs.json."

    # Step 3: Store gbfs snapshot information in the database

    # TODO: 4. Validate the feed's version otherwise add a version to the feed
    # TODO: 5. Validate the feed (summary) and store the results in the database

    return "GBFS files processed and stored successfully.", 200


@functions_framework.http
def gbfs_validator_batch(_):
    """
    HTTP Cloud Function to trigger the GBFS Validator function for multiple datasets.
    @param _: The request object.
    @return: The response of the function.
    """
    Logger.init_logger()
    logging.info("Batch function triggered.")
    pubsub_topic_name = os.getenv("PUBSUB_TOPIC_NAME", None)
    if pubsub_topic_name is None:
        logging.error("PUBSUB_TOPIC_NAME environment variable not set.")
        return "PUBSUB_TOPIC_NAME environment variable not set.", 500

    # Get all GBFS feeds from the database
    try:
        gbfs_feeds = fetch_all_gbfs_feeds()
    except Exception:
        return "Error getting all GBFS feeds.", 500

    feeds_data = []
    execution_id = str(uuid.uuid4())

    for gbfs_feed in gbfs_feeds:
        if len(gbfs_feed.gbfsversions) == 0:
            logging.warning(f"Feed {gbfs_feed.stable_id} has no versions.")
            latest_version = None
        else:
            latest_version = sorted(
                gbfs_feed.gbfsversions, key=lambda v: v.version, reverse=True
            )[0].version
            logging.info(
                f"Latest version for feed {gbfs_feed.stable_id}: {latest_version}"
            )
        feed_data = {
            "execution_id": execution_id,
            "stable_id": gbfs_feed.stable_id,
            "url": gbfs_feed.auto_discovery_url,
            "latest_version": latest_version,
        }
        feeds_data.append(feed_data)
        logging.info(f"Feed {gbfs_feed.stable_id} added to the batch.")

    # Publish to Pub/Sub topic
    try:
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(os.getenv("PROJECT_ID"), pubsub_topic_name)

        for feed_data in feeds_data:
            message_data = json.dumps(feed_data).encode("utf-8")
            future = publisher.publish(topic_path, message_data)
            future.result()  # Ensure message was published
            logging.info(f"Published feed {feed_data['stable_id']} to Pub/Sub.")
    except Exception as e:
        logging.error(f"Error publishing feeds to Pub/Sub: {e}")
        return "Error publishing feeds to Pub/Sub.", 500

    return (
        f"GBFS Validator batch function triggered successfully for {len(feeds_data)} feeds.",
        200,
    )
