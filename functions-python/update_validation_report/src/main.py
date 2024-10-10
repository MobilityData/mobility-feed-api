#
#   MobilityData 2024
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import logging
import os
from time import sleep
from typing import List

import flask
import functions_framework
import requests
import sqlalchemy.orm
import json
from sqlalchemy import or_
from google.cloud import storage
from sqlalchemy.engine import Row
from sqlalchemy.engine.interfaces import Any

from database_gen.sqlacodegen_models import Gtfsdataset, Gtfsfeed, Validationreport
from helpers.database import start_db_session
from google.cloud import workflows_v1
from google.cloud.workflows import executions_v1
from google.cloud.workflows.executions_v1 import Execution

from helpers.logger import Logger

logging.basicConfig(level=logging.INFO)
env = os.getenv("ENV", "dev").lower()
bucket_name = f"mobilitydata-datasets-{env}"


@functions_framework.http
def update_validation_report(request: flask.Request):
    """
    Update the validation report for the datasets that need it
    """
    Logger.init_logger()

    request_json = request.get_json()
    validator_endpoint = request_json.get(
        "validator_endpoint", os.getenv("WEB_VALIDATOR_URL")
    )
    bypass_db_update = validator_endpoint != os.getenv("WEB_VALIDATOR_URL")
    force_update = request_json.get("force_update", False)

    # Check if the environment parameter is valid and set the reports bucket name
    env_param = request_json.get("env", None)
    reports_bucket_name = None
    if env_param:
        if env_param.lower() not in ["staging", "prod"]:
            return {
                "message": "Invalid environment parameter. Allowed values: staging, prod"
            }, 400
        if env_param.lower() == "prod":
            reports_bucket_name = "gtfs-validator-results"
        else:
            reports_bucket_name = "stg-gtfs-validator-results"

    # Get validator version
    validator_version = get_validator_version(validator_endpoint)
    logging.info(f"Accessing bucket {bucket_name}")

    session = start_db_session(os.getenv("FEEDS_DATABASE_URL"), echo=False)
    latest_datasets = get_latest_datasets_without_validation_reports(
        session, validator_version, force_update
    )
    logging.info(f"Retrieved {len(latest_datasets)} latest datasets.")

    valid_latest_datasets = get_datasets_for_validation(latest_datasets)
    logging.info(f"Retrieved {len(latest_datasets)} blobs to update.")

    execution_triggered_datasets = execute_workflows(
        valid_latest_datasets, validator_endpoint, bypass_db_update, reports_bucket_name
    )
    response = {
        "message": f"Validation report update needed for {len(valid_latest_datasets)} datasets and triggered for "
        f"{len(execution_triggered_datasets)} datasets.",
        "dataset_workflow_triggered": sorted(execution_triggered_datasets),
        "datasets_not_updated": sorted(
            [
                dataset_id
                for _, dataset_id in valid_latest_datasets
                if dataset_id not in execution_triggered_datasets
            ]
        ),
        "ignored_datasets": sorted(
            [
                dataset_id
                for _, dataset_id in latest_datasets
                if dataset_id not in valid_latest_datasets
            ]
        ),
    }
    return response, 200


def get_validator_version(validator_url: str) -> str:
    """
    Get the version of the validator
    :param validator_url: The URL of the validator
    :return: the version of the validator
    """
    response = requests.get(f"{validator_url}/version")
    validator_version = response.json()["version"]
    logging.info(f"Validator version: {validator_version}")
    return validator_version


def get_latest_datasets_without_validation_reports(
    session: sqlalchemy.orm.Session,
    validator_version: str,
    force_update: bool = False,
) -> List[Row[tuple[Any, Any]]]:
    """
    Retrieve the latest datasets for each feed that do not have a validation report
    :param session: The database session
    :param validator_version: The version of the validator
    :param force_update: Whether to force the update of the validation report
    :return: A list of tuples containing the feed stable id and dataset stable id
    """
    query = (
        session.query(
            Gtfsfeed.stable_id,
            Gtfsdataset.stable_id,
        )
        .select_from(Gtfsfeed)
        .join(Gtfsdataset, Gtfsdataset.feed_id == Gtfsfeed.id)
        .outerjoin(Validationreport, Gtfsdataset.validation_reports)
        .filter(Gtfsdataset.latest.is_(True))
        .filter(
            or_(
                Validationreport.validator_version != validator_version,
                Validationreport.id.is_(None),
                force_update,
            )
        )
        .distinct(Gtfsfeed.stable_id, Gtfsdataset.stable_id)
    )
    return query.all()


