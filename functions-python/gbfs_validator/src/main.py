import json
import logging
import os
import traceback
import uuid
from datetime import datetime
from typing import List

import functions_framework
from cloudevents.http import CloudEvent
from google.cloud import pubsub_v1
from sqlalchemy.orm import Session

from gbfs_data_processor import GBFSDataProcessor
from gbfs_utils import (
    save_trace_with_error,
)
from shared.database_gen.sqlacodegen_models import Gbfsfeed
from shared.dataset_service.main import (
    DatasetTraceService,
    DatasetTrace,
    Status,
    PipelineStage,
    MaxExecutionsReachedError,
)
from shared.database.database import with_db_session
from shared.helpers.logger import init_logger, get_logger
from shared.helpers.parser import jsonify_pubsub

init_logger()


def fetch_all_gbfs_feeds(db_session: Session) -> List[Gbfsfeed]:
    try:
        gbfs_feeds = (
            db_session.query(Gbfsfeed).filter(Gbfsfeed.status != "deprecated").all()
        )
        db_session.expunge_all()
        return gbfs_feeds
    except Exception as e:
        logging.error("Error fetching all GBFS feeds: %s", e)
        raise e


@functions_framework.cloud_event
def gbfs_validator_pubsub(cloud_event: CloudEvent):
    data = cloud_event.data
    logging.info("Function triggered with Pub/Sub event data: %s", data)

    # Get the pubsub message data
    message_json = jsonify_pubsub(data)
    if message_json is None:
        return "Invalid Pub/Sub message data."

    try:
        execution_id = message_json["execution_id"]
        stable_id = message_json["stable_id"]
        url = message_json["url"]
        feed_id = message_json["feed_id"]
    except KeyError as e:
        logging.error("Missing required field: %s", e)
        return f"Invalid Pub/Sub message data. Missing {e}."

    # get logger with stable_id
    logger = get_logger(__name__, stable_id)
    # Save trace and validate if the execution is allowed
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
        trace_service.validate_and_save(trace, int(os.getenv("MAXIMUM_EXECUTIONS", 1)))
    except (ValueError, MaxExecutionsReachedError) as e:
        error_message = str(e)
        logger.error(error_message)
        save_trace_with_error(trace, error_message, trace_service)
        return error_message

    # Process GBFS data
    try:
        processor = GBFSDataProcessor(stable_id, feed_id)
        processor.process_gbfs_data(url)
    except Exception as e:
        error_message = f"Error processing GBFS data: {e}"
        logger.error(error_message)
        logger.error("Traceback: %s", traceback.format_exc())
        save_trace_with_error(trace, error_message, trace_service)
        return error_message

    trace.status = Status.SUCCESS
    trace_service.save(trace)
    return "GBFS data processed and stored successfully."


@with_db_session
@functions_framework.http
def gbfs_validator_batch(_, db_session: Session):
    """
    HTTP Cloud Function to trigger the GBFS Validator function for multiple datasets.
    @param _: The request object.
    @return: The response of the function.
    """
    logging.info("Batch function triggered.")
    pubsub_topic_name = os.getenv("PUBSUB_TOPIC_NAME", None)
    if pubsub_topic_name is None:
        logging.error("PUBSUB_TOPIC_NAME environment variable not set.")
        return "PUBSUB_TOPIC_NAME environment variable not set.", 500

    # Get all GBFS feeds from the database
    try:
        gbfs_feeds = fetch_all_gbfs_feeds(db_session)
    except Exception:
        return "Error getting all GBFS feeds.", 500

    feeds_data = []
    execution_id = str(uuid.uuid4())

    for gbfs_feed in gbfs_feeds:
        feed_data = {
            "execution_id": execution_id,
            "stable_id": gbfs_feed.stable_id,
            "feed_id": gbfs_feed.id,
            "url": gbfs_feed.auto_discovery_url,
        }
        feeds_data.append(feed_data)
        logging.info("Feed %s added to the batch.", gbfs_feed.stable_id)

    # Publish to Pub/Sub topic
    try:
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(os.getenv("PROJECT_ID"), pubsub_topic_name)

        for feed_data in feeds_data:
            message_data = json.dumps(feed_data).encode("utf-8")
            future = publisher.publish(topic_path, message_data)
            future.result()  # Ensure message was published
            logging.info("Published feed %s to Pub/Sub.", feed_data["stable_id"])
    except Exception as e:
        logging.error("Error publishing feeds to Pub/Sub: %s", e)
        return "Error publishing feeds to Pub/Sub.", 500

    return (
        f"GBFS Validator batch function triggered successfully for {len(feeds_data)} feeds.",
        200,
    )
