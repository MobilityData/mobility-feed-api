import json
import logging
import os
from typing import Tuple

import gtfs_kit
from cloudevents.http import CloudEvent
from google.cloud import storage
from google.cloud import tasks_v2

from location_group_utils import create_http_task, project_id, gcp_region
from shared.helpers.logger import Logger
from shared.helpers.parser import jsonify_pubsub


def init(request: CloudEvent) -> None:
    """
    Initializer function.
    """
    Logger.init_logger()
    logging.info("Processing reverse geolocation request.")
    logging.info("Request: %s", request)


def parse_resource_data(data: dict) -> Tuple[str, str, str]:
    """
    Parse the cloud event data to extract resource information.
    @:returns tuple: A tuple containing stable_id, dataset_id, and the resource URL.
    """
    resource_name = data["protoPayload"]["resourceName"]
    stable_id = resource_name.split("/")[-3]
    dataset_id = resource_name.split("/")[-2]
    file_name = resource_name.split("/")[-1]
    bucket_name = data["resource"]["labels"]["bucket_name"]
    url = f"https://storage.googleapis.com/{bucket_name}/{stable_id}/{dataset_id}/{file_name}"
    return stable_id, dataset_id, url


def reverse_geolocation_pubsub(request: CloudEvent) -> None:
    """
    Reverse geolocation function triggered by a Pub/Sub message.
    """
    try:
        init(request)
        message_json = jsonify_pubsub(request.data)
        if message_json is None:
            logging.error("Invalid Pub/Sub message.")
            return
        if (
            "stable_id" not in message_json
            or "dataset_id" not in message_json
            or "url" not in message_json
        ):
            logging.error("Invalid message data.")
            return
        stable_id = message_json["stable_id"]
        dataset_id = message_json["dataset_id"]
        url = message_json["url"]
        reverse_geolocation(stable_id, dataset_id, url)
    except Exception as e:
        logging.error(f"Execution error: {e}")


def reverse_geolocation_storage_trigger(request: CloudEvent) -> None:
    """
    Reverse geolocation function triggered by a storage trigger.
    """
    try:
        init(request)
        stable_id, dataset_id, url = parse_resource_data(request.data)
        reverse_geolocation(stable_id, dataset_id, url)
    except Exception as e:
        logging.error(f"Execution error: {e}")


def reverse_geolocation(stable_id: str, dataset_id: str, url: str) -> None:
    """
    Reverse geolocation function to create tasks for the reverse geolocation process.
    """
    try:
        logging.info(
            f"Stable ID: {stable_id} - Dataset Stable ID: {dataset_id} - URL: {url}"
        )

        # TODO: This logic should be moved to a separate service
        feed = gtfs_kit.read_feed(url, "km")
        feed.stops.to_csv("stops.txt", index=False)
        storage_client = storage.Client()
        bucket = storage_client.bucket(os.getenv("DATASETS_BUCKET_NAME"))
        blob = bucket.blob(f"{stable_id}/{dataset_id}/stops.txt")
        blob.upload_from_filename("stops.txt")
        blob.make_public()
        logging.info(f"Uploaded stops.txt to {blob.public_url}")

        create_http_processor_task(stable_id, dataset_id, blob.public_url)
        logging.info(f"Reverse geolocation task created for feed {stable_id}.")
    except Exception as e:
        logging.error(f"Error creating task: {e}")


def create_http_processor_task(
    stable_id: str,
    dataset_id: str,
    stops_url: str,
) -> None:
    """
    Create a task to process a group of points.
    """
    client = tasks_v2.CloudTasksClient()
    body = json.dumps(
        {"stable_id": stable_id, "stops_url": stops_url, "dataset_id": dataset_id}
    ).encode()
    create_http_task(
        client,
        body,
        f"https://{gcp_region}-{project_id}.cloudfunctions.net/reverse-geolocation-processor",
    )
