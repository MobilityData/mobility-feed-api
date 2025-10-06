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
# This module provides the PmtilesBuilder class and related functions to generate PMTiles files
# from GTFS datasets. It handles downloading required files from Google Cloud Storage, processing
# and indexing GTFS data, generating GeoJSON and JSON outputs, running Tippecanoe to create PMTiles,
# and uploading the results back to GCS.
import json
import logging
import os
import shutil
import subprocess
import sys
from enum import Enum
from typing import TypedDict, Tuple, List, Dict

from google.cloud import storage
from sqlalchemy.orm import Session

from csv_cache import (
    CsvCache,
    ROUTES_FILE,
    STOP_TIMES_FILE,
    TRIPS_FILE,
    STOPS_FILE,
    AGENCY_FILE,
    SHAPES_FILE,
    ShapeTrips,
)
from shapes_index import ShapesIndex
from gtfs_stops_to_geojson import convert_stops_to_geojson
from shared.database_gen.sqlacodegen_models import Gtfsdataset, Gtfsfeed
from shared.helpers.logger import get_logger, init_logger
from shared.helpers.runtime_metrics import track_metrics
from shared.database.database import with_db_session
from shared.helpers.transform import get_safe_value_from_csv

import flask
import functions_framework

init_logger()


class EphemeralOrDebugWorkdir:
    """Context manager similar to tempfile.TemporaryDirectory with debug + auto-clean.

    Behavior:
      - If DEBUG_WORKDIR env var is set (non-empty): that directory is created (if needed),
        returned, and never deleted nor cleaned.
      - Else: creates a temporary directory under the provided dir (or WORKDIR_ROOT env var),
        removes sibling directories older than a TTL (default 3600s / override via WORKDIR_MAX_AGE_SECONDS),
        and deletes the created directory on exit.

    Only directories whose names start with the fixed CLEANUP_PREFIX are considered for cleanup
    to avoid deleting unrelated folders that might exist under the same root.

    The final on-disk directory name always starts with the hardcoded prefix 'pmtiles_'.
    The caller-supplied prefix (if any) is appended verbatim after that.
    """

    CLEANUP_PREFIX = "pmtiles_"

    def __init__(
        self,
        dir: str | None = None,
        prefix: str | None = None,
        logger: logging.Logger | None = None,
    ):
        import tempfile

        self._debug_dir = os.getenv("DEBUG_WORKDIR") or None
        self._root = dir or os.getenv("WORKDIR_ROOT", "/tmp/in-memory")
        self._logger = logger or get_logger("Workdir")
        self._temp: tempfile.TemporaryDirectory[str] | None = None
        self.name: str

        os.makedirs(self._root, exist_ok=True)

        self._ttl_seconds = int(os.getenv("WORKDIR_MAX_AGE_SECONDS", "3600"))

        if self._debug_dir:
            os.makedirs(self._debug_dir, exist_ok=True)
            self.name = self._debug_dir
            return

        self._cleanup_old()

        # Simple prefix: fixed manager prefix + raw user prefix (if any)
        combined_prefix = self.CLEANUP_PREFIX + (prefix or "")

        self._temp = tempfile.TemporaryDirectory(dir=self._root, prefix=combined_prefix)
        self.name = self._temp.name

    def _cleanup_old(self):
        """
        Delete stale work directories created by this manager (names starting with CLEANUP_PREFIX)
        whose modification time is older than the configured TTL.
        """
        import time

        # If in debug mode, dont cleanup anything
        if self._debug_dir:
            return

        now = time.time()
        deleted_count = 0
        try:
            entries = list(os.scandir(self._root))
        except OSError as e:
            self._logger.warning("Could not scan workdir root %s: %s", self._root, e)
            return

        for entry in entries:
            try:
                if not entry.is_dir(follow_symlinks=False):
                    continue
                if not entry.name.startswith(self.CLEANUP_PREFIX):
                    continue
                try:
                    age = now - entry.stat(follow_symlinks=False).st_mtime
                except OSError:
                    continue
                if age > self._ttl_seconds:
                    shutil.rmtree(entry.path, ignore_errors=True)
                    deleted_count += 1
                    self._logger.debug(
                        "Removed expired workdir: %s age=%.0fs", entry.path, age
                    )
            except OSError as e:
                self._logger.warning("Failed to remove %s: %s", entry.path, e)

        if deleted_count:
            self._logger.info(
                "Cleanup removed %d expired workdirs from %s", deleted_count, self._root
            )

    def __enter__(self) -> str:  # Return path like TemporaryDirectory
        return self.name

    def __exit__(self, exc_type, exc, tb):
        if self._temp:
            self._temp.cleanup()
        return False  # do not suppress exceptions


