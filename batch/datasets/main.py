import base64
import json
import os
import traceback
import uuid
from datetime import datetime
from hashlib import sha256

import functions_framework
import requests
from cloudevents.http import CloudEvent
from google.cloud import pubsub_v1, datastore
from google.cloud import storage
from requests.adapters import HTTPAdapter
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker
from urllib3.util.retry import Retry

from database_gen.sqlacodegen_models import Gtfsfeed, Gtfsdataset, Feed
from helpers.utils import create_bucket, get_db_engine
from status import Status


class DatasetProcessor:
    def __init__(self, producer_url, stable_id, feed_id, dataset_id, bucket_name, latest_hash):
        self.producer_url = producer_url
        self.bucket_name = bucket_name
        self.stable_id = stable_id
        self.dataset_id = dataset_id
        self.latest_hash = latest_hash
        self.feed_id = feed_id
        self.storage_client = storage.Client()
        self.date = datetime.now().strftime('%Y%m%d')
        self.datastore = datastore.Client()

        self.init_status = None
        self.init_status_additional_data = None
        self.status_entity = None

        self.retrieve_feed_status()

    def process(self):
        """
        Process the dataset and store new version in GCP bucket if any changes are detected
        """
        try:
            # Validate that the feed wasn't previously processed
            print(f"[{self.stable_id} INFO] Feed status is {self.init_status}")

            if self.init_status and self.init_status != Status.PUBLISHED:
                print(f"[{self.stable_id} INFO] Feed was already processed")
                return

            if self.dataset_id is None:
                print(f"[{self.stable_id} INTERNAL ERROR] Couldn't find latest dataset related to feed_id.\n")
                self.update_feed_status(Status.FAILED)
                return

            sha256_file_hash, hosted_url = self.upload_dataset()

            if hosted_url is None:
                print(f'[{self.stable_id} INFO] Process completed. No database update required.')
        except Exception as e:
            self.handle_error(e, "")
            return

        if hosted_url is not None and sha256_file_hash is not None:
            # Allow exceptions to be raised
            self.validate_dataset_version(sha256_file_hash, hosted_url)
            self.update_feed_status(Status.UPDATED)
            print(f"[{self.stable_id} INFO] Process completed.")

    def upload_dataset(self):
        """
        Uploads a dataset to a GCP bucket as <stable_id>/latest.zip and <stable_id>/<upload_datetime>.zip
        if the dataset hash is different from the latest dataset stored
        :return: the file hash and the hosted url as a tuple
        """
        # Fix DH Key issues in server side
        try:
            requests.packages.urllib3.disable_warnings()
            requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
            requests.packages.urllib3.contrib.pyopenssl.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
        except AttributeError:
            # no pyopenssl support used / needed / available
            pass

        # Validate that the dataset wasn't previously uploaded
        if self.init_status == Status.PUBLISHED and self.init_status_additional_data is not None:
            return self.init_status_additional_data['file_sha256_hash'], self.init_status_additional_data['url']

        self.update_feed_status(Status.DO_NOT_RETRY)

        # Retrieving dataset from producer's URL
        print(f"[{self.stable_id} INFO] - Accessing URL {self.producer_url}")
        headers = {
            'User-Agent':
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'
        }
        session = requests.Session()
        retry = Retry(
            total=2,
            backoff_factor=0.1,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        try:
            response = session.get(self.producer_url, headers=headers, verify=False, timeout=120, stream=True)
        except OSError as e:
            print(e)
            raise Exception("OS Exception -- Connection timeout error")
        response.raise_for_status()

        content = response.content
        file_sha256_hash = sha256(content).hexdigest()
        print(f"[{self.stable_id} INFO] File hash is {file_sha256_hash}.")

        bucket = self.storage_client.get_bucket(self.bucket_name)
        blob = bucket.blob(f"{self.stable_id}/latest.zip")
        blob.make_public()

        if self.latest_hash != file_sha256_hash:
            print(
                f"[{self.stable_id} INFO] Dataset with stable id {self.stable_id} has changed (hash {self.latest_hash} "
                f"-> {file_sha256_hash}). Uploading new version.")

            # Upload file as latest
            blob.upload_from_string(content, timeout=300)

            # Upload file as upload timestamp
            current_time = datetime.now()
            timestamp = current_time.strftime("%Y%m%d_%H%M%S")
            timestamp_blob = bucket.blob(f"{self.stable_id}/{timestamp}.zip")
            timestamp_blob.upload_from_string(content, timeout=300)
            timestamp_blob.make_public()
            self.update_feed_status(
                Status.PUBLISHED,
                {
                    'file_sha256_hash': file_sha256_hash,
                    'url': timestamp_blob.public_url
                }
            )
            return file_sha256_hash, timestamp_blob.public_url

        else:
            print(
                f"[{self.stable_id} INFO] Dataset with stable id {self.stable_id} has not changed (hash {self.latest_hash} "
                f"-> {file_sha256_hash}). Not uploading.")
            self.update_feed_status(Status.NOT_UPDATED)
            return file_sha256_hash, None

    def retrieve_feed_status(self):
        """
        Retrieves the feed's status from GCP Datastore
        """
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        filters = [('stable_id', '=', self.stable_id), ('timestamp', '>=', today_start)]
        status_query = self.datastore.query(kind='historical_dataset_batch', filters=filters)

        docs = list(status_query.fetch())

        if len(docs) != 1:
            return

        self.status_entity = docs[0]
        status_code = self.status_entity.get('status', None)

        self.init_status = Status(status_code) if status_code is not None else None
        self.init_status_additional_data = self.status_entity.get('data', None)

    def update_feed_status(self, status: Status, extra_data=None):
        """
        Updates the feed's status in GCP Datastore
        """
        timestamp = datetime.utcnow()
        data = {
            'status': status.value.real,
            'timestamp': timestamp,
            'stable_id': self.stable_id
        }
        if extra_data is not None:
            data['data'] = extra_data

        with self.datastore.transaction():
            # No status was persisted today -- create new entity key
            if self.status_entity is None:
                status_entity_key = self.datastore.key('historical_dataset_batch')
                self.status_entity = datastore.Entity(key=status_entity_key, exclude_from_indexes=['data'])

            self.status_entity.update(data)
            self.datastore.put(self.status_entity)

    def handle_error(self, e, errors):
        """
        Handles the error logs and updates the feed's status to "Failed"
        :param e: the thrown error
        :param errors: the error logs
        """
        error_traceback = traceback.format_exc()
        errors += f"[{self.stable_id} ERROR]: {e} \t {error_traceback}"

        print(f"Logging errors for stable id {self.stable_id}: {errors}")
        self.update_feed_status(Status.FAILED)

    def validate_dataset_version(self, sha256_file_hash, hosted_url):
        """
        Handles the validation of the dataset including the upload of the dataset to GCP
        and the required database changes
        :param sha256_file_hash: Dataset's sha256 hash
        :param hosted_url: GCP URL hosting the dataset
        """
        Session = sessionmaker(bind=get_db_engine())
        session = Session()
        transaction = None
        errors = ""
        try:
            # Start a transaction
            transaction = session.begin_nested()

            # Check latest version of the dataset
            latest_dataset = session.query(Gtfsdataset).filter_by(id=self.dataset_id).one_or_none()
            if not latest_dataset:
                print(f"[{self.stable_id} INFO] No dataset found with id {self.dataset_id}")
                raise Exception(f"No dataset found with id {self.dataset_id}")

            print(f"[{self.stable_id} INFO] Dataset ID = {latest_dataset.id}, Dataset Hash = {latest_dataset.hash}")
            if latest_dataset.hash is None:
                print(
                    f"[{self.stable_id} WARNING] Dataset {latest_dataset.id} for feed {self.feed_id} has a NULL hash.")
            elif latest_dataset.hash != sha256_file_hash:
                latest_dataset.latest = False  # Set previous version 'latest' to False

            # Create or update the dataset
            if latest_dataset.hash != sha256_file_hash:
                new_dataset = Gtfsdataset(id=str(uuid.uuid4()), feed_id=self.feed_id, latest=True,
                                          bounding_box=latest_dataset.bounding_box if latest_dataset else None,
                                          note=latest_dataset.note if latest_dataset else None,
                                          hash=sha256_file_hash, download_date=func.now(),
                                          stable_id=self.stable_id, hosted_url=hosted_url)
                session.add(new_dataset)
            else:
                latest_dataset.hash = sha256_file_hash
                latest_dataset.hosted_url = hosted_url

            session.commit()
            print(f"[{self.stable_id} INFO] Processing completed successfully.")
        except Exception as e:
            pass
            if session is not None:
                session.rollback()
            self.handle_error(e, errors)
        finally:
            if session is not None:
                session.close()


@functions_framework.cloud_event
def process_dataset(cloud_event: CloudEvent):
    """
    Pub/Sub function entry point that processes a single dataset
    :param cloud_event: GCP Cloud Event
    """
    stable_id = "UNKNOWN"
    error_return_message = f'ERROR - Unsuccessful processing of dataset with stable id {stable_id}.'
    bucket_name = os.getenv("BUCKET_NAME")
    processor = None
    try:
        #  Extract  data from message
        data = base64.b64decode(cloud_event.data["message"]["data"]).decode()
        json_payload = json.loads(data)
        producer_url, stable_id, dataset_hash, dataset_id, feed_id = json_payload["producer_url"], json_payload["stable_id"], \
            json_payload["dataset_hash"], json_payload["dataset_id"], json_payload["feed_id"]

        print(f"[{stable_id} INFO] JSON Payload:", json_payload)

        processor = DatasetProcessor(producer_url, stable_id, feed_id, dataset_id, bucket_name, dataset_hash)
    except Exception as e:
        print(f'[{stable_id} ERROR] Error while uploading dataset\n {e} \n {traceback.format_exc()}')
        if processor is not None:
            processor.handle_error(e, "")
        return error_return_message

    if processor is not None:
        processor.process()

    return 'Completed.'


@functions_framework.http
def batch_datasets(request):
    """
    HTTP Function entry point that processes the datasets
    :param request: HTTP request
    """
    bucket_name = os.getenv("BUCKET_NAME")
    pubsub_topic_name = os.getenv("PUBSUB_TOPIC_NAME")
    project_id = os.getenv("PROJECT_ID")
    create_bucket(bucket_name)

    # Retrieve feeds
    Session = sessionmaker(bind=get_db_engine())
    session = Session()

    query = (
        session.query(
            Gtfsfeed.stable_id,
            Gtfsfeed.producer_url,
            Gtfsfeed.id,
            Gtfsdataset.id.label('dataset_id'),
            Gtfsdataset.hash
        )
        .select_from(Gtfsfeed)
        .outerjoin(Gtfsdataset, (Gtfsdataset.feed_id == Feed.id))
        .filter(Gtfsfeed.status == 'active', Gtfsfeed.authentication_type == '0')
        .filter(Gtfsdataset.id is not None, Gtfsdataset.latest.is_(True))
        .limit(10)
    )

    # Executing the query
    results = query.all()
    print(f"Retrieved {len(results)} active feeds.")

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, pubsub_topic_name)

    for stable_id, producer_url, feed_id, dataset_id, dataset_hash in results:
        # Retrieve latest dataset
        payload = {
            "producer_url": producer_url,
            "stable_id": stable_id,
            "feed_id": feed_id,
            "dataset_id": dataset_id,
            "dataset_hash": dataset_hash
        }
        data_str = json.dumps(payload)
        data_bytes = data_str.encode('utf-8')
        publisher.publish(topic_path, data=data_bytes)

    return f'Publish completed. Published {len(results)} feeds to {pubsub_topic_name}.'
