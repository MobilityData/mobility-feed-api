import hashlib
import json
import logging
import os
import uuid

import gtfs_kit
import pandas as pd
from cloudevents.http import CloudEvent
from google.cloud import tasks_v2

from helpers.logger import Logger

# Initialize logging
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

def create_http_task(
        url: str,
        payload: dict,
        service_account_email: str,
        project: str,
        location: str,
        queue: str
):
    """
    Create an HTTP task in Cloud Tasks.
    @param url (str): The URL of the task.
    @param payload (dict): The payload to send in the task.
    @param endpoint (str): The endpoint to send the task to.
    """
    client = tasks_v2.CloudTasksClient()
    task = tasks_v2.Task(
        http_request=tasks_v2.HttpRequest(
            http_method=tasks_v2.HttpMethod.POST,
            url=url,
            headers={"Content-type": "application/json"},
            oidc_token=tasks_v2.OidcToken(
                service_account_email=service_account_email,
                audience=url,
            ),
            body=json.dumps(payload).encode(),
        )
    )
    return client.create_task(
        tasks_v2.CreateTaskRequest(
            parent=client.queue_path(project, location, queue),
            task=task,
        )
    )


def reverse_geolocation(cloud_event: CloudEvent):
    """Function that is triggered when a new dataset is uploaded to extract the location information."""
    Logger.init_logger()
    logging.info(f"Cloud event data: {cloud_event.data}")
    processing_function_endpoint = os.getenv("PROCESSING_FUNCTION_ENDPOINT")
    aggregator_function_endpoint = os.getenv("AGGREGATOR_FUNCTION_ENDPOINT")
    service_account_email = os.getenv("SERVICE_ACCOUNT_EMAIL")
    project_id = os.getenv("PROJECT_ID")
    location = os.getenv("LOCATION")
    processing_queue = os.getenv("PROCESSING_QUEUE")
    aggregator_queue = os.getenv("AGGREGATOR_QUEUE")

    try:
        stable_id, dataset_id, url = parse_resource_data(cloud_event.data)
        logging.info(
            f"Processing dataset {dataset_id} and stable ID {stable_id} from {url}"
        )
    except KeyError as e:
        logging.error(f"Error parsing resource data: {e}")
        return "Invalid Pub/Sub message data."

    try:
        gtfs_feed = gtfs_kit.read_feed(url, dist_units="km")
        stops = gtfs_feed.stops[["stop_lon", "stop_lat"]].copy()
        stops = stops.sort_values(by=["stop_lon", "stop_lat"])
        stops_hash = hashlib.sha256(
            pd.util.hash_pandas_object(stops, index=True).values
        ).hexdigest()
        # TODO: Check if stops hash has changed
        logging.info(f"Stops hash: {stops_hash}")
    except Exception as e:
        logging.error(f"Error processing GTFS feed from {url}: {e}")
        return "Error processing GTFS feed."

    # 9 - Create one GCP task per batch of 1000 remaining stops to extract the location
    execution_id = str(uuid.uuid4())
    logging.info(f"Execution ID: {execution_id}")
    # process batches of 1000 stops
    # TODO fix logic in case of less than 1000 stops
    batch_size = 1000
    n_batches = (len(stops) + batch_size - 1) // batch_size  # Calculate total number of batches
    logging.info(f"Number of batches: {n_batches}")

    for i in range(n_batches):
        batch_stops = stops.iloc[i * batch_size: (i + 1) * batch_size]
        stops_list = [[stop['stop_lon'], stop['stop_lat']] for stop in batch_stops.to_dict(orient="records")]
        payload = {
            "execution_id": execution_id,
            "points": stops_list,
        }
        logging.info(f"Processing batch {i + 1} with {len(stops_list)} stops.")
        logging.info(f"Payload: {payload}")
        response = create_http_task(
            url=processing_function_endpoint,
            payload=payload,
            service_account_email=service_account_email,
            project=project_id,
            location=location,
            queue=processing_queue
        )
        logging.info(f"Task created for batch {i + 1}: {response.name}")

    # 10 - Crete a GCP task to aggregate the results
    create_http_task(
        url=aggregator_function_endpoint,
        payload={
            "execution_id": execution_id,
            "n_batches": n_batches,
            "stable_id": stable_id,
        },
        service_account_email=service_account_email,
        project=project_id,
        location=location,
        queue=aggregator_queue
    )
    # 11 - Save Execution trace in the database
    return "Success"
