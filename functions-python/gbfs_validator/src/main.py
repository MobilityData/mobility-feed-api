import logging
import os
import uuid

import functions_framework
from cloudevents.http import CloudEvent
from google.cloud import pubsub_v1
from sqlalchemy.orm import joinedload

from database_gen.sqlacodegen_models import Gbfsfeed
from helpers.database import start_db_session
from helpers.logger import Logger
from helpers.parser import jsonify_pubsub

logging.basicConfig(level=logging.INFO)


def get_all_gbfs_feeds():
    """
    Get all GBFS feeds from the database.
    @return: A list of all GBFS feeds.
    """
    session = None
    try:
        session = start_db_session(os.getenv("FEEDS_DATABASE_URL"))
        gbfs_feeds = (
            session.query(Gbfsfeed).options(joinedload(Gbfsfeed.gbfsversions)).all()
        )
        return gbfs_feeds
    except Exception as e:
        logging.error(f"Error getting all GBFS feeds: {e}")
        raise e
    finally:
        if session:
            session.close()


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

    message_json = jsonify_pubsub(cloud_event)
    if message_json is None:
        return "Invalid Pub/Sub message data."
    logging.info(f"Parsed message data: {message_json}")

    # TODO: 1. Parse the CloudEvent data to extract the feed information
    # TODO: 2. Store all gbfs file and generate new gbfs.json and store it as well
    # TODO: 2.5. Store gbfs snapshot information in the database
    # TODO: 3. Validate the feed's version otherwise add a version to the feed
    # TODO: 4. Validate the feed (summary) and store the results in the database
    return


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
        gbfs_feeds = get_all_gbfs_feeds()
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
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(os.getenv("PROJECT_ID"), pubsub_topic_name)

    for feed_data in feeds_data:
        future = publisher.publish(topic_path, data=b"", **feed_data)
        future.result()  # Ensure message was published
        logging.info(f"Published feed {feed_data['stable_id']} to Pub/Sub.")

    return (
        f"GBFS Validator batch function triggered successfully for {len(feeds_data)} feeds.",
        200,
    )
