import base64
import json
import os
import traceback
import uuid
import functions_framework
from sqlalchemy import text
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from helpers.utils import create_bucket, get_db_engine

import requests
from google.cloud import storage
from datetime import datetime
from hashlib import sha256
from cloudevents.http import CloudEvent
from google.cloud import pubsub_v1, datastore
from status import Status


class DatasetProcessor:
    def __init__(self, producer_url, stable_id, feed_id, dataset_id, bucket_name, latest_hash, connection):
        self.producer_url = producer_url
        self.bucket_name = bucket_name
        self.stable_id = stable_id
        self.dataset_id = dataset_id
        self.latest_hash = latest_hash
        self.feed_id = feed_id
        self.storage_client = storage.Client()
        self.connection = connection
        self.date = datetime.now().strftime('%Y%m%d')
        self.datastore = datastore.Client()

        self.init_status = None
        self.init_status_additional_data = None
        self.status_entity_key = None

        self.retrieve_feed_state()

    def process(self):
        # Validate that the feed wasn't previously processed
        print(f"[{self.stable_id} INFO] Feed status is {self.init_status}")

        if self.init_status and self.init_status != Status.PUBLISHED:
            print(f"[{self.stable_id} INFO] Feed was already processed")
            return

        if self.dataset_id is None:
            print(f"[{self.stable_id} INTERNAL ERROR] Couldn't find latest dataset related to feed_id.\n")
            print(
                json.dumps(
                    {
                        "stable_id": self.stable_id,
                        "status": Status.FAILED.name,
                        "timestamp": self.date
                    }
                )
            )
            self.update_feed_status(Status.FAILED)
            return

        sha256_file_hash, hosted_url = self.upload_dataset()

        if hosted_url is None:
            print(f'[{self.stable_id} INFO] Process completed. No database update required.')
            print(json.dumps({
                "stable_id": self.stable_id,
                "status": Status.NOT_UPDATED.name,
                "timestamp": self.date
            }))
        if hosted_url is not None:
            self.validate_dataset_version(sha256_file_hash, hosted_url)
            print(json.dumps({
                "stable_id": self.stable_id,
                "status": Status.UPDATED.name,
                "timestamp": self.date
            }))
            self.update_feed_status(Status.UPDATED)

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
            self.update_feed_status(Status.NOT_UPDATED, self.bucket_name)
            return file_sha256_hash, None

    def retrieve_feed_state(self):
        """
        Retrieves the feed's state from the database
        """
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        status_query = self.datastore.query(kind='historical_dataset_batch')
        status_query.add_filter('stable_id', '=', self.stable_id)
        status_query.add_filter('timestamp', 'GREATER_THAN_OR_EQUAL', today_start)

        docs = list(status_query.fetch())
        print(f"{20 * '*'} The query results are --> {docs} {20 * '*'}")

        if len(docs) != 1:
            # No status was persisted today -- create new entity key
            self.status_entity_key = self.datastore.key('historical_dataset_batch')
            return

        print(f"{20 * '*'} The query single result are --> {docs[0]} {20 * '*'}")
        status_entity = docs[0]
        status_code = status_entity.get('status', None)

        self.init_status = Status(status_code) if status_code is not None else None
        self.init_status_additional_data = status_entity.get('data', None)
        self.status_entity_key = status_entity.key

    def update_feed_status(self, status: Status, extra_data=None):
        """
        Updates the feed's status in the database
        """
        timestamp = datetime.utcnow()
        data = {
            'state': status.value.real,
            'timestamp': timestamp,
            'run_id': uuid.uuid4().hex,
            'stable_id': self.stable_id
        }
        if extra_data is not None:
            data['data'] = extra_data

        with self.datastore.transaction():
            status = datastore.Entity(key=self.status_entity_key)
            status.update(data)
            self.datastore.put(status)

    def handle_error(self, e, errors):
        """
        Handles the error logs and updates the feed's status to failed
        :param bucket_name: Bucket name where the error logs are updates
        :param e: thrown error
        :param errors: error logs
        :param stable_id: Feed's stable ID
        """
        date = datetime.now().strftime('%Y%m%d')
        error_traceback = traceback.format_exc()
        errors += f"[{self.stable_id} ERROR]: {e} \t {error_traceback}"

        print(f"Logging errors for stable id {self.stable_id}: {errors}")

        print(json.dumps({
            "stable_id": self.stable_id,
            "status": Status.FAILED.name,
            "timestamp": date
        }))

        self.update_feed_status(Status.FAILED)

    def validate_dataset_version(self, sha256_file_hash, hosted_url):
        """
        Handles the validation of the dataset including the upload of the dataset to GCP
        and the required database changes
        :param sha256_file_hash: Dataset's sha256 hash
        :param hosted_url: GCP URL hosting the dataset
        """
        transaction = None
        errors = ""
        try:
            # Set up transaction for SQL updates
            transaction = self.connection.begin()

            # Check latest version of the dataset
            print(f"[{self.stable_id} INFO] Dataset ID = {self.dataset_id}, Dataset Hash = {self.latest_hash}")

            if self.latest_hash is None:
                print(f"[{self.stable_id} WARNING] Dataset {self.dataset_id} for feed {self.feed_id} has a NULL hash.")

            # Set the previous version latest field to false
            if self.latest_hash is not None and self.latest_hash != sha256_file_hash:
                sql_statement = f"update gtfsdataset set latest=false where id='{self.dataset_id}'"
                self.connection.execute(text(sql_statement))

            sql_statement = f"insert into gtfsdataset (id, feed_id, latest, bounding_box, note, hash, " \
                            f"download_date, stable_id, hosted_url) " \
                            f"select '{str(uuid.uuid4())}', feed_id, true, bounding_box, note, " \
                            f"'{sha256_file_hash}', NOW(), stable_id, '{hosted_url}' from " \
                            f"gtfsdataset where id='{self.dataset_id}'"

            # In case the dataset doesn't include a hash or the dataset was deleted from the bucket,
            # update the existing entity
            if self.latest_hash is None or self.latest_hash == sha256_file_hash:
                sql_statement = f"update gtfsdataset set hash='{sha256_file_hash}', hosted_url='{hosted_url}' where id='{self.dataset_id}'"
            self.connection.execute(text(sql_statement))

            # Commit transaction after every step has run successfully
            transaction.commit()
            print(f"[{self.stable_id} INFO] Processing completed successfully.")
        except Exception as e:
            pass
            if transaction is not None:
                transaction.rollback()
            self.handle_error(e, errors)
        finally:
            if self.connection is not None:
                self.connection.close()


