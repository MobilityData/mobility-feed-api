import base64
import json
import logging
import os
import uuid
from datetime import datetime

import functions_framework
from cloudevents.http import CloudEvent
from google.cloud import pubsub_v1
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from shared.database_gen.sqlacodegen_models import Gtfsdataset
from shared.dataset_service.main import (
    DatasetTraceService,
    DatasetTrace,
    Status,
    PipelineStage,
    MaxExecutionsReachedError,
)
from shared.helpers.database import Database
from shared.helpers.logger import Logger
from shared.helpers.parser import jsonify_pubsub
from bounding_box.bounding_box_extractor import (
    create_polygon_wkt_element,
    update_dataset_bounding_box,
)
from reverse_geolocation.location_extractor import update_location, reverse_coords
from stops_utils import get_gtfs_feed_bounds_and_points

logging.basicConfig(level=logging.INFO)


def parse_resource_data(data: dict) -> tuple:
    """
    Parse the cloud event data to extract resource information.
    @:param data (dict): The data part of the CloudEvent.
    @:return tuple: A tuple containing stable_id, dataset_id, and the resource URL.
    """
    resource_name = data["protoPayload"]["resourceName"]
    stable_id = resource_name.split("/")[-3]
    dataset_id = resource_name.split("/")[-2]
    file_name = resource_name.split("/")[-1]
    bucket_name = data["resource"]["labels"]["bucket_name"]
    url = f"https://storage.googleapis.com/{bucket_name}/{stable_id}/{dataset_id}/{file_name}"
    return stable_id, dataset_id, url


@functions_framework.cloud_event
def extract_location_pubsub(cloud_event: CloudEvent):
    """
    Main function triggered by a Pub/Sub message to extract and update the location information in the database.
    @param cloud_event: The CloudEvent containing the Pub/Sub message.
    """
    Logger.init_logger()
    try:
        maximum_executions = int(os.getenv("MAXIMUM_EXECUTIONS", 1))
    except ValueError:
        maximum_executions = 1
    data = cloud_event.data
    location_extraction_n_points = os.getenv("LOCATION_EXTRACTION_N_POINTS", 5)
    logging.info(f"Function triggered with Pub/Sub event data: {data}")

    # Extract the Pub/Sub message data
    message_json = jsonify_pubsub(data)
    if message_json is None:
        return "Invalid Pub/Sub message data."

    logging.info(f"Parsed message data: {message_json}")

    if (
        message_json is None
        or "stable_id" not in message_json
        or "dataset_id" not in message_json
        or "url" not in message_json
    ):
        logging.error("Invalid message data.")
        return "Invalid message data. Expected 'stable_id', 'dataset_id', and 'url' in the message."

    stable_id = message_json["stable_id"]
    dataset_id = message_json["dataset_id"]
    url = message_json["url"]
    execution_id = message_json.get("execution_id", None)
    if execution_id is None:
        logging.warning(f"[{dataset_id}] No execution ID found in message")
        execution_id = str(uuid.uuid4())
        logging.info(f"[{dataset_id}] Generated execution ID: {execution_id}")
    trace_service = DatasetTraceService()
    trace_id = str(uuid.uuid4())
    error = None
    # Saving trace before starting in case we run into memory problems or uncatchable errors
    trace = DatasetTrace(
        trace_id=trace_id,
        stable_id=stable_id,
        execution_id=execution_id,
        status=Status.PROCESSING,
        timestamp=datetime.now(),
        hosted_url=url,
        dataset_id=dataset_id,
        pipeline_stage=PipelineStage.LOCATION_EXTRACTION,
    )
    try:
        trace_service.validate_and_save(trace, maximum_executions)
    except ValueError as e:
        logging.error(f"[{dataset_id}] Error while saving trace: {e}")
        return f"Error while saving trace: {e}"
    except MaxExecutionsReachedError as e:
        logging.warning(f"[{dataset_id}] {e}")
        return f"{e}"
    try:
        logging.info(f"[{dataset_id}] accessing url: {url}")
        try:
            bounds, location_geo_points = get_gtfs_feed_bounds_and_points(
                url, dataset_id, location_extraction_n_points
            )
        except Exception as e:
            error = f"Error processing GTFS feed: {e}"
            raise e
        logging.info(f"[{dataset_id}] extracted bounding box = {bounds}")

        geometry_polygon = create_polygon_wkt_element(bounds)

        db = Database(database_url=os.getenv("FEEDS_DATABASE_URL"))
        try:
            with db.start_db_session() as session:
                update_dataset_bounding_box(session, dataset_id, geometry_polygon)
                update_location(
                    reverse_coords(location_geo_points), dataset_id, session
                )
        except Exception as e:
            error = f"Error updating location information in database: {e}"
            logging.error(f"[{dataset_id}] Error while processing: {e}")
            raise e
        logging.info(
            f"[{stable_id} - {dataset_id}] Location information updated successfully."
        )
    except Exception:
        pass
    finally:
        trace.status = Status.FAILED if error is not None else Status.SUCCESS
        trace.error_message = error
        trace_service.save(trace)


