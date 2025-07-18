#
#   MobilityData 2023
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import base64
import json
import os
import random
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

import functions_framework
from cloudevents.http import CloudEvent
from google.cloud import storage
from sqlalchemy import func

from shared.database_gen.sqlacodegen_models import Gtfsdataset, t_feedsearch, Gtfsfile
from shared.dataset_service.main import DatasetTraceService, DatasetTrace, Status
from shared.database.database import with_db_session, refresh_materialized_view
import logging

from shared.helpers.logger import init_logger, get_logger
from shared.helpers.utils import download_and_get_hash
from sqlalchemy.orm import Session

init_logger()


@dataclass
class DatasetFile:
    """
    Dataset file information
    """

    stable_id: str
    extracted_files: List[Gtfsfile] = None
    file_sha256_hash: Optional[str] = None
    hosted_url: Optional[str] = None
    zipped_size: Optional[int] = None


class DatasetProcessor:
    def __init__(
        self,
        producer_url,
        feed_id,
        feed_stable_id,
        execution_id,
        latest_hash,
        bucket_name,
        authentication_type,
        api_key_parameter_name,
        public_hosted_datasets_url,
    ):
        self.logger = get_logger(DatasetProcessor.__name__, feed_stable_id)
        self.producer_url = producer_url
        self.bucket_name = bucket_name
        self.latest_hash = latest_hash
        self.feed_id = feed_id
        self.feed_stable_id = feed_stable_id
        self.execution_id = execution_id
        self.authentication_type = authentication_type
        self.api_key_parameter_name = api_key_parameter_name
        self.date = datetime.now().strftime("%Y%m%d%H%M")
        if self.authentication_type != 0:
            self.logger.info(f"Getting feed credentials for feed {self.feed_stable_id}")
            self.feed_credentials = self.get_feed_credentials(self.feed_stable_id)
            if self.feed_credentials is None:
                raise Exception(
                    f"Error getting feed credentials for feed {self.feed_stable_id}"
                )
        else:
            self.feed_credentials = None
        self.public_hosted_datasets_url = public_hosted_datasets_url

        self.init_status = None
        self.init_status_additional_data = None

    @staticmethod
    def get_feed_credentials(feed_stable_id) -> str | None:
        """
        Gets the feed credentials from the environment variable
        """
        try:
            feeds_credentials = json.loads(os.getenv("FEEDS_CREDENTIALS", "{}"))
            return feeds_credentials.get(feed_stable_id, None)
        except Exception as e:
            get_logger(DatasetProcessor.__name__, feed_stable_id).error(
                f"Error getting feed credentials: {e}"
            )
            return None

    @staticmethod
    def create_dataset_stable_id(feed_stable_id, timestamp):
        """
        Creates a stable id for the dataset
        :param feed_stable_id: the feed's stable id
        :param timestamp: the timestamp of the dataset
        :return: the dataset's stable id
        """
        return f"{feed_stable_id}-{timestamp}"

    def download_content(self, temporary_file_path):
        """
        Downloads the content of a URL and return the hash of the file
        """
        file_hash = download_and_get_hash(
            self.producer_url,
            temporary_file_path,
            authentication_type=self.authentication_type,
            api_key_parameter_name=self.api_key_parameter_name,
            credentials=self.feed_credentials,
            logger=self.logger,
        )
        is_zip = zipfile.is_zipfile(temporary_file_path)
        if is_zip:
            extracted_file_path = os.path.join(
                temporary_file_path.split(".")[0], "extracted"
            )
            with zipfile.ZipFile(temporary_file_path, "r") as zip_ref:
                zip_ref.extractall(os.path.dirname(extracted_file_path))
            # List all files in the extracted directory
            extracted_files = os.listdir(os.path.dirname(extracted_file_path))
            self.logger.info(f"Extracted files: {extracted_files}")
        return file_hash, is_zip

    def upload_file_to_storage(self, source_file_path, dataset_stable_id):
        """
        Uploads a file to the GCP bucket
        """
        bucket = storage.Client().get_bucket(self.bucket_name)
        target_paths = [
            f"{self.feed_stable_id}/latest.zip",
            f"{self.feed_stable_id}/{dataset_stable_id}/{dataset_stable_id}.zip",
        ]
        blob = None
        for target_path in target_paths:
            blob = bucket.blob(target_path)
            with open(source_file_path, "rb") as file:
                blob.upload_from_file(file)
            blob.make_public()

        base_path, _ = os.path.splitext(source_file_path)
        extracted_files_path = os.path.join(base_path, "extracted")
        extracted_files: List[Gtfsfile] = []
        if not os.path.exists(extracted_files_path):
            self.logger.warning(
                f"Extracted files path {extracted_files_path} does not exist."
            )
            return blob, extracted_files
        for file_name in os.listdir(extracted_files_path):
            file_path = os.path.join(extracted_files_path, file_name)
            if os.path.isfile(file_path):
                file_blob = bucket.blob(
                    f"{self.feed_stable_id}/{dataset_stable_id}/extracted/{file_name}"
                )
                file_blob.upload_from_filename(file_path)
                file_blob.make_public()
                self.logger.info(
                    f"Uploaded extracted file {file_name} to {file_blob.public_url}"
                )
                extracted_files.append(
                    Gtfsfile(
                        id=str(uuid.uuid4()),
                        file_name=file_name,
                        file_size_bytes=os.path.getsize(file_path),
                    )
                )
        return blob, extracted_files

    def upload_dataset(self) -> DatasetFile or None:
        """
        Uploads a dataset to a GCP bucket as <feed_stable_id>/latest.zip and
        <feed_stable_id>/<feed_stable_id>-<upload_datetime>.zip
        if the dataset hash is different from the latest dataset stored
        :return: the file hash and the hosted url as a tuple or None if no upload is required
        """
        try:
            self.logger.info("Accessing URL %s", self.producer_url)
            temp_file_path = self.generate_temp_filename()
            file_sha256_hash, is_zip = self.download_content(temp_file_path)
            if not is_zip:
                self.logger.error(
                    f"[{self.feed_stable_id}] The downloaded file from {self.producer_url} is not a valid ZIP file."
                )
                return None

            self.logger.info(
                f"[{self.feed_stable_id}] File hash is {file_sha256_hash}."
            )

            if self.latest_hash != file_sha256_hash:
                self.logger.info(
                    f"[{self.feed_stable_id}] Dataset has changed (hash {self.latest_hash}"
                    f"-> {file_sha256_hash}). Uploading new version."
                )
                self.logger.info(
                    f"Creating file {self.feed_stable_id}/latest.zip in bucket {self.bucket_name}"
                )

                dataset_stable_id = self.create_dataset_stable_id(
                    self.feed_stable_id, self.date
                )
                dataset_full_path = (
                    f"{self.feed_stable_id}/{dataset_stable_id}/{dataset_stable_id}.zip"
                )
                self.logger.info(
                    f"Creating file: {dataset_full_path}"
                    f" in bucket {self.bucket_name}"
                )
                _, extracted_files = self.upload_file_to_storage(
                    temp_file_path, dataset_stable_id
                )

                return DatasetFile(
                    stable_id=dataset_stable_id,
                    file_sha256_hash=file_sha256_hash,
                    hosted_url=f"{self.public_hosted_datasets_url}/{dataset_full_path}",
                    extracted_files=extracted_files,
                    zipped_size=os.path.getsize(temp_file_path)
                    if os.path.exists(temp_file_path)
                    else None,
                )

            self.logger.info(
                f"[{self.feed_stable_id}] Datasets hash has not changed (hash {self.latest_hash} "
                f"-> {file_sha256_hash}). Not uploading it."
            )
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        return None

    def generate_temp_filename(self):
        """
        Generates a temporary filename
        """
        temporary_file_path = (
            f"/tmp/{self.feed_stable_id}-{random.randint(0, 1000000)}.zip"
        )
        return temporary_file_path

    @with_db_session
    def create_dataset(self, dataset_file: DatasetFile, db_session: Session):
        """
        Creates a new dataset in the database
        """
        try:
            # Check latest version of the dataset
            latest_dataset = (
                db_session.query(Gtfsdataset)
                .filter_by(latest=True, feed_id=self.feed_id)
                .one_or_none()
            )
            if not latest_dataset:
                self.logger.info(
                    f"[{self.feed_stable_id}] No latest dataset found for feed."
                )

            self.logger.info(
                f"[{self.feed_stable_id}] Creating new dataset for feed with stable id {dataset_file.stable_id}."
            )
            new_dataset = Gtfsdataset(
                id=str(uuid.uuid4()),
                feed_id=self.feed_id,
                stable_id=dataset_file.stable_id,
                latest=True,
                bounding_box=None,
                note=None,
                hash=dataset_file.file_sha256_hash,
                downloaded_at=func.now(),
                hosted_url=dataset_file.hosted_url,
                gtfsfiles=dataset_file.extracted_files
                if dataset_file.extracted_files
                else [],
                zipped_size_bytes=dataset_file.zipped_size,
                unzipped_size_bytes=sum(
                    [ex.file_size_bytes for ex in dataset_file.extracted_files]
                )
                if dataset_file.extracted_files
                else None,
            )
            if latest_dataset:
                latest_dataset.latest = False
                db_session.add(latest_dataset)
            db_session.add(new_dataset)
            db_session.commit()
            self.logger.info(f"[{self.feed_stable_id}] Dataset created successfully.")

            refresh_materialized_view(db_session, t_feedsearch.name)
            self.logger.info(
                f"[{self.feed_stable_id}] Materialized view refresh event triggered successfully."
            )
        except Exception as e:
            raise Exception(f"Error creating dataset: {e}")

    def process(self) -> DatasetFile or None:
        """
        Process the dataset and store new version in GCP bucket if any changes are detected
        :return: the file hash and the hosted url as a tuple or None if no upload is required
        """
        dataset_file = self.upload_dataset()

        if dataset_file is None:
            self.logger.info(f"[{self.feed_stable_id}] No database update required.")
            return None
        self.create_dataset(dataset_file)
        return dataset_file


