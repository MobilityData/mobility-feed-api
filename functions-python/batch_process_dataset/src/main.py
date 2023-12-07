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
from dataset_service.main import DatasetTraceService, DatasetTrace, Status
from helpers.database import start_db_session, close_db_session
import logging

from helpers.logger import Logger
from helpers.utils import download_url_content


@dataclass
class DatasetFile:
    """
    Dataset file information
    """
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
        Uploads a dataset to a GCP bucket as <feed_stable_id>/latest.zip and
        <feed_stable_id>/<feed_stable_id>-<upload_datetime>.zip
        if the dataset hash is different from the latest dataset stored
        :return: the file hash and the hosted url as a tuple or None if no upload is required
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

    def create_dataset(self, dataset_file: DatasetFile):
        """
        Creates a new dataset in the database
        """
        session = start_db_session(os.getenv("FEEDS_DATABASE_URL"))
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
            logging.info(f"[{self.feed_stable_id}] Dataset created successfully.")
        except Exception as e:
            if session is not None:
                session.rollback()
            raise Exception(f"Error creating dataset: {e}")
        finally:
            if session is not None:
                close_db_session(session)

    def process(self) -> DatasetFile or None:
        """
        Process the dataset and store new version in GCP bucket if any changes are detected
        :return: the file hash and the hosted url as a tuple or None if no upload is required
        """
        dataset_file = self.upload_dataset()

        if dataset_file is None:
            logging.info(f'[{self.feed_stable_id}] No database update required.')
            return None
        self.create_dataset(dataset_file)
        return dataset_file


def record_trace(execution_id, stable_id, status, dataset_file, error_message, trace_service):
    """
    Record the trace in the datastore
    """
    logging.info(f'[{stable_id}] Recording trace in execution: [{execution_id}] with status: [{status}]')
    trace = DatasetTrace(trace_id=None, stable_id=stable_id, status=status,
                         execution_id=execution_id,
                         file_sha256_hash=dataset_file.file_sha256_hash if dataset_file else None,
                         hosted_url=dataset_file.hosted_url if dataset_file else None,
                         error_message=error_message,
                         timestamp=datetime.now())
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
    Logger.init_logger()
    logging.info(f'Function Started')
    stable_id = "UNKNOWN"
    execution_id = "UNKNOWN"
    bucket_name = os.getenv("DATASETS_BUCKET_NANE")
    start_db_session(os.getenv("FEEDS_DATABASE_URL"))
    maximum_executions = os.getenv("MAXIMUM_EXECUTIONS", 2)
    trace_service = None
    dataset_file: DatasetFile = None
    error_message = None
    try:
        #  Extract  data from message
        data = base64.b64decode(cloud_event.data["message"]["data"]).decode()
        json_payload = json.loads(data)
        logging.info(f"[{json_payload['feed_stable_id']}] JSON Payload: {json.dumps(json_payload)}")
        stable_id = json_payload["feed_stable_id"]
        execution_id = json_payload["execution_id"]
        trace_service = DatasetTraceService()
        trace = trace_service.get_by_execution_and_stable_ids(execution_id, stable_id)
        executions = len(trace) if trace else 0
        logging.info(f'[{stable_id}] Dataset executed times={executions} in execution=[{execution_id}] ')
        if executions > 0:
            if executions >= maximum_executions:
                error_message = f'[{stable_id}] Function already executed maximum times in execution: [{execution_id}]'
                logging.error(error_message)
                return error_message

        processor = DatasetProcessor(json_payload["producer_url"], json_payload["feed_id"],
                                     stable_id, execution_id, json_payload["dataset_hash"], bucket_name)
        dataset_file = processor.process()
    except Exception as e:
        logging.error(e)
        error_message = f'[{stable_id}] Function completed with error_message in execution: [{execution_id}]'
        logging.error(error_message)
    finally:
        if stable_id and execution_id:
            status = Status.PUBLISHED if dataset_file is not None else Status.NOT_PUBLISHED
            if error_message:
                status = Status.FAILED
            record_trace(execution_id, stable_id, status, dataset_file, error_message, trace_service)
        else:
            logging.error(f'Function completed with errors, missing stable={stable_id} or execution_id={execution_id}')
            return f'Function completed with errors, missing stable={stable_id} or execution_id={execution_id}'
    logging.info(f'[{stable_id}] Function Completed Successfully in execution: [{execution_id}]')
    return 'Completed.' if error_message is None else error_message
