import json
import logging
import os
from typing import Iterable, List

from google.cloud import tasks_v2
from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsdataset
from shared.helpers.utils import create_http_task


def create_http_reverse_geolocation_processor_task(
    stable_id: str,
    dataset_stable_id: str,
    stops_url: str,
) -> None:
    """
    Create a task to process reverse geolocation for a dataset.
    """
    client = tasks_v2.CloudTasksClient()
    body = json.dumps(
        {
            "stable_id": stable_id,
            "stops_url": stops_url,
            "dataset_id": dataset_stable_id,
        }
    ).encode()
    queue_name = os.getenv("REVERSE_GEOLOCATION_QUEUE")
    project_id = os.getenv("PROJECT_ID")
    gcp_region = os.getenv("GCP_REGION")

    create_http_task(
        client,
        body,
        f"https://{gcp_region}-{project_id}.cloudfunctions.net/reverse-geolocation-processor",
        project_id,
        gcp_region,
        queue_name,
    )


def create_http_pmtiles_builder_task(
    stable_id: str,
    dataset_stable_id: str,
) -> None:
    """
    Create a task to generate PMTiles for a dataset.
    """
    client = tasks_v2.CloudTasksClient()
    body = json.dumps(
        {"feed_stable_id": stable_id, "dataset_stable_id": dataset_stable_id}
    ).encode()
    queue_name = os.getenv("PMTILES_BUILDER_QUEUE")
    project_id = os.getenv("PROJECT_ID")
    gcp_region = os.getenv("GCP_REGION")

    create_http_task(
        client,
        body,
        f"https://{gcp_region}-{project_id}.cloudfunctions.net/pmtiles-builder",
        project_id,
        gcp_region,
        queue_name,
    )


@with_db_session
def get_changed_files(
    dataset: Gtfsdataset,
    db_session: Session,
) -> List[str]:
    """
    Return the subset of `file_names` whose content hash changed compared to the
    previous dataset for the same feed.
      - If there is no previous dataset → any file that exists in the new dataset is considered "changed".
      - If the file existed before and now is missing → NOT considered changed.
      - If the file did not exist before but exists now → considered changed.
      - If hashes differ → considered changed.
    """
    previous_dataset = (
        db_session.query(Gtfsdataset)
        .filter(
            Gtfsdataset.feed_id == dataset.feed_id,
            Gtfsdataset.id != dataset.id,
        )
        .order_by(Gtfsdataset.downloaded_at.desc())
        .first()
    )

    new_files = list(dataset.gtfsfiles)

    # No previous dataset -> everything that exists now is "changed"
    if not previous_dataset:
        return [f.file_name for f in new_files]

    prev_map = {
        f.file_name: getattr(f, "hash", None) for f in previous_dataset.gtfsfiles
    }

    changed_files = []
    for f in new_files:
        new_hash = getattr(f, "hash", None)
        old_hash = prev_map.get(f.file_name)

        if old_hash is None or old_hash != new_hash:
            changed_files.append(f)
            logging.info(f"Changed file {f.file_name} from {old_hash} to {new_hash}")

    return [f.file_name for f in changed_files]


@with_db_session
def create_pipeline_tasks(dataset: Gtfsdataset, db_session: Session) -> None:
    """
    Create pipeline tasks for a dataset.
    """
    changed_files = get_changed_files(dataset, db_session=db_session)

    stable_id = dataset.feed.stable_id
    dataset_stable_id = dataset.stable_id
    gtfs_files = dataset.gtfsfiles
    stops_file = next(
        (file for file in gtfs_files if file.file_name == "stops.txt"), None
    )
    stops_url = stops_file.hosted_url if stops_file else None

    # Create reverse geolocation task
    if stops_url and "stops.txt" in changed_files:
        create_http_reverse_geolocation_processor_task(
            stable_id, dataset_stable_id, stops_url
        )

    routes_file = next(
        (file for file in gtfs_files if file.file_name == "routes.txt"), None
    )
    # Create PMTiles builder task
    required_files = {"stops.txt", "routes.txt", "trips.txt", "stop_times.txt"}
    if not required_files.issubset(set(f.file_name for f in gtfs_files)):
        logging.info(
            f"Skipping PMTiles task for dataset {dataset_stable_id} due to missing required files. Required files: "
            f"{required_files}, available files: {[f.file_name for f in gtfs_files]}"
        )
    expected_file_change: Iterable[str] = {
        "stops.txt",
        "trips.txt",
        "routes.txt",
        "stop_times.txt",
        "shapes.txt",
    }
    if (
        routes_file
        and 0 < routes_file.file_size_bytes < 1_000_000
        and not set(changed_files).isdisjoint(expected_file_change)
    ):
        create_http_pmtiles_builder_task(stable_id, dataset_stable_id)
    elif routes_file:
        logging.info(
            f"Skipping PMTiles task for dataset {dataset_stable_id} due to constraints --> "
            f"routes.txt file size : {routes_file.file_size_bytes} bytes"
            f" and changed files: {changed_files}"
        )
