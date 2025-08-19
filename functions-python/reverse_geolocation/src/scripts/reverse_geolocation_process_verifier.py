import json
import logging
import os
from io import BytesIO

import folium
import requests
from dotenv import load_dotenv
from google.cloud import storage

from reverse_geolocation_processor import reverse_geolocation_process
from shared.helpers.logger import init_logger

HOST = "localhost"
PORT = 9023
BUCKET_NAME = "verifier"
feed_stable_id = "mdb-1"

station_information_url = (
    "https://data.rideflamingo.com/gbfs/3/auckland/station_information.json"
)
vehicle_status_url = "https://data.rideflamingo.com/gbfs/3/auckland/vehicle_status.json"
free_bike_status_url = None

# Load environment variables from .env.local
load_dotenv(dotenv_path=".env.local")

init_logger()


def download_to_local(url: str, filename: str):
    """
    Download a file from a URL and upload it to the Google Cloud Storage emulator.
    If the file already exists, it will not be downloaded again.
    Args:
        url (str): The URL to download the file from.
        filename (str): The name of the file to save in the emulator.
    """
    blob_path = f"{feed_stable_id}/{filename}"
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(blob_path)

    # Check if the blob already exists in the emulator
    if not blob.exists():
        logging.info(f"Downloading and uploading: {blob_path}")
        with requests.get(url, stream=True) as response:
            response.raise_for_status()
            blob.content_type = "application/json"
            # The file is downloaded into memory before uploading to ensure it's seekable.
            # Be careful with large files.
            data = BytesIO(response.content)
            blob.upload_from_file(data, rewind=True)
    else:
        logging.info(f"Blob already exists: gs://{BUCKET_NAME}/{blob_path}")


def verify_reverse_geolocation_process():
    """
    Verify the reverse geolocation process by downloading the necessary files,
    triggering the reverse geolocation process, and visualizing the resulting GeoJSON file.
    This function simulates the process as if it were running in a Google Cloud Function environment.
    The resulting map will be saved in the .cloudstorage/verifier/{feed_stable_id}/geojson_map.html
    location, which can be viewed in a web browser.
    """
    app = Flask(__name__)
    download_to_local(url=station_information_url, filename="station_information.json")
    download_to_local(url=vehicle_status_url, filename="vehicle_status.json")

    with app.test_request_context(
        path="/reverse_geolocation",
        method="POST",
        data=json.dumps(data),
        headers={"Content-Type": "application/json"},
    ):
        request = Request.from_values(
            method="POST",
            path="/reverse_geolocation",
            data=json.dumps(data),
            headers={"Content-Type": "application/json"},
        )
        reverse_geolocation_process(request)

        # Visualize the resulting geojson file
        url = f"http://{HOST}:{PORT}/{BUCKET_NAME}/{feed_stable_id}/geolocation.geojson"
        gdf = gpd.read_file(url)

        # Calculate centroid for map center
        center = gdf.geometry.union_all().centroid
        m = folium.Map(location=[center.y, center.x], zoom_start=2)

        # Add GeoJSON overlay
        folium.GeoJson(gdf).add_to(m)

        # Automatically zoom to fit the full polygon bounds
        minx, miny, maxx, maxy = gdf.total_bounds
        m.fit_bounds([[miny, minx], [maxy, maxx]])  # [[south, west], [north, east]]

        # Save the map
        m.save(f".cloudstorage/verifier/{feed_stable_id}/geojson_map.html")


if __name__ == "__main__":
    import geopandas as gpd
    from gcp_storage_emulator.server import create_server
    from flask import Flask, Request

    data = {
        "stable_id": feed_stable_id,
        "dataset_id": "example_dataset_id",
        "station_information_url": f"http://{HOST}:{PORT}/{BUCKET_NAME}/{feed_stable_id}/station_information.json",
        "vehicle_status_url": f"http://{HOST}:{PORT}/{BUCKET_NAME}/{feed_stable_id}/vehicle_status.json",
        "free_bike_status_url": free_bike_status_url,
        "strategy": "per-point",
        "data_type": "gbfs",
        "public": "False",
    }

    try:
        os.environ["STORAGE_EMULATOR_HOST"] = f"http://{HOST}:{PORT}"
        os.environ["DATASETS_BUCKET_NAME_GBFS"] = BUCKET_NAME
        os.environ["DATASETS_BUCKET_NAME_GTFS"] = BUCKET_NAME
        server = create_server(
            host=HOST, port=PORT, in_memory=False, default_bucket=BUCKET_NAME
        )
        server.start()
        verify_reverse_geolocation_process()
    except Exception as e:
        logging.error(f"Error verifying download content: {e}")
    finally:
        server.stop()
