import base64
import gc
import json
import os
import traceback
import uuid
import functions_framework
import urllib3
from sqlalchemy import create_engine, text
from requests.exceptions import HTTPError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import requests
from google.cloud import storage
from datetime import datetime
from hashlib import sha256
from cloudevents.http import CloudEvent
from google.cloud import pubsub_v1


def upload_dataset(url, bucket_name, stable_id, latest_hash):
    """
    Uploads a dataset to a GCP bucket as <stable_id>/latest.zip and <stable_id>/<upload_date>.zip
    if the dataset hash is different from the latest dataset stored
    :param url: dataset feed's producer url
    :param bucket_name: name of the GCP bucket
    :param stable_id: the dataset stable id
    :param latest_hash: the latest dataset hash
    :return: the file hash and the hosted url as a tuple
    """
    # Fix DH Key issues in server side
    requests.packages.urllib3.disable_warnings()
    requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
    try:
        requests.packages.urllib3.contrib.pyopenssl.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
    except AttributeError:
        # no pyopenssl support used / needed / available
        pass

    # Retrieving dataset from producer's URL
    print(f"[{stable_id}, INFO] - Accessing URL {url}")
    headers = {
        'User-Agent':
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'
    }
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=0.1,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    response = session.get(url, headers=headers, verify=False, timeout=300, stream=True)
    response.raise_for_status()

    content = response.content
    file_sha256_hash = sha256(content).hexdigest()
    print(f"[{stable_id}, INFO] File hash is {file_sha256_hash}.")

    # Create a storage client
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(f"{stable_id}/latest.zip")

    if latest_hash != file_sha256_hash:
        print(f"[{stable_id}, INFO] Dataset with stable id {stable_id} has changed (hash {latest_hash} "
              f"-> {file_sha256_hash}). Uploading new version.")

        # Upload file as latest
        blob.upload_from_string(content)

        # Upload file as upload timestamp
        current_time = datetime.now()
        timestamp = current_time.strftime("%Y%m%d")
        timestamp_blob = bucket.blob(f"{stable_id}/{timestamp}.zip")
        timestamp_blob.upload_from_string(content)
        return file_sha256_hash, timestamp_blob.public_url

    else:
        print(f"[{stable_id}, INFO] Dataset with stable id {stable_id} has not changed (hash {latest_hash} "
              f"-> {file_sha256_hash}). Not uploading.")
        return file_sha256_hash, None


def validate_dataset_version(engine, json_payload, bucket_name):
    """
    Handles the validation of the dataset including the upload of the dataset to GCP
    and the required database changes
    :param engine: Database engine
    :param json_payload: Pub/Sub payload
    :param bucket_name: GCP bucket name
    """
    transaction = None
    connection = None
    errors = ""
    stable_id = None
    try:
        # Set up transaction for SQL updates
        connection = engine.connect()
        transaction = connection.begin()

        # Check latest version of the dataset
        producer_url, stable_id, feed_id, dataset_id, dataset_hash = json_payload["producer_url"], \
            json_payload["stable_id"], json_payload["feed_id"], json_payload["dataset_id"], json_payload["dataset_hash"]
        print(f"[{stable_id}, INFO] Dataset ID = {dataset_id}, Dataset Hash = {dataset_hash}")

        if dataset_id is None:
            print(f"[{stable_id}, INTERNAL ERROR] Couldn't find latest dataset related to feed_id {feed_id}\n")
            return
        if dataset_hash is None:
            print(f"[{stable_id}, WARNING] Dataset {dataset_id} for feed {feed_id} has a NULL hash.")

        sha256_file_hash, hosted_url = upload_dataset(producer_url, bucket_name, stable_id, dataset_hash)

        # Set the previous version latest field to false
        if dataset_hash is not None and dataset_hash != sha256_file_hash:
            sql_statement = f"update gtfsdataset set latest=false where id='{dataset_id}'"
            connection.execute(text(sql_statement))

        sql_statement = f"insert into gtfsdataset (id, feed_id, latest, bounding_box, note, hash, " \
                        f"download_date, stable_id, hosted_url) " \
                        f"select '{str(uuid.uuid4())}', feed_id, true, bounding_box, note, " \
                        f"'{sha256_file_hash}', NOW(), stable_id, '{hosted_url}' from " \
                        f"gtfsdataset where id='{dataset_id}'"

        # In case the dataset doesn't include a hash or the dataset was deleted from the bucket,
        # update the existing entity
        if dataset_hash is None or dataset_hash == sha256_file_hash:
            sql_statement = f"update gtfsdataset set hash='{sha256_file_hash}', hosted_url='{hosted_url}' where id='{dataset_id}'"
        connection.execute(text(sql_statement))

        # Commit transaction after every step has run successfully
        transaction.commit()
        print(f"[{stable_id}, INFO] Processing completed successfully.")
    except Exception as e:
        if transaction is not None:
            transaction.rollback()
        handle_error(bucket_name, e, errors, stable_id)
    finally:
        if connection is not None:
            connection.close()
        gc.collect()  # Free memory