@functions_framework.cloud_event
def process_dataset(cloud_event: CloudEvent):
    """
    Pub/Sub function entry point that processes a single dataset
    :param cloud_event: GCP Cloud Event
    """
    stable_id = "UNKNOWN"
    error_return_message = f'ERROR - Unsuccessful processing of dataset with stable id {stable_id}.'
    bucket_name = os.getenv("BUCKET_NAME")

    # Allow raised exception to trigger the retry process until a connection is available
    engine = get_db_engine()
    connection = engine.connect()
    processor = None
    try:
        #  Extract  data from message
        data = base64.b64decode(cloud_event.data["message"]["data"]).decode()
        json_payload = json.loads(data)
        producer_url, stable_id, dataset_hash, dataset_id, feed_id = json_payload["producer_url"], json_payload["stable_id"], \
            json_payload["dataset_hash"], json_payload["dataset_id"], json_payload["feed_id"]

        print(f"[{stable_id} INFO] JSON Payload:", json_payload)

        processor = DatasetProcessor(producer_url, stable_id, feed_id, dataset_id, bucket_name, dataset_hash, connection)
        processor.process()
    except Exception as e:
        print(f'[{stable_id} ERROR] Error while uploading dataset\n {e} \n {traceback.format_exc()}')
        if processor is not None:
            processor.handle_error(e, "")
        return error_return_message
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
    engine = get_db_engine()
    sql_statement = "select stable_id, producer_url, gtfsfeed.id from feed join gtfsfeed on gtfsfeed.id=feed.id where " \
                    "status='active' and authentication_type='0' limit 1"
    results = engine.execute(text(sql_statement)).all()
    print(f"Retrieved {len(results)} active feeds.")

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, pubsub_topic_name)
    for stable_id, producer_url, feed_id in results:
        # Retrieve latest dataset
        select_dataset_statement = text(f"select id, hash from gtfsdataset where latest=true and feed_id='{feed_id}'")
        dataset_results = engine.execute(select_dataset_statement).all()
        dataset_id = dataset_results[0][0] if len(dataset_results) > 0 else None
        dataset_hash = dataset_results[0][1] if len(dataset_results) > 0 else None

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
