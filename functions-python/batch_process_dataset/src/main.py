import base64
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Optional

import functions_framework
from cloudevents.http import CloudEvent
from google.cloud import storage
from sqlalchemy import func

from database_gen.sqlacodegen_models import Gtfsdataset
from helpers.database import start_db_session, close_db_session
import logging

from helpers.logger import Logger
from helpers.utils import download_url_content


@dataclass
class DatasetFile:
    stable_id: str
    file_sha256_hash: Optional[str] = None
    hosted_url: Optional[str] = None


class DatasetProcessor:
    def __init__(self, producer_url, feed_id, feed_stable_id, execution_id, latest_hash, bucket_name):
        self.producer_url = producer_url
        self.bucket_name = bucket_name
        self.latest_hash = latest_hash
        self.feed_id = feed_id
        self.feed_stable_id = feed_stable_id
        self.execution_id = execution_id
        self.date = datetime.now().strftime('%Y%m%d%H%S')

        self.init_status = None
        self.init_status_additional_data = None

        # self.retrieve_feed_status()

    def process(self):
        """
        Process the dataset and store new version in GCP bucket if any changes are detected
        """
        dataset_file = self.upload_dataset()

        if dataset_file is None:
            logging.info(f'[{self.feed_stable_id}] Process completed. No database update required.')
            return
        # Allow exceptions to be raised
        self.create_dataset(dataset_file)
        # self.update_feed_status(Status.UPDATED)
        logging.info(f"[{self.feed_stable_id}] Process completed.")

    @staticmethod
    def create_dataset_stable_id(feed_stable_id, timestamp):
        """
        Creates a stable id for the dataset
        :param feed_stable_id: the feed's stable id
        :param timestamp: the timestamp of the dataset
        :return: the dataset's stable id
        """
        return f"{feed_stable_id}-{timestamp}"

    def download_content(self):
        """
        Downloads the content of a URL
        """
        return download_url_content(self.producer_url)

    def upload_dataset(self) -> DatasetFile or None:
        """
        Uploads a dataset to a GCP bucket as <stable_id>/latest.zip and <stable_id>/<upload_datetime>.zip
        if the dataset hash is different from the latest dataset stored
        :return: the file hash and the hosted url as a tuple
        """
        logging.info(f"[{self.feed_stable_id}] - Accessing URL {self.producer_url}")
        content = self.download_content()
        file_sha256_hash = sha256(content).hexdigest()
        logging.info(f"[{self.feed_stable_id}] File hash is {file_sha256_hash}.")

        if self.latest_hash != file_sha256_hash:
            logging.info(
                f"[{self.feed_stable_id}] Dataset has changed (hash {self.latest_hash}"
                f"-> {file_sha256_hash}). Uploading new version.")
            logging.info(f"Creating file {self.feed_stable_id}/latest.zip in bucket {self.bucket_name}")
            bucket = storage.Client().get_bucket(self.bucket_name)
            blob = bucket.blob(f"{self.feed_stable_id}/latest.zip")
            blob.upload_from_string(content, timeout=300)
            blob.make_public()

            dataset_stable_id = self.create_dataset_stable_id(self.feed_stable_id, self.date)

            logging.info(f"Creating file {self.feed_stable_id}/{dataset_stable_id}.zip in bucket {self.bucket_name}")
            timestamp_blob = bucket.blob(f"{self.feed_stable_id}/{dataset_stable_id}.zip")
            timestamp_blob.upload_from_string(content, timeout=300)
            timestamp_blob.make_public()
            return DatasetFile(stable_id=dataset_stable_id, file_sha256_hash=file_sha256_hash,
                               hosted_url=timestamp_blob.public_url)

        logging.info(
            f"[{self.feed_stable_id}] Datasets hash has not changed (hash {self.latest_hash} "
            f"-> {file_sha256_hash}). Not uploading it.")
        return None

    # def handle_error(self, e, errors):
    #     """
    #     Handles the error logs and updates the feed's status to "Failed"
    #     :param e: the thrown error
    #     :param errors: the error logs
    #     """
    #     error_traceback = traceback.format_exc()
    #     errors += f"[{self.feed_stable_id} ERROR]: {e} \t {error_traceback}"
    #
    #     print(f"Logging errors for stable id {self.feed_stable_id}: {errors}")
    #     # self.update_feed_status(Status.FAILED)

    def create_dataset(self, dataset_file: DatasetFile):
        """
        Handles the validation of the dataset including the upload of the dataset to GCP
        and the required database changes
        :param dataset_file: information about the dataset file
        """
        session = start_db_session(os.getenv("FEEDS_DATABASE_URL"))
        errors = ""
        try:
            # # Check latest version of the dataset
            latest_dataset = session.query(Gtfsdataset).filter_by(latest=True, feed_id=self.feed_id).one_or_none()
            if not latest_dataset:
                logging.info(f"[{self.feed_stable_id}] No latest dataset found for feed.")

            logging.info(f"[{self.feed_stable_id}] Creating new dataset for feed with stable id {dataset_file.stable_id}.")
            new_dataset = Gtfsdataset(id=str(uuid.uuid4()),
                                      feed_id=self.feed_id,
                                      stable_id=dataset_file.stable_id,
                                      latest=True,
                                      bounding_box=None,
                                      note=None,
                                      hash=dataset_file.file_sha256_hash, download_date=func.now(),
                                      hosted_url=dataset_file.hosted_url)
            if latest_dataset:
                latest_dataset.latest = False
                session.add(latest_dataset)
            session.add(new_dataset)

            session.commit()
            logging.info(f"[{self.feed_stable_id}] Processing completed successfully.")
        except Exception as e:
            if session is not None:
                session.rollback()
            raise Exception(f"Error creating dataset: {e}")
        finally:
            if session is not None:
                close_db_session(session)


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
    Logger.init_logger()
    logging.info(f'Function Started')
    stable_id = "UNKNOWN"
    execution_id = "UNKNOWN"
    bucket_name = os.getenv("DATASETS_BUCKET_NANE")
    start_db_session(os.getenv("FEEDS_DATABASE_URL"))
    try:
        #  Extract  data from message
        data = base64.b64decode(cloud_event.data["message"]["data"]).decode()
        json_payload = json.loads(data)
        logging.info(f"[{json_payload['feed_stable_id']}] JSON Payload: {json.dumps(json_payload)}")
        stable_id = json_payload["feed_stable_id"]
        execution_id = json_payload["execution_id"]
        processor = DatasetProcessor(json_payload["producer_url"], json_payload["feed_id"],
                                     stable_id, execution_id, json_payload["dataset_hash"], bucket_name)
        processor.process()
    except Exception as e:
        logging.error(e)
        logging.error(f'[{stable_id}] Function completed with error in execution: [{execution_id}]')
        return f'[{stable_id}] Function completed with error in execution: [{execution_id}]'

    logging.info(f'[{stable_id}] Function Completed Successfully in execution: [{execution_id}]')
    return 'Completed.'
