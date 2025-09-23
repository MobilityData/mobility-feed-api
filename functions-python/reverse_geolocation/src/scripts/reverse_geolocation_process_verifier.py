# This script is used to verify the reverse geolocation process
# Before running this script, ensure you have the necessary environment set up:
# 1. Google DataStore emulator running on localhost:8081 by running:
#       gcloud beta emulators datastore start --project=your-project-id

import json
import logging
from typing import Dict

import folium
from dotenv import load_dotenv

from reverse_geolocation_processor import reverse_geolocation_process
from shared.helpers.locations import ReverseGeocodingStrategy
from shared.helpers.logger import init_logger

from shared.helpers.verifier_common import (
    download_to_local,
    EMULATOR_STORAGE_BUCKET_NAME,
    create_test_data,
    EMULATOR_HOST,
    EMULATOR_STORAGE_PORT,
    setup_local_storage_emulator,
    shutdown_local_storage_emulator,
    start_datastore_emulator,
    shutdown_datastore_emulator,
)

feeds = [
    {
        # 0. 1539 stops, NZ, 1 location
        "stable_id": "local-test-gbfs-flamingo_auckland",
        "station_information_url": "https://data.rideflamingo.com/gbfs/3/auckland/station_information.json",
        "vehicle_status_url": "https://data.rideflamingo.com/gbfs/3/auckland/vehicle_status.json",
        "data_type": "gbfs",
    },
    {
        # 1. 11777 stops, JP, 241 locations
        "stable_id": "local-test-gbfs-hellocycling",
        "station_information_url": "https://api-public.odpt.org/api/v4/gbfs/hellocycling/station_information.json",
        "data_type": "gbfs",
    },
    {
        # 2. 308611, UK aggregated, 225 locations
        "stable_id": "local-test-2014",
        "stops_url": "https://storage.googleapis.com/mobilitydata-datasets-prod/mdb-2014/"
        "mdb-2014-202508120303/extracted/stops.txt",
        "data_type": "gtfs",
    },
    {
        # 3. 663 stops, Europe, 334 locations
        "stable_id": "local-test-1139",
        "stops_url": "https://storage.googleapis.com/mobilitydata-datasets-prod/mdb-1139/"
        "mdb-1139-202406071559/stops.txt",
        "data_type": "gtfs",
    },
    {
        # 4. 10985 stops, Spain, duplicate key error(https://github.com/MobilityData/mobility-feed-api/issues/1289)
        "stable_id": "local-test-gtfs-mdb-2825",
        "stops_url": "https://storage.googleapis.com/mobilitydata-datasets-prod/mdb-2825/"
        "mdb-2825-202508181628/extracted/stops.txt",
        "data_type": "gtfs",
    },
    {
        # 5. 1355 stops, Canada, Saskatchewan ,
        # Duplicate admin level https://github.com/MobilityData/mobility-feed-api/issues/965
        "stable_id": "local-test-gtfs-mdb-716",
        "stops_url": "https://storage.googleapis.com/mobilitydata-datasets-dev/mdb-716/mdb-716-202507082001/"
        "extracted/stops.txt",
        "data_type": "gtfs",
    },
    {
        # 6. 667 stops, Canada, New Brunswick,
        # Duplicate admin level https://github.com/MobilityData/mobility-feed-api/issues/965
        "stable_id": "local-test-gtfs-mdb-1111",
        "stops_url": "https://storage.googleapis.com/mobilitydata-datasets-dev/mdb-1111/mdb-1111-202507082012/"
        "extracted/stops.txt",
        "data_type": "gtfs",
    },
]
run_with_feed_index = (
    3  # Set to an integer index to run with a specific feed from the list above
)


# Load environment variables from .env.local
load_dotenv(dotenv_path=".env.local")

init_logger()


