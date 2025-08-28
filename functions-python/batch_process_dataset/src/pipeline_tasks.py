import json
import logging
import os

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
        f"https://{gcp_region}-{project_id}.cloudfunctions.net/pmtiles_builder",
        project_id,
        gcp_region,
        queue_name,
    )


@with_db_session
def has_file_changed(dataset: Gtfsdataset, file_name: str, db_session: Session) -> bool:
    """
    Check if a file has changed in the dataset.
    """
    previous_dataset = (
        db_session.query(Gtfsdataset)
        .filter(
            Gtfsdataset.feed_id == dataset.feed_id,
            Gtfsdataset.id != dataset.id,
            Gtfsdataset.latest.is_(False),
        )
        .order_by(Gtfsdataset.downloaded_at.desc())
        .first()
    )
    if not previous_dataset:
        return True
    existing_file = next(
        (file for file in previous_dataset.gtfsfiles if file.file_name == file_name),
        None,
    )
    if not existing_file:
        return True
    new_dataset_file = next(
        (file for file in dataset.gtfsfiles if file.file_name == file_name), None
    )
    if not new_dataset_file:
        return True
    return existing_file.hash != new_dataset_file.hash


@with_db_session
def create_pipeline_tasks(dataset: Gtfsdataset, db_session: Session) -> None:
    """
    Create pipeline tasks for a dataset.
    """
    stable_id = dataset.feed.stable_id
    dataset_stable_id = dataset.stable_id
    gtfs_files = dataset.gtfsfiles
    stops_file = next(
        (file for file in gtfs_files if file.file_name == "stops.txt"), None
    )
    stops_url = stops_file.hosted_url if stops_file else None

    # Create reverse geolocation task
    if stops_url and has_file_changed(dataset, "stops.txt", db_session):
        create_http_reverse_geolocation_processor_task(
            stable_id, dataset_stable_id, stops_url
        )

    routes_file = next(
        (file for file in gtfs_files if file.file_name == "routes.txt"), None
    )
    # Create PMTiles builder task
    if (
        routes_file
        and 0 < routes_file.file_size_bytes < 1_000_000
        and has_file_changed(dataset, "routes.txt", db_session)
    ):
        create_http_pmtiles_builder_task(stable_id, dataset_stable_id)
    elif routes_file:
        logging.info(
            f"Skipping PMTiles task for dataset {dataset_stable_id} due to size. routes.txt size: "
            f"{routes_file.file_size_bytes} bytes"
        )
