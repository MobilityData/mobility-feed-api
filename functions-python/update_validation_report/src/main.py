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
from typing import List

import flask
import functions_framework
import requests
import sqlalchemy.orm
from sqlalchemy import or_
from sqlalchemy.orm import Session
from google.cloud import storage
from sqlalchemy.engine import Row
from sqlalchemy.engine.interfaces import Any

from shared.database_gen.sqlacodegen_models import (
    Gtfsdataset,
    Gtfsfeed,
    Validationreport,
)
from shared.helpers.gtfs_validator_common import get_gtfs_validator_results_bucket
from shared.database.database import with_db_session

from shared.helpers.logger import init_logger
from shared.helpers.validation_report.validation_report_update import execute_workflows

init_logger()
env = os.getenv("ENV", "dev").lower()
bucket_name = f"mobilitydata-datasets-{env}"


@with_db_session
@functions_framework.http
def update_validation_report(request: flask.Request, db_session: Session):
    """
    Update the validation report for the datasets that need it
    """
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
        reports_bucket_name = get_gtfs_validator_results_bucket(
            env_param.lower() == "prod"
        )

    # Get validator version
    validator_version = get_validator_version(validator_endpoint)
    logging.info(f"Accessing bucket {bucket_name}")

    latest_datasets = get_latest_datasets_without_validation_reports(
        db_session, validator_version, force_update
    )
    logging.info("Retrieved %s latest datasets.", len(latest_datasets))

    valid_latest_datasets = get_datasets_for_validation(latest_datasets)
    logging.info("Retrieved %s blobs to update.", len(latest_datasets))

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
    logging.info("Validator version: %s", validator_version)
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
        .join(Gtfsdataset, Gtfsfeed.latest_dataset_id == Gtfsdataset.id)
        .outerjoin(Validationreport, Gtfsdataset.validation_reports)
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
    latest_datasets: List[Row[tuple[Any, Any]]],
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
                    "Dataset blob found for %s/%s -- Adding to update list",
                    feed_id,
                    dataset_id,
                )
        except Exception as e:
            logging.error(
                f"Error while accessing dataset blob for {feed_id}/{dataset_id}: {e}"
            )
    return report_update_needed
