import logging
import os
import socket
import subprocess
from typing import Dict
import uuid
from io import BytesIO

import requests

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsfeed, Gbfsfeed
from shared.helpers.runtime_metrics import track_metrics

from google.cloud import storage
from sqlalchemy.orm import Session


EMULATOR_STORAGE_BUCKET_NAME = "verifier"
EMULATOR_HOST = "localhost"
EMULATOR_STORAGE_PORT = 9023


@track_metrics(metrics=("time", "memory", "cpu"))
def download_to_local(
    feed_stable_id: str, url: str, filename: str, force_download: bool = False
):
    """
    Download a file from a URL and upload it to the Google Cloud Storage emulator.
    If the file already exists, it will not be downloaded again.
    Args:
        url (str): The URL to download the file from.
        filename (str): The name of the file to save in the emulator.
    """
    if not url:
        return
    blob_path = f"{feed_stable_id}/{filename}"
    client = storage.Client()
    bucket = client.bucket(EMULATOR_STORAGE_BUCKET_NAME)
    blob = bucket.blob(blob_path)

    # Check if the blob already exists in the emulator
    if not blob.exists() or force_download:
        logging.info(f"Downloading and uploading: {blob_path}")
        with requests.get(url, stream=True) as response:
            response.raise_for_status()
            blob.content_type = "application/json"
            # The file is downloaded into memory before uploading to ensure it's seekable.
            # Be careful with large files.
            data = BytesIO(response.content)
            blob.upload_from_file(data, rewind=True)
    else:
        logging.info(
            f"Blob already exists: gs://{EMULATOR_STORAGE_BUCKET_NAME}/{blob_path}"
        )


@with_db_session
def create_test_data(feed_stable_id: str, feed_dict: Dict, db_session: Session = None):
    """
    Create test data in the database if it does not exist.
    This function is used to ensure that the reverse geolocation process has the necessary data to work with.
    """
    # Here you would typically interact with your database to create the necessary test data
    # For this example, we will just log the action
    logging.info(f"Creating test data for {feed_stable_id} with data: {feed_dict}")
    model = Gtfsfeed if feed_dict["data_type"] == "gtfs" else Gbfsfeed
    local_feed = (
        db_session.query(model).filter(model.stable_id == feed_stable_id).one_or_none()
    )
    if not local_feed:
        local_feed = model(
            id=uuid.uuid4(),
            stable_id=feed_stable_id,
            data_type=feed_dict["data_type"],
            feed_name="Test Feed",
            note="This is a test feed created for reverse geolocation verification.",
            producer_url="https://files.mobilitydatabase.org/mdb-2014/mdb-2014-202508120303/mdb-2014-202508120303.zip",
            authentication_type="0",
            status="active",
        )
        db_session.add(local_feed)
        db_session.commit()


def setup_local_storage_emulator():
    """
    Setup the Google Cloud Storage emulator by creating the necessary bucket.
    """
    from gcp_storage_emulator.server import create_server

    os.environ[
        "STORAGE_EMULATOR_HOST"
    ] = f"http://{EMULATOR_HOST}:{EMULATOR_STORAGE_PORT}"
    os.environ["DATASETS_BUCKET_NAME_GBFS"] = EMULATOR_STORAGE_BUCKET_NAME
    os.environ["DATASETS_BUCKET_NAME_GTFS"] = EMULATOR_STORAGE_BUCKET_NAME
    os.environ["DATASTORE_EMULATOR_HOST"] = "localhost:8081"
    server = create_server(
        host=EMULATOR_HOST,
        port=EMULATOR_STORAGE_PORT,
        in_memory=False,
        default_bucket=EMULATOR_STORAGE_BUCKET_NAME,
    )
    server.start()
    return server


def shutdown_local_storage_emulator(server):
    """Shutdown the Google Cloud Storage emulator."""
    server.stop()


def is_datastore_emulator_running(host=EMULATOR_HOST, port=8081):
    """Check if the Google Cloud Datastore emulator is running."""
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def start_datastore_emulator(project_id="test-project"):
    """Start the Google Cloud Datastore emulator if it's not already running."""
    if not is_datastore_emulator_running():
        process = subprocess.Popen(
            [
                "gcloud",
                "beta",
                "emulators",
                "datastore",
                "start",
                "--project={}".format(project_id),
                "--host-port=localhost:8081",
            ]
        )
        return process
    return None  # Already running


def shutdown_datastore_emulator(process):
    """Shutdown the Google Cloud Datastore emulator."""
    if process:
        process.terminate()
        process.wait()