def record_trace(
    execution_id, stable_id, status, dataset_file, error_message, trace_service
):
    """
    Record the trace in the datastore
    """
    get_logger("record_trace", stable_id if stable_id else "UNKNOWN").info(
        f"Recording trace in execution: [{execution_id}] with status: [{status}]"
    )
    trace = DatasetTrace(
        trace_id=None,
        stable_id=stable_id,
        status=status,
        execution_id=execution_id,
        file_sha256_hash=dataset_file.file_sha256_hash if dataset_file else None,
        hosted_url=dataset_file.hosted_url if dataset_file else None,
        error_message=error_message,
        timestamp=datetime.now(),
    )
    trace_service.save(trace)


@functions_framework.cloud_event
def process_dataset(cloud_event: CloudEvent):
    """
    Pub/Sub function entry point that processes a single dataset
    :param cloud_event: GCP Cloud Event with the format
    {
        "message": {
            "data":
            {
                execution_id,
                producer_url,
                feed_stable_id,
                feed_id,
                dataset_id,
                dataset_hash,
                authentication_type,
                authentication_info_url,
                api_key_parameter_name
            }
        }
    }
    """
    logging.info("Function Started")
    stable_id = "UNKNOWN"
    bucket_name = os.getenv("DATASETS_BUCKET_NAME")

    try:
        #  Extract data from message
        logging.info(f"Cloud Event: {cloud_event}")
        data = base64.b64decode(cloud_event.data["message"]["data"]).decode()
        json_payload = json.loads(data)
        logging.info(
            f"[{json_payload['feed_stable_id']}] JSON Payload: {json.dumps(json_payload)}"
        )
        stable_id = json_payload["feed_stable_id"]
        execution_id = json_payload["execution_id"]
    except Exception as e:
        error_message = f"[{stable_id}] Error parsing message: [{e}]"
        logging.error(error_message)
        logging.error(f"Function completed with error:{error_message}")
        return

    try:
        maximum_executions = os.getenv("MAXIMUM_EXECUTIONS", 1)
        public_hosted_datasets_url = os.getenv("PUBLIC_HOSTED_DATASETS_URL")
        trace_service = None
        dataset_file: DatasetFile = None
        error_message = None
        #  Extract  data from message
        data = base64.b64decode(cloud_event.data["message"]["data"]).decode()
        json_payload = json.loads(data)
        stable_id = json_payload["feed_stable_id"]
        logger = get_logger("process_dataset", stable_id)
        logger.info(f"JSON Payload: {json.dumps(json_payload)}")

        execution_id = json_payload["execution_id"]
        trace_service = DatasetTraceService()
        trace = trace_service.get_by_execution_and_stable_ids(execution_id, stable_id)
        logger.info(f"Dataset trace: {trace}")
        executions = len(trace) if trace else 0
        logger.info(
            f"Dataset executed times={executions}/{maximum_executions} "
            f"in execution=[{execution_id}] "
        )

        if executions > 0:
            if executions >= maximum_executions:
                error_message = (
                    f"Function already executed maximum times "
                    f"in execution: [{execution_id}]"
                )
                logger.error(error_message)
                return error_message

        processor = DatasetProcessor(
            json_payload["producer_url"],
            json_payload["feed_id"],
            stable_id,
            execution_id,
            json_payload["dataset_hash"],
            bucket_name,
            int(json_payload["authentication_type"]),
            json_payload["api_key_parameter_name"],
            public_hosted_datasets_url,
        )
        dataset_file = processor.process()
    except Exception as e:
        # This makes sure the logger is initialized
        logger = get_logger("process_dataset", stable_id if stable_id else "UNKNOWN")
        logger.error(e)
        error_message = f"Error execution: [{execution_id}] error: [{e}]"
        logger.error(error_message)
        logger.error(f"Function completed with error:{error_message}")
    finally:
        logger = get_logger("process_dataset", stable_id if stable_id else "UNKNOWN")
        if stable_id and execution_id:
            status = (
                Status.PUBLISHED if dataset_file is not None else Status.NOT_PUBLISHED
            )
            if error_message:
                status = Status.FAILED
            record_trace(
                execution_id,
                stable_id,
                status,
                dataset_file,
                error_message,
                trace_service,
            )
        else:
            logger.error(
                f"Function completed with errors, missing stable={stable_id} or execution_id={execution_id}"
            )
            return f"Function completed with errors, missing stable={stable_id} or execution_id={execution_id}"
    logger.info(
        f"Function %s in execution: [{execution_id}]",
        "successfully completed" if not error_message else "Failed",
    )
    return "Completed." if error_message is None else error_message