def verify_reverse_geolocation_process(
    feed_stable_id: str,
    feed_dict: Dict,
    data: Dict,
    strategy: ReverseGeocodingStrategy,
    force_download: bool = True,
):
    """
    Verify the reverse geolocation process by downloading the necessary files,
    triggering the reverse geolocation process, and visualizing the resulting GeoJSON file.
    This function simulates the process as if it were running in a Google Cloud Function environment.
    The resulting map will be saved in the .cloudstorage/verifier/{feed_stable_id}/geojson_map.html
    location, which can be viewed in a web browser.
    """
    app = Flask(__name__)

    if feed_dict["data_type"] == "gbfs":
        if "station_information_url" in feed_dict:
            download_to_local(
                feed_stable_id=feed_stable_id,
                url=feed_dict["station_information_url"],
                filename="station_information.json",
                force_download=True,
            )
        if "vehicle_status_url" in feed_dict:
            download_to_local(
                feed_stable_id=feed_stable_id,
                url=feed_dict["vehicle_status_url"],
                filename="vehicle_status.json",
                force_download=True,
            )
        if "free_bike_status_url" in feed_dict:
            download_to_local(
                feed_stable_id=feed_stable_id,
                url=feed_dict["free_bike_status_url"],
                filename="free_bike_status.json",
                force_download=True,
            )
    else:
        download_to_local(
            feed_stable_id=feed_stable_id,
            url=feed_dict["stops_url"],
            filename="stops.txt",
            force_download=force_download,
        )

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
        url = (
            f"http://{EMULATOR_HOST}:{EMULATOR_STORAGE_PORT}/{EMULATOR_STORAGE_BUCKET_NAME}"
            f"/{feed_stable_id}/geolocation.geojson"
        )
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
        m.save(
            f".cloudstorage/verifier/{feed_stable_id}/geojson_map_{strategy.value}.html"
        )


if __name__ == "__main__":
    import geopandas as gpd
    from flask import Flask, Request

    strategy = ReverseGeocodingStrategy.PER_POINT

    feed_dict = feeds[run_with_feed_index]
    feed_stable_id = feed_dict["stable_id"]
    # create test data in the database if does not exist
    create_test_data(feed_stable_id=feed_stable_id, feed_dict=feed_dict)
    data = {
        "stable_id": feed_stable_id,
        "dataset_id": feed_dict["dataset_id"] if "dataset_id" in feed_dict else None,
        "station_information_url": f"http://{EMULATOR_HOST}:{EMULATOR_STORAGE_PORT}/{EMULATOR_STORAGE_BUCKET_NAME}"
        f"/{feed_stable_id}/station_information.json"
        if "station_information_url" in feed_dict
        else None,
        "vehicle_status_url": f"http://{EMULATOR_HOST}:{EMULATOR_STORAGE_PORT}/{EMULATOR_STORAGE_BUCKET_NAME}"
        f"/{feed_stable_id}/vehicle_status.json"
        if "vehicle_status_url" in feed_dict
        else None,
        "free_bike_status_url": f"http://{EMULATOR_HOST}:{EMULATOR_STORAGE_PORT}/{EMULATOR_STORAGE_BUCKET_NAME}"
        f"/{feed_stable_id}/free_bike_status.json"
        if "free_bike_status_url" in feed_dict
        else None,
        "stops_url": f"http://{EMULATOR_HOST}:{EMULATOR_STORAGE_PORT}/{EMULATOR_STORAGE_BUCKET_NAME}"
        f"/{feed_stable_id}/stops.txt",
        "strategy": str(strategy.value),
        "data_type": feed_dict["data_type"],
        # "use_cache": False,
        "public": False,
        "maximum_executions": 1000,
    }

    try:
        server = setup_local_storage_emulator()
        datastore_process = start_datastore_emulator()
        verify_reverse_geolocation_process(
            feed_stable_id=feed_stable_id,
            feed_dict=feed_dict,
            strategy=strategy,
            data=data,
        )
    except Exception as e:
        logging.error(f"Error verifying download content: {e}")
    finally:
        shutdown_local_storage_emulator(server)
        shutdown_datastore_emulator(datastore_process)
