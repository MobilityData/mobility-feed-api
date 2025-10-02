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
import logging
import os
from pathlib import Path

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
from sqlalchemy.orm import Session

from shared.common.gcp_utils import create_refresh_materialized_view_task
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsdataset, Gtfsfile
from shared.dataset_service.main import DatasetTraceService, DatasetTrace, Status
from shared.helpers.logger import init_logger, get_logger
from shared.helpers.utils import (
    download_and_get_hash,
    get_hash_from_file,
    download_from_gcs,
)
from pipeline_tasks import create_pipeline_tasks

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


def peek_bytes(path: str, n: int = 64) -> bytes:
    p = Path(path)
    if not p.exists():
        return b""
    with open(p, "rb") as f:
        return f.read(n)


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
        dataset_stable_id=None,
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
        self.dataset_stable_id = dataset_stable_id

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

    def download_content(self, temporary_file_path, feed_id):
        """
        Downloads the content of a URL and return the hash of the file
        """
        file_hash = download_and_get_hash(
            self.producer_url,
            file_path=temporary_file_path,
            feed_id=feed_id,
            authentication_type=self.authentication_type,
            api_key_parameter_name=self.api_key_parameter_name,
            credentials=self.feed_credentials,
            logger=self.logger,
        )
        self.logger.info(f"hash is: {file_hash}")
        is_zip = zipfile.is_zipfile(temporary_file_path)
        return file_hash, is_zip

    def upload_files_to_storage(
        self,
        source_file_path,
        dataset_stable_id,
        extracted_files_path,
        public=True,
        skip_dataset_upload=False,
    ):
        """
        Uploads the dataset file and extracted files to GCP storage
        """
        bucket = storage.Client().get_bucket(self.bucket_name)
        target_paths = [
            f"{self.feed_stable_id}/latest.zip",
            f"{self.feed_stable_id}/{dataset_stable_id}/{dataset_stable_id}.zip",
        ]
        blob = None
        if not skip_dataset_upload:
            for target_path in target_paths:
                blob = bucket.blob(target_path)
                blob.upload_from_filename(source_file_path)
                if public:
                    blob.make_public()
                self.logger.info(f"Uploaded {blob.public_url}")

        base_path, _ = os.path.splitext(source_file_path)
        extracted_files: List[Gtfsfile] = []
        if not extracted_files_path or not os.path.exists(extracted_files_path):
            self.logger.warning(
                f"Extracted files path {extracted_files_path} does not exist."
            )
            return blob, extracted_files
        self.logger.info("Processing extracted files from %s", extracted_files_path)
        for file_name in os.listdir(extracted_files_path):
            file_path = os.path.join(extracted_files_path, file_name)
            if os.path.isfile(file_path):
                file_blob = bucket.blob(
                    f"{self.feed_stable_id}/{dataset_stable_id}/extracted/{file_name}"
                )
                file_blob.upload_from_filename(file_path)
                if public:
                    file_blob.make_public()
                self.logger.info(
                    f"Uploaded extracted file {file_name} to {file_blob.public_url}"
                )
                extracted_files.append(
                    Gtfsfile(
                        id=str(uuid.uuid4()),
                        file_name=file_name,
                        file_size_bytes=os.path.getsize(file_path),
                        hosted_url=file_blob.public_url if public else None,
                        hash=get_hash_from_file(file_path),
                    )
                )
        return blob, extracted_files

    def upload_dataset(self, feed_id, public=True) -> DatasetFile or None:
        """
        Uploads a dataset to a GCP bucket as <feed_stable_id>/latest.zip and
        <feed_stable_id>/<feed_stable_id>-<upload_datetime>.zip
        if the dataset hash is different from the latest dataset stored
        :return: the file hash and the hosted url as a tuple or None if no upload is required
        """
        temp_file_path = None
        try:
            self.logger.info("Accessing URL %s", self.producer_url)
            temp_file_path = self.generate_temp_filename()
            file_sha256_hash, is_zip = self.download_content(temp_file_path, feed_id)
            if not is_zip:
                # General guard for HTML/non-ZIP responses and a browser-like fallback download
                first = peek_bytes(temp_file_path, 64)
                looks_html = (
                    first.strip().startswith(b"<!DOCTYPE") or b"<html" in first.lower()
                )
                if looks_html:
                    self.logger.warning(
                        "[%s] Download returned HTML instead of ZIP. "
                        "Retrying with browser-like headers and session.",
                        self.feed_stable_id,
                    )
                    try:
                        import requests
                        from urllib.parse import urlparse

                        parsed = urlparse(self.producer_url)
                        origin = f"{parsed.scheme}://{parsed.netloc}"
                        referer = origin + "/"
                        dir_url = (
                            (self.producer_url.rsplit("/", 1)[0] + "/")
                            if "/" in self.producer_url
                            else referer
                        )
                        headers = {
                            "User-Agent": (
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/124.0 Safari/537.36"
                            ),
                            "Accept": "*/*",
                            "Accept-Language": "en-US,en;q=0.9",
                            # Use site origin as a safe, general Referer (no path assumptions)
                            "Referer": referer,
                            "Connection": "keep-alive",
                        }
                        os.makedirs(
                            os.path.dirname(temp_file_path) or ".", exist_ok=True
                        )
                        with requests.Session() as s:
                            s.headers.update(headers)
                            # Best-effort cookie priming on the site origin and the file's directory (non-fatal)
                            try:
                                s.get(referer, timeout=15, allow_redirects=True)
                            except Exception:
                                pass
                            try:
                                if dir_url != referer:
                                    s.get(dir_url, timeout=15, allow_redirects=True)
                            except Exception:
                                pass
                            with s.get(
                                self.producer_url,
                                stream=True,
                                timeout=60,
                                allow_redirects=True,
                            ) as r:
                                r.raise_for_status()
                                ct = (r.headers.get("Content-Type") or "").lower()
                                # Peek signature to guard against HTML interstitials
                                first8 = r.raw.read(8, decode_content=True)
                                if "text/html" in ct or not first8.startswith(b"PK"):
                                    raise RuntimeError(
                                        f"Unexpected response during fallback. "
                                        f"Content-Type={ct!r}, first bytes={first8!r}"
                                    )
                                with open(temp_file_path, "wb") as out:
                                    out.write(first8)
                                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                                        if chunk:
                                            out.write(chunk)
                        if zipfile.is_zipfile(temp_file_path):
                            # Recompute hash after successful fallback
                            file_sha256_hash, is_zip = (
                                self.compute_file_hash(temp_file_path),
                                True,
                            )
                            self.logger.info(
                                "[%s] Fallback download validated as ZIP.",
                                self.feed_stable_id,
                            )
                        else:
                            self.logger.error(
                                "[%s] The downloaded file from %s is not a valid ZIP file.",
                                self.feed_stable_id,
                                self.producer_url,
                            )
                            return None
                    except Exception as fallback_err:
                        self.logger.error(
                            "[%s] Browser-like fallback failed: %s",
                            self.feed_stable_id,
                            fallback_err,
                        )

            self.logger.info(
                f"[{self.feed_stable_id}] File hash is {file_sha256_hash}."
            )
            if self.latest_hash != file_sha256_hash:
                self.logger.info(
                    f"[{self.feed_stable_id}] Dataset has changed (hash {self.latest_hash}"
                    f"-> {file_sha256_hash}). Uploading new version."
                )
                extracted_files_path = self.unzip_files(temp_file_path)
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
                    f"Creating file {dataset_full_path} in bucket {self.bucket_name}"
                )
                _, extracted_files = self.upload_files_to_storage(
                    temp_file_path,
                    dataset_stable_id,
                    extracted_files_path,
                    public=public,
                )

                return DatasetFile(
                    stable_id=dataset_stable_id,
                    file_sha256_hash=file_sha256_hash,
                    hosted_url=f"{self.public_hosted_datasets_url}/{dataset_full_path}",
                    extracted_files=extracted_files,
                    zipped_size=(
                        os.path.getsize(temp_file_path)
                        if os.path.exists(temp_file_path)
                        else None
                    ),
                )

            self.logger.info(
                f"[{self.feed_stable_id}] Datasets hash has not changed (hash {self.latest_hash} "
                f"-> {file_sha256_hash}). Not uploading it."
            )
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        return None

    @with_db_session
    def process_from_bucket(self, db_session, public=True) -> Optional[DatasetFile]:
        """
        Process an existing dataset from the GCP bucket updates the related database entities
        :return: The DatasetFile object created
        """
        temp_file_path = None
        try:
            temp_file_path = self.generate_temp_filename()
            blob_file_path = f"{self.feed_stable_id}/{self.dataset_stable_id}/{self.dataset_stable_id}.zip"
            self.logger.info(f"Processing dataset from bucket: {blob_file_path}")
            download_from_gcs(
                os.getenv("DATASETS_BUCKET_NAME"), blob_file_path, temp_file_path
            )

            extracted_files_path = self.unzip_files(temp_file_path)

            _, extracted_files = self.upload_files_to_storage(
                temp_file_path,
                self.dataset_stable_id,
                extracted_files_path,
                public=public,
                skip_dataset_upload=True,  # Skip the upload of the dataset file
            )

            dataset_file = DatasetFile(
                stable_id=self.dataset_stable_id,
                file_sha256_hash=self.latest_hash,
                hosted_url=f"{self.public_hosted_datasets_url}/{blob_file_path}",
                extracted_files=extracted_files,
                zipped_size=(
                    os.path.getsize(temp_file_path)
                    if os.path.exists(temp_file_path)
                    else None
                ),
            )
            dataset = self.create_dataset_entities(
                dataset_file, skip_dataset_creation=True, db_session=db_session
            )
            if dataset and dataset.latest:
                self.logger.info(
                    f"Creating pipeline tasks for latest dataset {dataset.stable_id}"
                )
                create_pipeline_tasks(dataset)
            elif dataset:
                self.logger.info(
                    f"Dataset {dataset.stable_id} is not the latest, skipping pipeline tasks creation."
                )
            else:
                raise ValueError("Dataset update failed, dataset is None.")
            return dataset_file
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    def unzip_files(self, temp_file_path):
        extracted_files_path = os.path.join(temp_file_path.split(".")[0], "extracted")
        self.logger.info(f"Unzipping files to {extracted_files_path}")
        # Create the directory for extracted files if it does not exist
        os.makedirs(extracted_files_path, exist_ok=True)
        with zipfile.ZipFile(temp_file_path, "r") as zip_ref:
            zip_ref.extractall(path=extracted_files_path)
        # List all files in the extracted directory
        extracted_files = os.listdir(extracted_files_path)
        self.logger.info(f"Extracted files: {extracted_files}")
        return extracted_files_path

    def generate_temp_filename(self):
        """
        Generates a temporary filename
        """
        working_dir = os.getenv("WORKING_DIR", "/in-memory")
        temporary_file_path = (
            f"{working_dir}/{self.feed_stable_id}-{random.randint(0, 1000000)}.zip"
        )
        return temporary_file_path

    @with_db_session
    def create_dataset_entities(
        self,
        dataset_file: DatasetFile,
        db_session: Session,
        skip_dataset_creation=False,
    ):
        """
        Creates dataset entities in the database
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

            dataset = None
            if not skip_dataset_creation:
                self.logger.info(
                    f"[{self.feed_stable_id}] Creating new dataset for feed with stable id {dataset_file.stable_id}."
                )
                dataset = Gtfsdataset(
                    id=str(uuid.uuid4()),
                    feed_id=self.feed_id,
                    stable_id=dataset_file.stable_id,
                    latest=True,
                    bounding_box=None,
                    note=None,
                    hash=dataset_file.file_sha256_hash,
                    downloaded_at=func.now(),
                    hosted_url=dataset_file.hosted_url,
                    gtfsfiles=(
                        dataset_file.extracted_files
                        if dataset_file.extracted_files
                        else []
                    ),
                    zipped_size_bytes=dataset_file.zipped_size,
                    unzipped_size_bytes=self._get_unzipped_size(dataset_file),
                )
                db_session.add(dataset)
            elif skip_dataset_creation and latest_dataset:
                self.logger.info(
                    f"[{self.feed_stable_id}] Updating latest dataset for feed with stable id "
                    f"{latest_dataset.stable_id}."
                )
                latest_dataset.gtfsfiles = (
                    dataset_file.extracted_files if dataset_file.extracted_files else []
                )
                latest_dataset.zipped_size_bytes = dataset_file.zipped_size
                latest_dataset.unzipped_size_bytes = self._get_unzipped_size(
                    dataset_file
                )

            if latest_dataset and not skip_dataset_creation:
                latest_dataset.latest = False
                db_session.add(latest_dataset)
            db_session.commit()
            self.logger.info(f"[{self.feed_stable_id}] Dataset created successfully.")

            create_refresh_materialized_view_task()
            return latest_dataset if skip_dataset_creation else dataset
        except Exception as e:
            raise Exception(f"Error creating dataset: {e}")

    @staticmethod
    def _get_unzipped_size(dataset_file):
        return (
            sum([ex.file_size_bytes for ex in dataset_file.extracted_files])
            if dataset_file.extracted_files
            else None
        )

    @with_db_session
    def process_from_producer_url(
        self, feed_id, db_session: Session
    ) -> Optional[DatasetFile]:
        """
        Process the dataset and store new version in GCP bucket if any changes are detected
        :return: the DatasetFile object created
        """
        dataset_file = self.upload_dataset(feed_id)

        if dataset_file is None:
            self.logger.info(f"[{self.feed_stable_id}] No database update required.")
            return None
        dataset = self.create_dataset_entities(dataset_file, db_session=db_session)
        create_pipeline_tasks(dataset)
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
                dataset_stable_id,
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
        #  Extract data from message
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
            json_payload.get("dataset_stable_id"),
        )
        if json_payload.get("use_bucket_latest", False):
            dataset_file = processor.process_from_bucket()
        else:
            dataset_file = processor.process_from_producer_url(json_payload["feed_id"])
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
