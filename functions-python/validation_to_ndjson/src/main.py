import logging

import flask
import functions_framework
from cloudevents.http import CloudEvent

from shared.helpers.logger import init_logger
from google.cloud import storage
from validation_report_converter import (
    ValidationReportConverter,
    project_id,
    bucket_name,
)


init_logger()


def parse_resource_data(data: dict) -> tuple:
    """
    Parse the cloud event data to extract resource information.
    @param data: The data part of the CloudEvent.
    @return tuple: A tuple containing the stable_id, dataset_id, report_id, and url.
    """
    logging.info("Parsing resource data {}".format(data))
    resource_name = data["protoPayload"]["resourceName"]
    stable_id = resource_name.split("/")[-3]
    dataset_id = resource_name.split("/")[-2]
    file_name = resource_name.split("/")[-1]
    report_id = ".".join(file_name.split(".")[:-1])
    bucket_name = data["resource"]["labels"]["bucket_name"]
    url = f"https://storage.googleapis.com/{bucket_name}/{stable_id}/{dataset_id}/{file_name}"
    return stable_id, dataset_id, report_id, url


@functions_framework.cloud_event
def convert_reports_to_ndjson(cloud_event: CloudEvent):
    """
    Convert a validation report to NDJSON format.
    @param cloud_event: The CloudEvent object.
    """
    logging.info("Function triggered")
    stable_id, dataset_id, report_id, url = parse_resource_data(cloud_event.data)
    logging.info(
        "Stable ID: %s, Dataset ID: %s, URL: %s, Report ID: %s",
        stable_id,
        dataset_id,
        url,
        report_id,
    )
    converter_type = ValidationReportConverter.get_converter()
    converter_type(stable_id, dataset_id, report_id, url).process()
    return stable_id, dataset_id, url


@functions_framework.http
def batch_convert_reports_to_ndjson(request: flask.Request):
    """Batch convert all reports in the bucket to NDJSON format."""
    logging.info("Function triggered")

    # 1. Get the validator version from the request
    try:
        request_json = request.get_json(silent=True)
        validator_version = request_json.get("validator_version", "")
        report_suffix = f"{validator_version}.json"
    except Exception as e:
        logging.error("Failed to get validator version: %s", e)
        report_suffix = ".json"

    # 2. Get all reports in the bucket
    storage_client = storage.Client(project_id)
    blobs = list(storage_client.list_blobs(bucket_name))
    report_blobs = [
        blob
        for blob in blobs
        if "report_" in blob.name and blob.name.endswith(report_suffix)
    ]
    logging.info("Found %s reports to process.", len(report_blobs))

    # 3. For each report create cloud event and call convert_reports_to_ndjson
    for blob in report_blobs:
        cloud_event = CloudEvent(
            data={
                "protoPayload": {
                    "resourceName": blob.name,
                },
                "resource": {"labels": {"bucket_name": bucket_name}},
            },
            attributes={
                "source": "batch_convert_reports_to_ndjson",
                "type": "batch_convert_reports_to_ndjson",
            },
        )
        convert_reports_to_ndjson(cloud_event)
    return "Success converting reports to NDJSON"
