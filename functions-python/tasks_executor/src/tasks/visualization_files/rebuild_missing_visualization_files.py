#
#   MobilityData 2025
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
from typing import List, Final

from google.cloud import storage
from sqlalchemy import func, distinct
from sqlalchemy.orm import Session, selectinload

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsfeed, Gtfsdataset, Gtfsfile
from shared.helpers.utils import create_http_pmtiles_builder_task

REQUIRED_FILES: Final[List[str]] = [
    "stops.txt",
    "routes.txt",
    "trips.txt",
    "stop_times.txt",
]
PMTILES_FILES: Final[List[str]] = [
    "pmtiles/stops.pmtiles",
    "pmtiles/routes.pmtiles",
    "pmtiles/routes.json",
]


def rebuild_missing_visualization_files_handler(payload) -> dict:
    """
    Rebuilds missing visualization files for GTFS datasets.
    This function processes datasets missing visualization files and triggers the PMTiles builder workflow.
    The payload structure is:
    {
        "dry_run": bool,  # [optional] If True, do not execute the workflow
    }
    Args:
        payload (dict): The payload containing the task details.
    Returns:
        str: A message indicating the result of the operation with the total_processed datasets.
    """
    (dry_run, bucket_name, check_existing) = get_parameters(payload)

    return rebuild_missing_visualization_files(
        dry_run=dry_run,
        bucket_name=bucket_name,
        check_existing=check_existing,
    )


@with_db_session
def rebuild_missing_visualization_files(
    bucket_name: str,
    dry_run: bool = True,
    check_existing: bool = True,
    db_session: Session | None = None,
) -> dict:
    """
    Rebuilds missing visualization files for GTFS datasets.
    Args:
        bucket_name (str): The name of the bucket containing the GTFS data.
        dry_run (bool): dry run flag. If True, do not execute the workflow. Default: True
        db_session: DB session

    Returns:
        flask.Response: A response with message and total_processed datasets.
    """
    # Query latest datasets with all required files
    datasets_query = (
        db_session.query(Gtfsdataset)
        .filter(Gtfsdataset.latest.is_(True))
        .filter(Gtfsdataset.feed.has(Gtfsfeed.status != "deprecated"))
        .join(Gtfsdataset.gtfsfiles)
        .filter(Gtfsfile.file_name.in_(REQUIRED_FILES))
        .group_by(Gtfsdataset.id)
        .having(func.count(distinct(Gtfsfile.file_name)) == len(REQUIRED_FILES))
        .options(selectinload(Gtfsdataset.feed))
    )
    datasets = datasets_query.all()
    logging.info(f"Found {len(datasets)} latest datasets with all required files.")

    # Validate visualization files existence in the storage bucket
    client = storage.Client()
    bucket = client.get_bucket(bucket_name)
    tasks_to_create = []
    for dataset in datasets:
        if not check_existing:
            tasks_to_create.append(
                {
                    "feed_stable_id": dataset.feed.stable_id,
                    "dataset_stable_id": dataset.stable_id,
                }
            )
        else:
            # Check if visualization files already exist
            all_files_exist = True
            for file_suffix in PMTILES_FILES:
                file_path = (
                    f"{dataset.feed.stable_id}/{dataset.stable_id}/{file_suffix}"
                )
                blob = bucket.blob(file_path)
                if not blob.exists():
                    all_files_exist = False
                    logging.info(f"Missing visualization file: {file_path}")
                    break
            if not all_files_exist:
                tasks_to_create.append(
                    {
                        "feed_stable_id": dataset.feed.stable_id,
                        "dataset_stable_id": dataset.stable_id,
                    }
                )
            else:
                logging.info(
                    f"All visualization files exist for dataset {dataset.stable_id}. Skipping."
                )
    total_processed = len(tasks_to_create)
    logging.info(f"Total datasets to process: {total_processed}")

    # Create tasks to rebuild visualization files
    if not dry_run:
        for task in tasks_to_create:
            create_http_pmtiles_builder_task(
                task["feed_stable_id"], task["dataset_stable_id"]
            )

    message = (
        "Dry run: no datasets processed."
        if dry_run
        else "Rebuild missing visualization files task executed successfully."
    )
    result = {
        "message": message,
        "total_processed": total_processed,
        "params": {
            "dry_run": dry_run,
            "bucket_name": bucket_name,
        },
    }
    logging.info(result)
    return result


def get_parameters(payload):
    """
    Get parameters from the payload and environment variables.

    Args:
        payload (dict): dictionary containing the payload data.
    Returns:
        tuple: tuple with: dry_run, bucket_name, check_existing parameters
    """
    dry_run = payload.get("dry_run", True)
    dry_run = dry_run if isinstance(dry_run, bool) else str(dry_run).lower() == "true"
    bucket_name = os.getenv("DATASETS_BUCKET_NAME")
    if not bucket_name:
        raise EnvironmentError("DATASETS_BUCKET_NAME environment variable is not set.")
    check_existing = payload.get("check_existing", True)
    return dry_run, bucket_name, check_existing
