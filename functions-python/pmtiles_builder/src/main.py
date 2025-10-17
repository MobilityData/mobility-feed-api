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
import subprocess
import sys
from enum import Enum

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
)
from routes_processor import RoutesProcessor
from shared.database_gen.sqlacodegen_models import Gtfsdataset, Gtfsfeed
from shared.helpers.logger import get_logger, init_logger
from shared.helpers.runtime_metrics import track_metrics
from shared.database.database import with_db_session
from shared.helpers.transform import get_safe_value_from_csv
from ephemeral_workdir import EphemeralOrDebugWorkdir
import flask
import functions_framework

from routes_processor_for_colors import RoutesProcessorForColors
from shapes_processor import ShapesProcessor
from stops_processor import StopsProcessor
from trips_processor import TripsProcessor
from stop_times_processor import StopTimesProcessor

init_logger()


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
        no_database = os.getenv("NO_DATABASE", "").lower()
        self.use_database = False if no_database == "true" else True

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

        self.create_routes_geojson()

        self._run_tippecanoe("routes-output.geojson", "routes.pmtiles")

        # self.create_stops_geojson()

        # convert_stops_to_geojson(
        #     self.csv_cache,
        #     self.get_path("stops-output.geojson"),
        # )

        self._run_tippecanoe("stops-output.geojson", "stops.pmtiles")

        # self._create_routes_json()

        if self.use_gcs:
            files_to_upload = ["routes.pmtiles", "stops.pmtiles", "routes.json"]
            self._upload_files_to_gcs(files_to_upload)

        if self.use_database:
            self._update_database()

        self.logger.info("Completed PMTiles build")
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
    def create_routes_geojson(self):
        try:
            agencies = self._load_agencies()

            self.logger.info("Creating routes geojson ")
            shapes_processor = ShapesProcessor(self.csv_cache, self.logger)
            shapes_processor.process()
            trips_processor = TripsProcessor(self.csv_cache, self.logger)
            trips_processor.process()
            stop_times_processor = StopTimesProcessor(
                self.csv_cache, self.logger, trips_processor
            )
            stop_times_processor.process()

            routes_processor_for_colors = RoutesProcessorForColors(
                csv_cache=self.csv_cache,
                logger=self.logger,
            )
            routes_processor_for_colors.process()
            stops_processor = StopsProcessor(
                self.csv_cache,
                self.logger,
                routes_processor_for_colors,
                stop_times_processor,
            )
            stops_processor.process()

            routes_processor = RoutesProcessor(
                csv_cache=self.csv_cache,
                agencies=agencies,
                logger=self.logger,
                shapes_processor=shapes_processor,
                trips_processor=trips_processor,
                stops_processor=stops_processor,
                stop_times_processor=stop_times_processor,
            )
            routes_processor.process()
        except Exception as e:
            raise Exception(f"Failed to create routes GeoJSON: {e}") from e

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