class RouteCoordinates(TypedDict):
    shape_id: str
    trip_ids: List[str]
    coordinates: List[Tuple[float, float]]


@functions_framework.http
def build_pmtiles_handler(request: flask.Request) -> dict:
    """
    Entrypoint for building PMTiles files from a GTFS dataset.
    """

    payload = request.get_json(silent=True)

    feed_stable_id = payload.get("feed_stable_id")
    dataset_stable_id = payload.get("dataset_stable_id")

    if not (feed_stable_id and dataset_stable_id):
        return {
            "status": "error",
            "error": "Both feed_stable_id and dataset_stable_id must be defined.",
            "message": "",
        }

    if not dataset_stable_id.startswith(feed_stable_id):
        return {
            "status": "error",
            "error": f"feed_stable_id={feed_stable_id} is not a prefix of dataset_stable_id={dataset_stable_id}",
            "message": "",
        }

    bucket_name = os.getenv("DATASETS_BUCKET_NAME")
    if not bucket_name:
        return {
            "status": "error",
            "error": "DATASETS_BUCKET_NAME environment variable is not defined.",
            "message": "",
        }

    try:
        workdir_root = os.getenv("WORKDIR_ROOT", "/tmp/in-memory")
        # Use combined context manager that also cleans old directories
        with EphemeralOrDebugWorkdir(
            dir=workdir_root, prefix=f"{dataset_stable_id}_"
        ) as workdir:
            result = {
                "params": {
                    "feed_stable_id": feed_stable_id,
                    "dataset_stable_id": dataset_stable_id,
                },
            }
            builder = PmtilesBuilder(
                feed_stable_id=feed_stable_id,
                dataset_stable_id=dataset_stable_id,
                workdir=workdir,
            )
            status, message = builder.build_pmtiles()

            # A failure at this point means the pmtiles could not be created because the data
            # is not available. So it's not an error of the pmtiles creation. I n that case
            # we log an warning instead of an error.
            if status == PmtilesBuilder.OperationStatus.FAILURE:
                result["warning"] = message
            else:
                result["message"] = "Successfully built pmtiles."
            return result

    except Exception as e:
        # We expect the creation of pmtiles to be run periodically (like every day).
        # If it fails, we don't want GCP to retry automatically, which would be the case if we let the exception through
        # So we log the error and return a message, and that will be taken as a success with no retries.
        logging.exception("Failed to build PMTiles for dataset %s", dataset_stable_id)
        return {
            "error": f"Failed to build PMTiles for dataset {dataset_stable_id}: {e}"
        }


