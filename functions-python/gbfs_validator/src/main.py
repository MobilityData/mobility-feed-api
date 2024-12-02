import json
import logging
import os
import uuid
from datetime import datetime
from typing import List

import functions_framework
from cloudevents.http import CloudEvent
from google.cloud import pubsub_v1, storage
from sqlalchemy.orm import joinedload, Session
import traceback
from database_gen.sqlacodegen_models import Gbfsfeed
from dataset_service.main import (
    DatasetTraceService,
    DatasetTrace,
    Status,
    PipelineStage,
    MaxExecutionsReachedError,
)
from helpers.database import Database, with_db_session
from helpers.logger import Logger, StableIdFilter
from helpers.parser import jsonify_pubsub
from .gbfs_utils import (
    GBFSValidator,
    fetch_gbfs_files,
    save_trace_with_error,
    save_snapshot_and_report,
)

logging.basicConfig(level=logging.INFO)

BUCKET_NAME = os.getenv("BUCKET_NAME", "mobilitydata-gbfs-snapshots-dev")


@with_db_session
def fetch_all_gbfs_feeds(db_session: "Session") -> List[Gbfsfeed]:
    try:
        gbfs_feeds = (
            db_session.query(Gbfsfeed).options(joinedload(Gbfsfeed.gbfsversions)).all()
        )
        return gbfs_feeds
    except Exception as e:
        logging.error(f"Error fetching all GBFS feeds: {e}")
        raise e


@functions_framework.cloud_event
def gbfs_validator_pubsub(cloud_event: CloudEvent):
    Logger.init_logger()
    data = cloud_event.data
    logging.info(f"Function triggered with Pub/Sub event data: {data}")

    message_json = jsonify_pubsub(data)
    if message_json is None:
        return "Invalid Pub/Sub message data."

    try:
        execution_id = message_json["execution_id"]
        stable_id = message_json["stable_id"]
        url = message_json["url"]
        feed_id = message_json["feed_id"]
    except KeyError as e:
        logging.error(f"Missing required field: {e}")
        return f"Invalid Pub/Sub message data. Missing {e}."

    stable_id_filter = StableIdFilter(stable_id)
    logging.getLogger().addFilter(stable_id_filter)
    try:
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
            trace_service.validate_and_save(
                trace, int(os.getenv("MAXIMUM_EXECUTIONS", 1))
            )
        except (ValueError, MaxExecutionsReachedError) as e:
            error_message = str(e)
            logging.error(error_message)
            save_trace_with_error(trace, error_message, trace_service)
            return error_message

        try:
            storage_client = storage.Client()
            bucket = storage_client.bucket(BUCKET_NAME)
            gbfs_data = fetch_gbfs_files(url)
            validator = GBFSValidator(stable_id)
            validator.create_gbfs_json_with_bucket_paths(bucket, gbfs_data)
        except Exception as e:
            error_message = f"Error processing GBFS files: {e}"
            logging.error(f"{error_message}\nTraceback:\n{traceback.format_exc()}")
            save_trace_with_error(trace, error_message, trace_service)
            return error_message

        try:
            snapshot = validator.create_snapshot(feed_id)
            validation_results = validator.validate_gbfs_feed(bucket)
            db = Database(database_url=os.getenv("FEEDS_DATABASE_URL"))
            with db.start_db_session() as session:
                save_snapshot_and_report(session, snapshot, validation_results)
        except Exception as e:
            error_message = f"Error validating GBFS feed: {e}"
            logging.error(f"{error_message}\nTraceback:\n{traceback.format_exc()}")
            save_trace_with_error(trace, error_message, trace_service)
            return error_message

        trace.status = Status.SUCCESS
        trace_service.save(trace)
        return "GBFS files processed and stored successfully."
    finally:
        logging.getLogger().removeFilter(stable_id_filter)


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
            "feed_id": gbfs_feed.id,
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
