import json
import os

from google.cloud import tasks_v2

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


def create_pipeline_tasks(dataset: Gtfsdataset) -> None:
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
    if stops_url:
        create_http_reverse_geolocation_processor_task(
            stable_id, dataset_stable_id, stops_url
        )

    # Create PMTiles builder task
    create_http_pmtiles_builder_task(stable_id, dataset_stable_id)