class PmtilesBuilder:
    """
    Orchestrates the end-to-end process of generating PMTiles files from GTFS datasets.

    This class manages downloading required files from Google Cloud Storage, processing and indexing GTFS data,
    generating GeoJSON and JSON outputs, running Tippecanoe to create PMTiles, and uploading results back to GCS.
    Temporary files are stored in the global `workdir` directory for local processing.
    """

    class OperationStatus(Enum):
        SUCCESS = 1
        FAILURE = 2

    def __init__(
        self,
        feed_stable_id: str | None = None,
        dataset_stable_id: str | None = None,
        workdir: str = "./workdir",
    ):
        self.bucket = None
        self.feed_stable_id = feed_stable_id
        self.dataset_stable_id = dataset_stable_id
        self.bucket_name = os.getenv("DATASETS_BUCKET_NAME")
        self.logger = get_logger(PmtilesBuilder.__name__, dataset_stable_id)

        self.csv_cache = CsvCache(workdir, self.logger)
        self.use_gcs = True
        # Track calls to _get_shape_points to control logging cadence
        self._get_shape_points_calls = 0

        # The NO_GCS variable controls if we do uploads and downloads from GCS.
        # It's useful for testing with local files only.
        no_gcs = os.getenv("NO_GCS", "").lower()
        self.use_gcs = False if no_gcs == "true" else True

    def get_path(self, filename: str) -> str:
        return self.csv_cache.get_path(filename)

    # Useful for testing
    def set_workdir(self, workdir: str):
        self.csv_cache.set_workdir(workdir)

    @track_metrics(metrics=("time",))
    def build_pmtiles(self):
        self.logger.info("Starting PMTiles build")

        if self.use_gcs:
            # If we don't use gcs, we assume the txt files are already in the workdir.
            unzipped_files_path = (
                f"{self.feed_stable_id}/{self.dataset_stable_id}/extracted"
            )

            status, message = self._download_files_from_gcs(unzipped_files_path)
            if status == self.OperationStatus.FAILURE:
                return status, message

        self._create_routes_geojson()

        self._run_tippecanoe("routes-output.geojson", "routes.pmtiles")

        convert_stops_to_geojson(
            self.csv_cache,
            self.get_path("stops-output.geojson"),
        )

        self._run_tippecanoe("stops-output.geojson", "stops.pmtiles")

        self._create_routes_json()

        if self.use_gcs:
            files_to_upload = ["routes.pmtiles", "stops.pmtiles", "routes.json"]
            self._upload_files_to_gcs(files_to_upload)
        self._update_database()

        return self.OperationStatus.SUCCESS, "success"

    def _download_files_from_gcs(self, unzipped_files_path):
        self.logger.info(
            "Downloading dataset from GCS bucket %s, directory %s",
            self.bucket_name,
            unzipped_files_path,
        )
        try:
            self.logger.debug("Initializing storage client")
            try:
                self.bucket = storage.Client().get_bucket(self.bucket_name)
            except Exception as e:
                msg = f"Bucket '{self.bucket_name}' does not exist or is inaccessible: {e}"
                self.logger.warning(msg)
                return self.OperationStatus.FAILURE, msg

            self.logger.debug("Getting blobs with prefix: %s", unzipped_files_path)
            blobs = list(self.bucket.list_blobs(prefix=unzipped_files_path))
            self.logger.debug("Found %d blobs", len(blobs))
            if not blobs:
                msg = f"Directory '{unzipped_files_path}' does not exist or is empty in bucket '{self.bucket_name}'."
                self.logger.warning(msg)
                return self.OperationStatus.FAILURE, msg

            files = [
                {"name": ROUTES_FILE, "required": True},
                {"name": STOP_TIMES_FILE, "required": True},
                {"name": TRIPS_FILE, "required": True},
                {"name": STOPS_FILE, "required": True},
                {"name": AGENCY_FILE, "required": False},
                {"name": SHAPES_FILE, "required": False},
            ]
            for file_info in files:
                file_name = file_info["name"]
                required = file_info["required"]
                blob_path = f"{unzipped_files_path}/{file_name}"
                blob = self.bucket.blob(blob_path)
                if not blob.exists():
                    if required:
                        msg = f"Required file '{blob_path}' does not exist in bucket '{self.bucket_name}'."
                        self.logger.warning(msg)
                        return self.OperationStatus.FAILURE, msg
                    self.logger.debug(
                        "Optional file %s does not exist in bucket %s",
                        blob_path,
                        self.bucket_name,
                    )
                    continue
                try:
                    blob.download_to_filename(self.get_path(file_name))
                except Exception as e:
                    if required:
                        msg = f"Error downloading required file '{blob_path}' from bucket '{self.bucket_name}': {e}"
                        self.logger.error(msg)
                        raise Exception(msg) from e
                    else:
                        msg = f"Cannot download optional file '{blob_path}' from bucket '{self.bucket_name}': {e}"
                        self.logger.warning(msg)

            msg = "All required files downloaded successfully."
            return self.OperationStatus.SUCCESS, msg
        except Exception as e:
            msg = f"Error downloading files from GCS: {e}"
            raise Exception(msg) from e

    def _upload_files_to_gcs(self, file_to_upload):
        dest_prefix = f"{self.feed_stable_id}/{self.dataset_stable_id}/pmtiles"
        self.logger.info(
            "Uploading files to GCS bucket %s, directory %s",
            self.bucket_name,
            dest_prefix,
        )
        try:
            blobs_to_delete = list(self.bucket.list_blobs(prefix=dest_prefix + "/"))
            for blob in blobs_to_delete:
                blob.delete()
                self.logger.debug("Deleted existing blob: %s", blob.name)
            for file_name in file_to_upload:
                file_path = self.get_path(file_name)
                if not os.path.exists(file_path):
                    self.logger.warning("File not found: %s", file_path)
                    continue
                blob_path = f"{dest_prefix}/{file_name}"
                blob = self.bucket.blob(blob_path)
                blob.upload_from_filename(file_path)
                self.logger.debug(
                    "Uploaded %s to gs://%s/%s",
                    file_path,
                    self.bucket_name,
                    blob_path,
                )
                try:
                    blob.make_public()
                    self.logger.debug(
                        "Made object public: https://storage.googleapis.com/%s/%s",
                        self.bucket_name,
                        blob_path,
                    )
                except Exception as e:
                    # Likely due to Uniform bucket-level access; log and continue
                    self.logger.warning(
                        "Could not make %s public (uniform bucket-level access enabled?): %s",
                        blob_path,
                        e,
                    )
        except Exception as e:
            raise Exception(f"Failed to upload files to GCS: {e}") from e

    @track_metrics(metrics=("time", "memory", "cpu"))
    def _create_shapes_index(self) -> ShapesIndex:
        """
        Create an index for shapes.txt file to quickly access shape points by shape_id.
        """

        shapes_index = ShapesIndex(
            self.get_path(SHAPES_FILE),
            "shape_id",
            ["shape_pt_lon", "shape_pt_lat", "shape_pt_sequence"],
            logger=self.logger,
        )
        shapes_index.build_index()
        self.csv_cache.debug_log_size("shapes_index", shapes_index)

        return shapes_index

    def _get_shape_points(self, shape_id, index):
        """Retrieve shape points for a given shape_id using the provided index.
        Args:
            shape_id (str): The shape_id to retrieve points for.
            index (ShapesIndex): The index to use for retrieval.
        Returns:
            List of (lon, lat) tuples representing the shape points.
        """
        # Log only on first call and every 1,000,000 calls
        self._get_shape_points_calls += 1
        count = self._get_shape_points_calls
        if count == 1 or (count % 1_000_000 == 0):
            self.logger.debug(
                "Getting shape points (called #%d times) for shape_id %s",
                count,
                shape_id,
            )
        return index.get_objects(shape_id)

    @track_metrics(metrics=("time", "memory", "cpu"))
    def _create_routes_geojson(self):
        try:
            agencies = self._load_agencies()

            shapes_index = self._create_shapes_index()
            self.logger.info("Creating routes geojson (optimized for memory)")

            features_count = 0
            missing_coordinates_routes = set()
            routes_geojson = self.get_path("routes-output.geojson")
            with open(routes_geojson, "w", encoding="utf-8") as geojson_file:
                geojson_file.write('{"type": "FeatureCollection", "features": [\n')
                for i, route in enumerate(self.csv_cache.get_file(ROUTES_FILE), 1):
                    agency_id = route.get("agency_id") or "default"
                    agency_name = agencies.get(agency_id, agency_id)

                    route_id = route["route_id"]
                    logging.debug("Processing route_id %s", route_id)
                    trips_coordinates: list[
                        RouteCoordinates
                    ] = self.get_route_coordinates(route_id, shapes_index)
                    if not trips_coordinates:
                        missing_coordinates_routes.add(route_id)
                        continue
                    for trip_coordinates in trips_coordinates:
                        trip_ids = trip_coordinates["trip_ids"]
                        shape_id = trip_coordinates["shape_id"]
                        feature = {
                            "type": "Feature",
                            "properties": {
                                "agency_name": agency_name,
                                "route_id": route_id,
                                "shape_id": shape_id,
                                "trip_ids": trip_ids,
                                "route_short_name": route.get("route_short_name", ""),
                                "route_long_name": route.get("route_long_name", ""),
                                "route_type": route.get("route_type", ""),
                                "route_color": route.get("route_color", ""),
                                "route_text_color": route.get("route_text_color", ""),
                            },
                            "geometry": {
                                "type": "LineString",
                                "coordinates": trip_coordinates["coordinates"],
                            },
                        }

                        if features_count != 0:
                            geojson_file.write(",\n")
                        geojson_file.write(json.dumps(feature))
                        features_count += 1

                    if i % 100 == 0 or i == 1:
                        self.logger.debug(
                            "Processed route %d (route_id: %s)", i, route_id
                        )

                geojson_file.write("\n]}")
                # Clear the different caches to save memory. They are currently not used anywhere else.
                self.csv_cache.clear_coordinate_for_stops()
                self.csv_cache.clear_shape_from_route()
                self.csv_cache.clear_stops_from_trip()
                self.csv_cache.clear_trip_from_route()
            if missing_coordinates_routes:
                self.logger.info(
                    "Routes without coordinates: %s", list(missing_coordinates_routes)
                )
            self.logger.debug(
                "Wrote %d features to routes-output.geojson", features_count
            )
        except Exception as e:
            raise Exception(f"Failed to create routes GeoJSON: {e}") from e

    def get_route_coordinates(self, route_id, shapes_index) -> List[RouteCoordinates]:
        shapes: Dict[str, ShapeTrips] = self.csv_cache.get_shape_from_route(route_id)
        result: List[RouteCoordinates] = []
        if shapes:
            for shape_id, trip_ids in shapes.items():
                # shape_id = shape["shape_id"]
                # trip_ids = shape["trip_ids"]
                coordinates = self._get_shape_points(shape_id, shapes_index)
                if coordinates:
                    result.append(
                        {
                            "shape_id": shape_id,
                            "trip_ids": trip_ids.get("trip_ids", []),
                            "coordinates": coordinates,
                        }
                    )

        trips_without_shape = self.csv_cache.get_trips_without_shape_from_route(
            route_id
        )
        if trips_without_shape:
            for trip_id in trips_without_shape:
                stops_for_trip = self.csv_cache.get_stops_from_trip(trip_id)
                if not stops_for_trip:
                    self.logger.info(
                        "No stops found for trip_id %s on route_id %s",
                        trip_id,
                        route_id,
                    )
                    continue
                # We assume stop_times is already sorted by stop_sequence in the file.
                # According to the SPECS:
                #    The values must increase along the trip but do not need to be consecutive.
                coordinates = [
                    coord
                    for stop_id in stops_for_trip
                    if (coord := self.csv_cache.get_coordinates_for_stop(stop_id))
                    is not None
                ]
                if coordinates:
                    result.append(
                        {
                            "shape_id": "",
                            "trip_ids": [trip_id],
                            "coordinates": coordinates,
                        }
                    )
                else:
                    self.logger.info(
                        "Coordinates do not have the right formatting for stops of trip_id %s on route_id %s",
                        trip_id,
                        route_id,
                    )

        return result

    @track_metrics(metrics=("time", "memory", "cpu"))
    def _run_tippecanoe(self, input_file, output_file):
        self.logger.info("Running tippecanoe for input file %s", input_file)
        try:
            cmd = [
                "tippecanoe",
                "-o",
                self.get_path(output_file),
                "--force",
                "--no-tile-size-limit",
                "-zg",
                self.get_path(input_file),
            ]
            self.logger.debug("Running command: %s", " ".join(cmd))
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.stdout:
                self.logger.debug("Tippecanoe output:\n%s", result.stdout)
            if result.returncode != 0:
                self.logger.error("Tippecanoe error:\n%s", result.stderr)
                raise Exception(f"Tippecanoe failed with exit code {result.returncode}")
            self.logger.debug("Tippecanoe command executed successfully.")
        except Exception as e:
            raise Exception(
                f"Failed to run tippecanoe for output file {output_file}: {e}"
            ) from e

    @track_metrics(metrics=("time", "memory", "cpu"))
    def _create_routes_json(self):
        self.logger.info("Creating routes json...")
        try:
            routes = []
            for row in self.csv_cache.get_file(ROUTES_FILE):
                route_id = get_safe_value_from_csv(row, "route_id", "")
                route = {
                    "routeId": route_id,
                    "routeName": (
                        get_safe_value_from_csv(row, "route_long_name", "")
                        or get_safe_value_from_csv(row, "route_short_name", "")
                        or route_id
                    ),
                    "color": f"#{get_safe_value_from_csv(row, 'route_color', '000000')}",
                    "textColor": f"#{get_safe_value_from_csv(row, 'route_text_color', 'FFFFFF')}",
                    "routeType": f"{get_safe_value_from_csv(row, 'route_type', '')}",
                }
                routes.append(route)

            with open(self.get_path("routes.json"), "w", encoding="utf-8") as f:
                json.dump(routes, f, ensure_ascii=False, indent=4)

            self.logger.debug("Converted %d routes to routes.json.", len(routes))
        except Exception as e:
            raise Exception(f"Failed to create routes JSON for dataset: {e}") from e

    def _load_agencies(self):
        agencies = {}
        agency_file_path = self.get_path(AGENCY_FILE)
        if not os.path.exists(agency_file_path):
            self.logger.warning("agency.txt not found, agencies will be empty.")
            return agencies
        for row in self.csv_cache.get_file(AGENCY_FILE):
            agency_id = row.get("agency_id") or ""
            agency_name = row.get("agency_name", "").strip()
            agencies[agency_id] = agency_name

        return agencies

    @with_db_session
    def _update_database(self, db_session: Session = None):
        dataset = (
            db_session.query(Gtfsdataset)
            .filter(Gtfsdataset.stable_id == self.dataset_stable_id)
            .one_or_none()
        )
        if not dataset:
            self.logger.error(
                "Dataset %s not found in database, cannot update pmtiles_generated.",
                self.dataset_stable_id,
            )
            return

        # fetch the subclass row that shares the same PK as Feed
        gtfsfeed = db_session.get(Gtfsfeed, dataset.feed_id)
        if not gtfsfeed:
            self.logger.error(
                "Gtfsfeed(id=%s) not found (but Feed exists) — cannot set visualization_dataset.",
                dataset.feed_id,
            )
            return

        # set the relationship on the subclass
        gtfsfeed.visualization_dataset = dataset
        db_session.commit()


def main():  # pragma: no cover
    if len(sys.argv) < 2:
        print("Usage: python src/main.py <dataset_stable_id>")
        sys.exit(1)

    dataset_stable_id = sys.argv[1]
    # Deduce feed_stable_id as the part before the first underscore
    feed_stable_id = dataset_stable_id.rsplit("-", 1)[0]
    payload = {"feed_stable_id": feed_stable_id, "dataset_stable_id": dataset_stable_id}

    with flask.Flask(__name__).test_request_context(json=payload):
        request = flask.request
        result = build_pmtiles_handler(request)
        print(result)


if __name__ == "__main__":
    main()
