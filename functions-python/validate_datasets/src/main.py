import logging

import functions_framework
from cloudevents.http import CloudEvent

from helpers.logger import Logger

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
def validate_dataset(cloud_event: CloudEvent) -> None:
    """
    Main function triggered by a GTFS dataset upload to run the validation process.
    @:param cloud_event (CloudEvent): The CloudEvent that triggered this function.
    """
    Logger.init_logger()
    data = cloud_event.data
    logging.info(f"Function Triggered with event data: {data}")

    stable_id, dataset_id, url = parse_resource_data(data)
    logging.info(f"[{dataset_id}] accessing url: {url}")

    # TODO run validation process
    logging.info(f"[{stable_id} - {dataset_id}] Validation process completed.")