def handle_error(bucket_name, e, errors, stable_id):
    """
    Persists error logs to GCP bucket
    :param bucket_name: Bucket name where the error logs are updates
    :param e: thrown error
    :param errors: error logs
    :param stable_id: Feed's stable ID
    """
    if stable_id is None:
        return
    error_traceback = traceback.format_exc()
    errors += f"[{stable_id}, ERROR]: {e}\n{error_traceback}\n"
    print(f"Logging errors for stable id {stable_id}\n{errors}")
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    error_type = 'other'
    if 'remaining connection slots are reserved for non-replication superuser connections' in errors:
        raise e  # Rethrow error to trigger retry process until a connection is available
    elif isinstance(e, HTTPError):
        error_type = f"http/{e.response.status_code}"
    blob = bucket.blob(f"errors/{datetime.now().strftime('%Y%m%d')}/{error_type}/{stable_id}.log")
    blob.upload_from_string(errors)


def create_bucket(bucket_name):
    """
    Creates GCP storage bucket if it doesn't exist
    :param bucket_name: name of the bucket to create
    """
    storage_client = storage.Client()
    bucket = storage_client.lookup_bucket(bucket_name)
    if bucket is None:
        bucket = storage_client.create_bucket(bucket_name)
        print(f'Bucket {bucket} created.')
    else:
        print(f'Bucket {bucket_name} already exists.')


def get_db_engine():
    """
    :return: Database engine
    """
    postgres_user = os.getenv("POSTGRES_USER")
    postgres_password = os.getenv("POSTGRES_PASSWORD")
    postgres_db = os.getenv("POSTGRES_DB")
    postgres_port = os.getenv("POSTGRES_PORT")
    postgres_host = os.getenv("POSTGRES_HOST")

    sqlalchemy_database_url = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}" \
                              f"/{postgres_db}"
    engine = create_engine(sqlalchemy_database_url, echo=True)
    return engine


@functions_framework.cloud_event
def process_dataset(cloud_event: CloudEvent):
    """
    Pub/Sub function entry point that processes a single dataset
    :param cloud_event: GCP Cloud Event
    """
    try:
        data = base64.b64decode(cloud_event.data["message"]["data"]).decode()
        json_payload = json.loads(data)
        stable_id = json_payload["stable_id"]
        print(f"[{stable_id}, INFO] JSON Payload:", json_payload)

        bucket_name = os.getenv("BUCKET_NAME")
        engine = get_db_engine()
        validate_dataset_version(engine, json_payload, bucket_name)
    except Exception as e:
        print("Could not parse JSON:", e)
        return f'[ERROR] Error processing request \n{e}\n{traceback.format_exc()}'
    return 'Done!'


@functions_framework.http
def batch_dataset(request):
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
                    "status='active' and authentication_type='0'"
    results = engine.execute(text(sql_statement)).all()
    print(f"Retrieved {len(results)} active feeds.")

    # Publish to topic for processing
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