@functions_framework.cloud_event
def extract_location(cloud_event: CloudEvent):
    """
    Wrapper function to extract necessary data from the CloudEvent and call the core function.
    @param cloud_event: The CloudEvent containing the Pub/Sub message.
    """
    Logger.init_logger()
    data = cloud_event.data
    logging.info(f"Function Triggered with event data: {data}")

    try:
        stable_id, dataset_id, url = parse_resource_data(data)
    except KeyError as e:
        logging.error(f"Missing key in event data: {e}")
        return "Invalid event data.", 400
    except Exception as e:
        logging.error(f"Error parsing resource data: {e}")
        return "Error processing event data.", 500

    # Construct a CloudEvent-like dictionary with the necessary information
    new_cloud_event_data = {
        "message": {
            "data": base64.b64encode(
                json.dumps(
                    {"stable_id": stable_id, "dataset_id": dataset_id, "url": url}
                ).encode("utf-8")
            ).decode("utf-8")
        }
    }
    attributes = {
        "type": None,
        "source": None,
    }

    # Create a new CloudEvent object to pass to the PubSub function
    new_cloud_event = CloudEvent(attributes=attributes, data=new_cloud_event_data)

    # Call the pubsub function with the constructed CloudEvent
    return extract_location_pubsub(new_cloud_event)


@functions_framework.http
def extract_location_batch(_):
    Logger.init_logger()
    logging.info("Batch function triggered.")

    pubsub_topic_name = os.getenv("PUBSUB_TOPIC_NAME", None)
    force_datasets_update = bool(os.getenv("FORCE_DATASETS_UPDATE", False))
    if pubsub_topic_name is None:
        logging.error("PUBSUB_TOPIC_NAME environment variable not set.")
        return "PUBSUB_TOPIC_NAME environment variable not set.", 500

    # Get latest GTFS dataset with no bounding boxes
    db = Database(database_url=os.getenv("FEEDS_DATABASE_URL"))
    execution_id = str(uuid.uuid4())
    datasets_data = []

    try:
        with db.start_db_session() as session:
            # Select all latest datasets with no bounding boxes or all datasets if forced
            datasets = (
                session.query(Gtfsdataset)
                .filter(
                    or_(
                        force_datasets_update,
                        Gtfsdataset.bounding_box == None,  # noqa: E711
                    )
                )
                .filter(Gtfsdataset.latest)
                .options(joinedload(Gtfsdataset.feed))
                .all()
            )
            for dataset in datasets:
                data = {
                    "stable_id": dataset.feed.stable_id,
                    "dataset_id": dataset.stable_id,
                    "url": dataset.hosted_url,
                    "execution_id": execution_id,
                }
                datasets_data.append(data)
                logging.info(f"Dataset {dataset.stable_id} added to the batch.")

    except Exception as e:
        logging.error(f"Error while fetching datasets: {e}")
        return "Error while fetching datasets.", 500
    finally:
        pass

    # Trigger update location for each dataset by publishing to Pub/Sub
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(os.getenv("PROJECT_ID"), pubsub_topic_name)
    for data in datasets_data:
        message_data = json.dumps(data).encode("utf-8")
        future = publisher.publish(topic_path, message_data)
        logging.info(f"Published message to Pub/Sub with ID: {future.result()}")

    return f"Batch function triggered for {len(datasets_data)} datasets.", 200
