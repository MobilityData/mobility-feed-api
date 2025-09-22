import json
import logging
import os

from csv_cache import (
    STOP_TIMES_FILE,
    SHAPES_FILE,
    TRIPS_FILE,
    ROUTES_FILE,
    STOPS_FILE,
    AGENCY_FILE,
)
from main import build_pmtiles_handler
from shared.helpers.verifier_common import (
    setup_local_storage_emulator,
    shutdown_local_storage_emulator,
    EMULATOR_STORAGE_BUCKET_NAME,
    download_to_local,
)

feeds = [
    {"stable_id": "mdb-437", "dataset_stable_id": "mdb-437-202507081733"},
]
run_with_feed_index = 0  # Change this index to run with a different feed

FILES = [STOP_TIMES_FILE, SHAPES_FILE, TRIPS_FILE, ROUTES_FILE, STOPS_FILE, AGENCY_FILE]


def download_feed_files(feed_stable_id: str, dataset_stable_id: str):
    FILES_URL = "https://dev-files.mobilitydatabase.org"
    base_url = f"{FILES_URL}/{feed_stable_id}/{dataset_stable_id}/extracted"
    for file in FILES:
        url = f"{base_url}/{file}"
        logging.info(f"Downloading {url}")
        filename = f"{dataset_stable_id}/extracted/{file}"
        try:
            download_to_local(feed_stable_id, url, filename, False)
        except Exception as e:
            logging.warning(f"Failed to download {file}: {e}")


if __name__ == "__main__":
    from flask import Flask, Request

    app = Flask(__name__)
    os.environ["DATASETS_BUCKET_NAME"] = EMULATOR_STORAGE_BUCKET_NAME
    feed_dict = feeds[run_with_feed_index]
    feed_stable_id = feed_dict["stable_id"]
    dataset_stable_id = feed_dict["dataset_stable_id"]
    data = {
        "feed_stable_id": feed_stable_id,
        "dataset_stable_id": dataset_stable_id,
    }
    with app.test_request_context(
        path="/",
        method="POST",
        data=json.dumps(data),
        headers={"Content-Type": "application/json"},
    ):
        request = Request.from_values(
            method="POST",
            path="/",
            data=json.dumps(data),
            headers={"Content-Type": "application/json"},
        )
    try:
        server = setup_local_storage_emulator()
        download_feed_files(feed_stable_id, dataset_stable_id)
        response = build_pmtiles_handler(request)
        logging.info(response)
    except Exception as e:
        logging.error(f"Error verifying pmtiles builder: {e}")
    finally:
        shutdown_local_storage_emulator(server)
