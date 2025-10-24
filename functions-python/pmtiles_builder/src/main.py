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
import logging
import os
import subprocess
import sys
from enum import Enum

from google.cloud import storage
from sqlalchemy.orm import Session

from agencies_processor import AgenciesProcessor
from base_processor import BaseProcessor
from csv_cache import (
    CsvCache,
    ROUTES_FILE,
    STOP_TIMES_FILE,
    TRIPS_FILE,
    STOPS_FILE,
)
from routes_processor import RoutesProcessor
from shared.database_gen.sqlacodegen_models import Gtfsdataset, Gtfsfeed
from shared.helpers.logger import get_logger, init_logger
from shared.helpers.runtime_metrics import track_metrics
from shared.database.database import with_db_session
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
            result: dict[str, object] = {
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
            # is not available. So it's not an error of the pmtiles creation. In that case
            # we log a warning instead of an error.
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
    Build PMTiles for a GTFS dataset.

    - Reads GTFS CSVs and writes: routes-output.geojson, routes.json, stops-output.geojson
    - Runs Tippecanoe: routes.pmtiles, stops.pmtiles
    - Upload outputs to GCS and update the database

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
        # Track calls to _get_shape_points to control logging cadence
        self._get_shape_points_calls = 0

        no_database = os.getenv("NO_DATABASE", "").lower()
        self.use_database = False if no_database == "true" else True

        no_download = os.getenv("NO_DOWNLOAD_FROM_GCS", "").lower()
        self.download_from_gcs = False if no_download == "true" else True

        no_delete = os.getenv("NO_DELETE_DOWNLOADED_FILES", "").lower()
        self.delete_downloaded_files = False if no_delete == "true" else True

        no_upload = os.getenv("NO_UPLOAD_TO_GCS", "").lower()
        self.upload_to_gcs = False if no_upload == "true" else True

        no_gcs = os.getenv("NO_GCS", "").lower()
        if no_gcs == "true":
            self.download_from_gcs = False
            self.upload_to_gcs = False

        self.unzipped_files_path = (
            f"{self.feed_stable_id}/{self.dataset_stable_id}/extracted"
        )

    def get_path(self, filename: str) -> str:
        return self.csv_cache.get_path(filename)

    # Useful for testing
    def set_workdir(self, workdir: str):
        self.csv_cache.set_workdir(workdir)

    @track_metrics(metrics=("time", "memory", "cpu"))
    def build_pmtiles(self):
        self.logger.info("Starting PMTiles build")

        if self.download_from_gcs:
            # If we don't use gcs, we assume the txt files are already in the workdir.
            status, message = self.check_required_files_presence()
            if status == self.OperationStatus.FAILURE:
                return status, message

        self.process_all()

        self.run_tippecanoe("routes-output.geojson", "routes.pmtiles")

        self.run_tippecanoe("stops-output.geojson", "stops.pmtiles")

        if self.upload_to_gcs:
            files_to_upload = ["routes.pmtiles", "stops.pmtiles", "routes.json"]
            self.upload_files_to_gcs(files_to_upload)

        if self.use_database:
            self.update_database()

        self.logger.info("Completed PMTiles build")
        return self.OperationStatus.SUCCESS, "success"

    def check_required_files_presence(self):
        self.logger.info(
            "Making sure all required files are present in bucket %s, directory %s",
            self.bucket_name,
            self.unzipped_files_path,
        )
        try:
            try:
                self.bucket = storage.Client().get_bucket(self.bucket_name)
            except Exception as e:
                msg = f"Bucket '{self.bucket_name}' does not exist or is inaccessible: {e}"
                self.logger.warning(msg)
                return self.OperationStatus.FAILURE, msg

            self.logger.debug("Getting blobs with prefix: %s", self.unzipped_files_path)
            blobs = list(self.bucket.list_blobs(prefix=self.unzipped_files_path))
            self.logger.debug("Found %d blobs", len(blobs))
            if not blobs:
                msg = (
                    f"Directory '{self.unzipped_files_path}' does not exist or is empty "
                    f"in bucket '{self.bucket_name}'."
                )
                self.logger.warning(msg)
                return self.OperationStatus.FAILURE, msg

            required_files = [ROUTES_FILE, STOP_TIMES_FILE, TRIPS_FILE, STOPS_FILE]
            for file_name in required_files:
                blob_path = f"{self.unzipped_files_path}/{file_name}"
                blob = self.bucket.blob(blob_path)
                if not blob.exists():
                    msg = f"Required file '{blob_path}' does not exist in bucket '{self.bucket_name}'."
                    self.logger.warning(msg)
                    return self.OperationStatus.FAILURE, msg

            msg = "All required files are present."
            return self.OperationStatus.SUCCESS, msg
        except Exception as e:
            msg = f"Error checking presence of required files in bucket: {e}"
            raise Exception(msg) from e

    def upload_files_to_gcs(self, file_to_upload):
        if not self.upload_to_gcs:
            return

        dest_prefix = f"{self.feed_stable_id}/{self.dataset_stable_id}/pmtiles"
        self.logger.info(
            "Uploading files to GCS bucket %s, directory %s",
            self.bucket_name,
            dest_prefix,
        )
        try:
            self.bucket = storage.Client().get_bucket(self.bucket_name)

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
    def process_all(self):
        try:
            trips_processor = TripsProcessor(self.csv_cache, self.logger)
            self.download_and_process(trips_processor)

            stop_times_processor = StopTimesProcessor(
                self.csv_cache, self.logger, trips_processor
            )
            self.download_and_process(stop_times_processor)

            # Unfortunately, routes.txt has to be parsed in 2 passes. One to extract route colors, that is required by
            # StopProcessors, and another to build the full routes GeoJSON.
            # The file routes.txt is downloaded only once in RoutesProcessorForColors, then the file is kept for
            # processing in RoutesProcessor. Then it is deleted.
            routes_processor_for_colors = RoutesProcessorForColors(
                csv_cache=self.csv_cache,
                logger=self.logger,
            )
            self.download_and_process(routes_processor_for_colors)
            stops_processor = StopsProcessor(
                self.csv_cache,
                self.logger,
                routes_processor_for_colors,
                stop_times_processor,
            )
            self.download_and_process(stops_processor)

            shapes_processor = ShapesProcessor(self.csv_cache, self.logger)
            self.download_and_process(shapes_processor)

            agencies_processor = AgenciesProcessor(self.csv_cache, self.logger)
            self.download_and_process(agencies_processor)

            routes_processor = RoutesProcessor(
                csv_cache=self.csv_cache,
                logger=self.logger,
                agencies_processor=agencies_processor,
                shapes_processor=shapes_processor,
                trips_processor=trips_processor,
                stops_processor=stops_processor,
                stop_times_processor=stop_times_processor,
            )
            self.download_and_process(routes_processor)
        except Exception as e:
            raise Exception(f"Failed to create routes GeoJSON: {e}") from e

    def download_and_process(self, processor: BaseProcessor):
        file_name = processor.filename
        local_file_path = self.get_path(file_name)

        try:
            if processor.no_download or self.download_from_gcs is False:
                processor.process()
            else:
                blob_path = f"{self.unzipped_files_path}/{file_name}"

                self.logger.info(
                    "Downloading %s from GCS bucket %s",
                    blob_path,
                    self.bucket_name,
                )

                self.logger.debug("Initializing storage client for %s", blob_path)
                bucket = storage.Client().get_bucket(self.bucket_name)

                blob = bucket.blob(blob_path)
                if not blob.exists():
                    msg = f"File '{blob_path}' does not exist in bucket '{self.bucket_name}'."
                    self.logger.warning(msg)
                    return

                blob.download_to_filename(local_file_path)

                self.logger.debug(f"File {file_name} downloaded successfully.")

                processor.process()
        finally:
            if processor.no_delete or self.delete_downloaded_files is False:
                self.logger.debug(
                    "Skipping deletion of %s because no_delete is set to True",
                    local_file_path,
                )
            else:
                try:
                    if os.path.exists(local_file_path):
                        os.remove(local_file_path)
                        self.logger.debug(
                            f"File {local_file_path} deleted successfully."
                        )
                except Exception as e:
                    self.logger.warning(f"Failed to delete file {local_file_path}: {e}")

    @track_metrics(metrics=("time", "memory", "cpu"))
    def run_tippecanoe(self, input_file, output_file):
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

    @with_db_session
    def update_database(self, db_session: Session = None):
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