def get_datasets_for_validation(
    latest_datasets: List[Row[tuple[Any, Any]]]
) -> List[tuple[str, str]]:
    """
    Get the valid dataset blobs that need their validation report to be updated
    :param latest_datasets: List of tuples containing the feed stable id and dataset stable id
    :return: List of tuples containing the feed stable id and dataset stable id
    """
    report_update_needed = []
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    for feed_id, dataset_id in latest_datasets:
        try:
            dataset_blob = bucket.blob(f"{feed_id}/{dataset_id}/{dataset_id}.zip")
            if not dataset_blob.exists():
                logging.warning(f"Dataset blob not found for {feed_id}/{dataset_id}")
            else:
                report_update_needed.append((feed_id, dataset_id))
                logging.info(
                    f"Dataset blob found for {feed_id}/{dataset_id} -- Adding to update list"
                )
        except Exception as e:
            logging.error(
                f"Error while accessing dataset blob for {feed_id}/{dataset_id}: {e}"
            )
    return report_update_needed


def execute_workflow(
    project: str,
    location: str = "northamerica-northeast1",
    workflow: str = "gtfs_validator_execution",
    input_data: dict = None,
) -> Execution:
    """
    Executes a workflow with input data and print the execution results.
    @param project: The Google Cloud project id which contains the workflow to execute.
    @param location: The location for the workflow.
    @param workflow: The ID of the workflow to execute.
    @param input_data: A dictionary containing input data for the workflow.
    @return: The execution response.
    """
    execution_client = executions_v1.ExecutionsClient()
    workflows_client = workflows_v1.WorkflowsClient()
    parent = workflows_client.workflow_path(project, location, workflow)

    # Prepare the execution input as a JSON string.
    input_json = json.dumps(input_data) if input_data else "{}"

    # Create and configure the execution request with input data.
    execution_request = Execution(argument=input_json)
    response = execution_client.create_execution(
        parent=parent, execution=execution_request
    )
    logging.info(f"Created execution: {response.name}")
    execution = execution_client.get_execution(request={"name": response.name})
    return execution


def execute_workflows(
    latest_datasets,
    validator_endpoint=None,
    bypass_db_update=False,
    reports_bucket_name=None,
):
    """
    Execute the workflow for the latest datasets that need their validation report to be updated
    :param latest_datasets: List of tuples containing the feed stable id and dataset stable id
    :param validator_endpoint: The URL of the validator
    :param bypass_db_update: Whether to bypass the database update
    :param reports_bucket_name: The name of the bucket where the reports are stored
    :return: List of dataset stable ids for which the workflow was executed
    """
    project_id = f"mobility-feeds-{env}"
    location = os.getenv("LOCATION", "northamerica-northeast1")
    execution_triggered_datasets = []
    batch_size = int(os.getenv("BATCH_SIZE", 5))
    sleep_time = int(os.getenv("SLEEP_TIME", 5))
    count = 0
    logging.info(f"Executing workflow for {len(latest_datasets)} datasets")
    for feed_id, dataset_id in latest_datasets:
        try:
            input_data = {
                "data": {
                    "bypass_db_update": bypass_db_update,
                    "protoPayload": {
                        "resourceName": "projects/_/"
                        f"buckets/{bucket_name}/"
                        f"objects/{feed_id}/{dataset_id}/{dataset_id}.zip"
                    },
                    "resource": {
                        "labels": {"location": location, "project_id": project_id},
                    },
                }
            }
            if validator_endpoint:
                input_data["data"]["validator_endpoint"] = validator_endpoint
            if reports_bucket_name:
                input_data["data"]["reports_bucket_name"] = reports_bucket_name
            logging.info(f"Executing workflow for {feed_id}/{dataset_id}")
            execute_workflow(project_id, input_data=input_data)
            execution_triggered_datasets.append(dataset_id)
        except Exception as e:
            logging.error(
                f"Error while executing workflow for {feed_id}/{dataset_id}: {e}"
            )
        count += 1
        logging.info(f"Triggered workflow execution for {count} datasets")
        if count % batch_size == 0:
            logging.info(
                f"Sleeping for {sleep_time} seconds before next batch to avoid rate limiting.."
            )
            sleep(sleep_time)
    return execution_triggered_datasets
