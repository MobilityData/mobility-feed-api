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

import functions_framework
import requests
import sqlalchemy.orm
from google.cloud import storage
from sqlalchemy.engine import Row
from sqlalchemy.engine.interfaces import Any

from database_gen.sqlacodegen_models import Gtfsdataset, Gtfsfeed
from helpers.database import start_db_session
from helpers.logger import Logger

logging.basicConfig(level=logging.INFO)


@functions_framework.http
def update_validation_report(_):
    """
    Update the validation report for the datasets that need it
    """
    Logger.init_logger()
    env = os.getenv("ENV", "dev").lower()

    # Get validator version
    validator_version = get_validator_version()

    bucket_name = f"mobilitydata-datasets-{env}"
    logging.info(f"Accessing bucket {bucket_name}")

    session = start_db_session(os.getenv("FEEDS_DATABASE_URL"), echo=False)
    latest_datasets = get_latest_datasets(session)
    logging.info(f"Retrieved {len(latest_datasets)} latest datasets.")

    dataset_blobs = get_dataset_blobs_for_validation(
        bucket_name, validator_version, latest_datasets
    )
    logging.info(f"Retrieved {len(dataset_blobs)} blobs to update.")

    updated_datasets = update_dataset_metadata(dataset_blobs, validator_version)
    response = {
        "message": f"Updated {len(updated_datasets)} validation report(s).",
        "updated_datasets": sorted(updated_datasets),
        "ignored_datasets": sorted(
            [
                dataset_id
                for _, dataset_id in latest_datasets
                if dataset_id not in updated_datasets
            ]
        ),
    }
    return response, 200


def get_validator_version():
    """
    Get the version of the validator
    :return: the version of the validator
    """
    web_validator_endpoint = os.getenv("WEB_VALIDATOR_URL")
    response = requests.get(f"{web_validator_endpoint}/version")
    validator_version = response.json()["version"]
    logging.info(f"Validator version: {validator_version}")
    return validator_version


def update_dataset_metadata(
    dataset_blobs: List[storage.Blob], validator_version: str
) -> List[str]:
    """
    Update the metadata of the dataset blobs - This will trigger the validation report processor
    :param dataset_blobs: The dataset blobs to update
    :param validator_version: The version of the validator
    :return: The list of updated datasets stable ids
    """
    max_retry = os.getenv("MAX_RETRY", None)
    batch_size = int(os.getenv("BATCH_SIZE", 5))
    sleep_time = int(os.getenv("SLEEP_TIME", 5))
    logging.info(f"Max retry: {max_retry}, Batch size: {batch_size}")

    batch_count = 0
    updated_datasets = []
    for blob in dataset_blobs:
        # Update metadata to trigger the validation report processor
        metadata = blob.metadata if blob.metadata is not None else {}
        retry = 0
        if "retry" in metadata:
            retry = int(metadata["retry"])
            if (
                "latest_validator_version" in metadata
                and metadata["latest_validator_version"] == validator_version
            ):
                if max_retry is not None and retry >= int(max_retry):
                    logging.info(
                        f"Max retry of {max_retry} reached for {blob.name} for validator version {validator_version} "
                        f"-- Skipping"
                    )
                    continue
            if (
                "latest_validator_version" in metadata
                and metadata["latest_validator_version"] != validator_version
            ):
                retry = 0  # Reset retry count if validator version has changed

        metadata["retry"] = str(retry + 1)
        metadata["latest_validator_version"] = validator_version
        blob.metadata = metadata
        blob.patch()
        batch_count += 1
        updated_datasets.append(blob.name.split("/")[1])
        logging.info(f"Updated {blob.name} metadata.")

        if batch_count == batch_size:
            logging.info("Sleeping for 5 seconds to avoid rate limiting..")
            sleep(sleep_time)
            batch_count = 0
    return updated_datasets


def get_latest_datasets(session: sqlalchemy.orm.Session) -> List[Row[tuple[Any, Any]]]:
    """
    Retrieve the latest datasets for each feed
    :param session: The database session
    :return: A list of tuples containing the feed stable id and dataset stable id
    """
    query = (
        session.query(
            Gtfsfeed.stable_id,
            Gtfsdataset.stable_id,
        )
        .select_from(Gtfsfeed)
        .join(Gtfsdataset, Gtfsdataset.feed_id == Gtfsfeed.id)
        .filter(Gtfsdataset.latest.is_(True))
    )
    return query.all()


def get_dataset_blobs_for_validation(
    bucket_name: str,
    validator_version: str,
    latest_datasets: List[Row[tuple[Any, Any]]],
) -> List[storage.Blob]:
    """
    Get the dataset blobs that need their validation report to be updated
    :param bucket_name: Name of the GCP bucket
    :param validator_version: Version of the validator
    :param latest_datasets: List of tuples containing the feed stable id and dataset stable id
    :return: List of blobs that need their validation report to be updated
    """
    report_update_needed = []
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    for feed_id, dataset_id in latest_datasets:
        system_errors_blob = bucket.blob(
            f"{feed_id}/{dataset_id}/system_errors_{validator_version}.json"
        )
        dataset_blob = bucket.blob(
            f"{feed_id}/{dataset_id}/{dataset_id}.zip"
        )
        dataset_blob_exists = dataset_blob.exists()
        if not dataset_blob_exists:
            logging.warning(f"Dataset blob not found for {feed_id}/{dataset_id}")
        # The system errors blob is used to determine if the validation report needs to be updated
        # since it's the only report that is always generated even if there are errors during validation
        if not system_errors_blob.exists() and dataset_blob_exists:
            report_update_needed.append(dataset_blob)
            logging.info(
                f"System errors blob not found for {feed_id}/{dataset_id} -- Adding to update list"
            )
    return report_update_needed
