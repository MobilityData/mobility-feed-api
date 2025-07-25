#
#
#   MobilityData 2025
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
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
import shutil
import subprocess
import sys

from google.cloud import storage
from sqlalchemy.orm import Session

sys.path.append(os.path.dirname(os.path.abspath(__file__)))  # noqa: E402

from create_shapes_index import create_shapes_index  # noqa: E402
from create_routes_geojson import create_routes_geojson  # noqa: E402
from run_tippecanoe import run_tippecanoe  # noqa: E402


def build_pmtiles_handler(payload) -> dict:
    """
    Rebuilds missing validation reports for GTFS datasets.
    This function processes datasets with missing validation reports using the GTFS validator workflow.
    The payload structure is:
    {
        "dry_run": bool,  # [optional] If True, do not execute the workflow
        "feed_stable_id": int, # [optional] Filter datasets older than this number of days(default: 14 days ago)
        "dataset_stable_id": list[str] # [optional] Filter datasets by status(in)
    }
    Args:
        payload (dict): The payload containing the task details.
    Returns:
        str: A message indicating the result of the operation with the total_processed datasets.
    """
    dry_run: bool
    (
        dry_run,
        feed_stable_id,
        dataset_stable_id,
    ) = get_parameters(payload)

    return build_pmtiles(
        dry_run=dry_run,
        feed_stable_id=feed_stable_id,
        dataset_stable_id=dataset_stable_id,
    )


def build_pmtiles(
    dry_run: bool = True,
    feed_stable_id: str | None = None,
    dataset_stable_id: str | None = None,
    db_session: Session | None = None,
) -> dict:
    """
    Rebuilds missing validation reports for GTFS datasets.

    Args:
        validator_endpoint: Validator endpoint URL
        dry_run (bool): dry run flag. If True, do not execute the workflow. Default: True
        filter_after_in_days (int):  Filter the datasets older than this number of days. Default: 14 days ago
        filter_statuses: [optional] Filter datasets by status(in). Default: None
        prod_env (bool): True if target environment is production, false otherwise. Default: False
        db_session: DB session

    Returns:
        flask.Response: A response with message and total_processed datasets.
    """
    bucket_name = os.getenv("DATASETS_BUCKET_NAME")
    if not bucket_name:
        return {"error": "DATASETS_BUCKET_NAME environment variable is not defined."}

    if not feed_stable_id or not dataset_stable_id:
        return {"error": "Both feed_stable_id and dataset_stable_id must be defined."}

    if feed_stable_id not in dataset_stable_id:
        return {"error": "feed_stable_id must be a substring of dataset_stable_id."}

    logging.info(
        "Starting PMTiles build for feed %s and dataset %s on bucket %s",
        feed_stable_id,
        dataset_stable_id,
        bucket_name,
    )
    unzipped_files_path = f"{feed_stable_id}/{dataset_stable_id}/extracted"

    logging.info("Initializing storage client")
    bucket = storage.Client().get_bucket(bucket_name)
    logging.info("Getting blobs with prefix: %s", unzipped_files_path)
    blobs = list(bucket.list_blobs(prefix=unzipped_files_path))
    logging.info("Found %d blobs", len(blobs))
    if not blobs:
        return {
            "error": f"Directory '{unzipped_files_path}' does not exist in bucket '{bucket_name}'."
        }

    local_dir = "./unzipped"
    if os.path.exists(local_dir):
        shutil.rmtree(local_dir)
    os.makedirs(local_dir, exist_ok=True)
    download_files_from_gcs(bucket_name, unzipped_files_path, local_dir)

    create_shapes_index(local_dir)
    create_routes_geojson(local_dir)
    logging.info(os.getcwd())

    result = subprocess.run(["which", "tippecanoe"], capture_output=True, text=True)
    logging.info("REsult of which command: %s", result.stdout.strip())

    run_tippecanoe("routes.pmtiles", "routes-output.geojson", local_dir)

    upload_files_to_gcs(
        bucket_name, local_dir, ["routes.pmtiles"], feed_stable_id, dataset_stable_id
    )

    result = subprocess.run(
        ["ls", "-l", "-R", local_dir], capture_output=True, text=True
    )
    logging.info("Files created:\n%s", result.stdout.strip())
    return {
        "message": f"Directory '{unzipped_files_path}' exists in bucket '{bucket_name}'."
    }


def get_parameters(payload):
    """
    Get parameters from the payload and environment variables.

    Args:
        payload (dict): dictionary containing the payload data.
    Returns:
        dict: dict with: dry_run, filter_after_in_days, filter_statuses, prod_env, validator_endpoint parameters
    """
    dry_run = payload.get("dry_run", True)
    dry_run = dry_run if isinstance(dry_run, bool) else str(dry_run).lower() == "true"
    feed_stable_id = payload.get("feed_stable_id", None)
    dataset_stable_id = payload.get("dataset_stable_id", None)

    return dry_run, feed_stable_id, dataset_stable_id


def download_files_from_gcs(bucket_name, unzipped_files_path, local_dir):
    file_names = [
        "routes.txt",
        "shapes.txt",
        "stop_times.txt",
        "trips.txt",
        "stops.txt",
    ]
    client = storage.Client()
    bucket = client.get_bucket(bucket_name)

    for file_name in file_names:
        blob_path = f"{unzipped_files_path}/{file_name}"
        blob = bucket.blob(blob_path)
        local_path = os.path.join(local_dir, file_name)
        blob.download_to_filename(local_path)
        logging.info("Downloaded %s to %s", blob_path, local_path)


def upload_files_to_gcs(
    bucket_name: str,
    source_dir: str,
    file_names: list[str],
    feed_stable_id: str,
    dataset_stable_id: str,
):
    client = storage.Client()
    bucket = client.get_bucket(bucket_name)
    dest_prefix = f"{feed_stable_id}/{dataset_stable_id}/pmtiles"

    # Delete existing files in the destination folder
    blobs_to_delete = list(bucket.list_blobs(prefix=dest_prefix + "/"))
    for blob in blobs_to_delete:
        blob.delete()
        logging.info("Deleted existing blob: %s", blob.name)

    # Upload new files
    for file_name in file_names:
        file_path = os.path.join(source_dir, file_name)
        if not os.path.exists(file_path):
            logging.warning("File not found: %s", file_path)
            continue
        blob_path = f"{dest_prefix}/{file_name}"
        blob = bucket.blob(blob_path)
        blob.upload_from_filename(file_path)
        logging.info("Uploaded %s to gs://%s/%s", file_path, bucket_name, blob_path)
