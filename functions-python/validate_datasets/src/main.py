import logging
import requests
import functions_framework
from cloudevents.http import CloudEvent

from helpers.logger import Logger
from requests_toolbelt.multipart.encoder import MultipartEncoder


logging.basicConfig(level=logging.INFO)


def create_job(url: str, country_code: str) -> dict:
    """
    Calls the 'createJob' API endpoint to initiate a validation job with the provided URL and country code.

    Args:
        url (str): The URL of the GTFS ZIP file to be validated.
        country_code (str): The country code associated with the GTFS dataset.

    Returns:
        dict: A dictionary containing the response from the 'createJob' endpoint.
    """
    endpoint = "https://gtfs-validator-results.mobilitydata.org/create-job"
    multipart_data = MultipartEncoder(
        fields={
            'url': url,
            'countryCode': country_code
        }
    )

    headers = {
        "Content-Type": multipart_data.content_type,
    }

    response = requests.post(endpoint, headers=headers, data=multipart_data)

    if response.status_code == 200:
        return response.json()
    else:
        logging.error(
            f"Failed to create job. Status code: {response.status_code}, Response: {response.text}"
        )
        return {}


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

    job_info = create_job(url, "CA")
    if job_info:
        logging.info(f"Job created successfully: {job_info}")
    #     TODO: wait for file creation
    else:
        logging.error("Failed to create job or process response.")
    logging.info(f"[{stable_id} - {dataset_id}] Validation process completed.")
