import base64
import json
import logging
import os
import uuid
from datetime import datetime

import functions_framework
import gtfs_kit
import numpy
from cloudevents.http import CloudEvent
from geoalchemy2 import WKTElement
from google.cloud import pubsub_v1

from database_gen.sqlacodegen_models import Gtfsdataset
from helpers.database import start_db_session
from helpers.logger import Logger
from dataset_service.main import (
    DatasetTraceService,
    DatasetTrace,
    Status,
    PipelineStage,
)

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


def get_gtfs_feed_bounds(url: str, dataset_id: str) -> numpy.ndarray:
    """
    Retrieve the bounding box coordinates from the GTFS feed.
    @:param url (str): URL to the GTFS feed.
    @:param dataset_id (str): ID of the dataset for logs
    @:return numpy.ndarray: An array containing the bounds (min_longitude, min_latitude, max_longitude, max_latitude).
    @:raises Exception: If the GTFS feed is invalid
    """
    try:
        feed = gtfs_kit.read_feed(url, "km")
        return feed.compute_bounds()
    except Exception as e:
        logging.error(f"[{dataset_id}] Error retrieving GTFS feed from {url}: {e}")
        raise Exception(e)


def create_polygon_wkt_element(bounds: numpy.ndarray) -> WKTElement:
    """
    Create a WKTElement polygon from bounding box coordinates.
    @:param bounds (numpy.ndarray): Bounding box coordinates.
    @:return WKTElement: The polygon representation of the bounding box.
    """
    min_longitude, min_latitude, max_longitude, max_latitude = bounds
    points = [
        (min_longitude, min_latitude),
        (min_longitude, max_latitude),
        (max_longitude, max_latitude),
        (max_longitude, min_latitude),
        (min_longitude, min_latitude),
    ]
    wkt_polygon = f"POLYGON(({', '.join(f'{lon} {lat}' for lon, lat in points)}))"
    return WKTElement(wkt_polygon, srid=4326)


def update_dataset_bounding_box(session, dataset_id, geometry_polygon):
    """
    Update the bounding box of a dataset in the database.
    @:param session (Session): The database session.
    @:param dataset_id (str): The ID of the dataset.
    @:param geometry_polygon (WKTElement): The polygon representing the bounding box.
    @:raises Exception: If the dataset is not found in the database.
    """
    dataset: Gtfsdataset | None = (
        session.query(Gtfsdataset)
        .filter(Gtfsdataset.stable_id == dataset_id)
        .one_or_none()
    )
    if dataset is None:
        raise Exception(f"Dataset {dataset_id} does not exist in the database.")
    dataset.bounding_box = geometry_polygon
    session.add(dataset)
    session.commit()


@functions_framework.cloud_event
def extract_bounding_box_pubsub(cloud_event: CloudEvent):
    """
    Main function triggered by a Pub/Sub message to extract and update the bounding box in the database.
    @param cloud_event: The CloudEvent containing the Pub/Sub message.
    """
    Logger.init_logger()
    try:
        maximum_executions = int(os.getenv("MAXIMUM_EXECUTIONS", 1))
    except ValueError:
        maximum_executions = 1
    data = cloud_event.data
    logging.info(f"Function triggered with Pub/Sub event data: {data}")

    # Extract the Pub/Sub message data
    try:
        message_data = data["message"]["data"]
        message_json = json.loads(base64.b64decode(message_data).decode("utf-8"))
    except Exception as e:
        logging.error(f"Error parsing message data: {e}")
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
    trace = trace_service.get_by_execution_and_stable_ids(execution_id, stable_id)
    logging.info(f"[{dataset_id}] Trace: {trace}")
    executions = len(trace) if trace else 0
    print(f"[{dataset_id}] Executions: {executions}")
    print(trace_service.get_by_execution_and_stable_ids(execution_id, stable_id))
    logging.info(f"[{dataset_id}] Executions: {executions}")
    if executions > 0 and executions >= maximum_executions:
        logging.warning(
            f"[{dataset_id}] Maximum executions reached. Skipping processing."
        )
        return f"Maximum executions reached for {dataset_id}."
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
    trace_service.save(trace)
    try:
        logging.info(f"[{dataset_id}] accessing url: {url}")
        try:
            bounds = get_gtfs_feed_bounds(url, dataset_id)
        except Exception as e:
            error = f"Error processing GTFS feed: {e}"
            raise e
        logging.info(f"[{dataset_id}] extracted bounding box = {bounds}")

        geometry_polygon = create_polygon_wkt_element(bounds)

        session = None
        try:
            session = start_db_session(os.getenv("FEEDS_DATABASE_URL"))
            update_dataset_bounding_box(session, dataset_id, geometry_polygon)
        except Exception as e:
            error = f"Error updating bounding box in database: {e}"
            logging.error(f"[{dataset_id}] Error while processing: {e}")
            if session is not None:
                session.rollback()
            raise e
        finally:
            if session is not None:
                session.close()
        logging.info(f"[{stable_id} - {dataset_id}] Bounding box updated successfully.")
    except Exception:
        pass
    finally:
        trace.status = Status.FAILED if error is not None else Status.SUCCESS
        trace.error_message = error
        trace_service.save(trace)


@functions_framework.cloud_event
def extract_bounding_box(cloud_event: CloudEvent):
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
    return extract_bounding_box_pubsub(new_cloud_event)


@functions_framework.http
def extract_bounding_box_batch(_):
    Logger.init_logger()
    logging.info("Batch function triggered.")

    pubsub_topic_name = os.getenv("PUBSUB_TOPIC_NAME", None)
    if pubsub_topic_name is None:
        logging.error("PUBSUB_TOPIC_NAME environment variable not set.")
        return "PUBSUB_TOPIC_NAME environment variable not set.", 500

    # Get latest GTFS dataset with no bounding boxes
    session = None
    datasets_data = []
    try:
        session = start_db_session(os.getenv("FEEDS_DATABASE_URL"))
        datasets = (
            session.query(Gtfsdataset)
            .filter(Gtfsdataset.bounding_box == None)  # noqa: E711
            .filter(Gtfsdataset.latest)
            .all()
        )
        for dataset in datasets:
            data = {
                "stable_id": dataset.feed_id,
                "dataset_id": dataset.stable_id,
                "url": dataset.hosted_url,
            }
            datasets_data.append(data)
            logging.info(f"Dataset {dataset.stable_id} added to the batch.")

    except Exception as e:
        logging.error(f"Error while fetching datasets: {e}")
        return "Error while fetching datasets.", 500
    finally:
        if session is not None:
            session.close()

    # Trigger update bounding box for each dataset by publishing to Pub/Sub
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(os.getenv("PROJECT_ID"), pubsub_topic_name)
    for data in datasets_data:
        message_data = json.dumps(data).encode("utf-8")
        future = publisher.publish(topic_path, message_data)
        logging.info(f"Published message to Pub/Sub with ID: {future.result()}")

    return f"Batch function triggered for {len(datasets_data)} datasets.", 200
