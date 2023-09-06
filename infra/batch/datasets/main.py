import base64
import gc
import json
import os
import time
import traceback
import uuid
import functions_framework
from sqlalchemy import create_engine, text
from aiohttp import ClientSession, TCPConnector
import asyncio
from requests.exceptions import HTTPError

import requests
from google.cloud import storage
from datetime import datetime
from hashlib import md5
from cloudevents.http import CloudEvent
from google.cloud import pubsub_v1


def upload_dataset(url, bucket_name, stable_id):
    """
    Uploads a dataset to a GCP bucket
    :param url: dataset feed's producer url
    :param bucket_name: name of the GCP bucket
    :param stable_id: the dataset stable id
    :return: the file hash and the hosted url as a tuple
    """
    headers = {
        'User-Agent':
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/39.0.2171.95 Safari/537.36'
    }
    response = requests.get(url, headers=headers, verify=False)
    print(response.status_code)
    response.raise_for_status()

    content = response.content
    file_md5_hash = md5(content).hexdigest()
    print(f"File hash is {file_md5_hash}.")

    # Create a storage client
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(f"{stable_id}/latest.zip")

    upload_file = False
    if blob.exists():
        # Validate change
        latest_hash = md5()
        with blob.open("rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                latest_hash.update(chunk)
        latest_hash = latest_hash.hexdigest()
        print(f"Latest hash is {latest_hash}.")
        if latest_hash != file_md5_hash:
            upload_file = True
    else:
        # Upload first version of dataset
        upload_file = True

    if upload_file:
        # Upload file as latest
        blob.upload_from_string(content)

        # Upload file as upload timestamp
        current_time = datetime.now()
        timestamp = current_time.strftime("%Y%m%d")
        timestamp_blob = bucket.blob(f"{stable_id}/{timestamp}.zip")
        timestamp_blob.upload_from_string(content)

        return file_md5_hash, timestamp_blob.public_url
    return file_md5_hash, None


def validate_dataset_version(engine, url, bucket_name, stable_id, feed_id):
    """
    Handles the validation of the dataset including the upload of the dataset to GCP
    and the required database changes
    :param engine: Database engine
    :param url: Producer URL
    :param bucket_name: GCP bucket name
    :param stable_id: Feed's stable ID
    :param feed_id: Feed's ID
    """
    transaction = None
    connection = None
    errors = ""
    try:
        md5_file_hash, hosted_url = upload_dataset(url, bucket_name, stable_id)

        # Set up transaction for SQL updates
        connection = engine.connect()
        transaction = connection.begin()

        # Create a new version of the dataset in the database
        select_dataset_statement = text(f"select id, hash from gtfsdataset where latest=true and feed_id='{feed_id}'")
        dataset_results = connection.execute(select_dataset_statement).all()
        dataset_id = dataset_results[0][0] if len(dataset_results) > 0 else None
        dataset_hash = dataset_results[0][1] if len(dataset_results) > 0 else None
        print(f"Dataset ID = {dataset_id}, Dataset Hash = {dataset_hash}")
        if dataset_id is None:
            errors += f"[INTERNAL ERROR] Couldn't find latest dataset related to feed_id {feed_id}\n"
            return

        # Set the previous version latest field to false
        if dataset_hash is not None and dataset_hash != md5_file_hash:
            sql_statement = f"update gtfsdataset set latest=false where id='{dataset_id}'"
            connection.execute(text(sql_statement))

        sql_statement = f"insert into gtfsdataset (id, feed_id, latest, bounding_box, note, hash, " \
                        f"download_date, stable_id, hosted_url) " \
                        f"select '{str(uuid.uuid4())}', feed_id, true, bounding_box, note, " \
                        f"'{md5_file_hash}', NOW(), stable_id, '{hosted_url}' from " \
                        f"gtfsdataset where id='{dataset_id}'"

        # In case the dataset doesn't include a hash or the dataset was deleted from the bucket,
        # update the existing entity
        if dataset_hash is None or dataset_hash == md5_file_hash:
            sql_statement = f"update gtfsdataset set hash='{md5_file_hash}', hosted_url={hosted_url} where id='{dataset_id}'"
        connection.execute(text(sql_statement))

        # Commit transaction after every step has run successfully
        transaction.commit()
    except Exception as e:
        if transaction is not None:
            transaction.rollback()
        error_traceback = traceback.format_exc()
        errors += f"[ERROR]: {e}\n{error_traceback}\n"
        print(f"Logging errors for stable id {stable_id}\n{errors}")
        storage_client = storage.Client()
        bucket = storage_client.get_bucket(bucket_name)
        error_type = f"http/{e.response.status_code}" if isinstance(e, HTTPError) else "other"
        blob = bucket.blob(f"errors/{datetime.now().strftime('%Y%m%d')}/{error_type}/{stable_id}.log")
        blob.upload_from_string(errors)
    finally:
        if connection is not None:
            connection.close()
        gc.collect()  # Free memory


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
    try:
        data = base64.b64decode(cloud_event.data["message"]["data"]).decode()
        json_payload = json.loads(data)
        producer_url, stable_id, feed_id = json_payload["producer_url"], json_payload["stable_id"], json_payload[
            "feed_id"]
        print("JSON Payload:", json_payload)

        bucket_name = os.getenv("BUCKET_NAME")
        engine = get_db_engine()
        validate_dataset_version(engine, producer_url, bucket_name, stable_id, feed_id)
    except Exception as e:
        print("Could not parse JSON:", e)
        return f'[ERROR] Error processing request \n{e}\n{traceback.format_exc()}'
    return 'Done!'


async def call_process_dataset(session, url, payload):
    async with session.post(url, json=payload, headers={'Content-Type': 'application/json'}) as response:
        return await response.text()


@functions_framework.http
def batch_dataset(request):
    bucket_name = os.getenv("BUCKET_NAME")
    create_bucket(bucket_name)

    engine = get_db_engine()
    sql_statement = "select stable_id, producer_url, gtfsfeed.id from feed join gtfsfeed on gtfsfeed.id=feed.id where " \
                    "status='active' and authentication_type='0'"

    results = engine.execute(text(sql_statement)).all()
    print(f"Retrieved {len(results)} active feeds.")

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path('mobility-feeds-dev', 'functions2-topic')

    # batch_count = 0
    for stable_id, producer_url, feed_id in results:
        payload = {
            "producer_url": producer_url,
            "stable_id": stable_id,
            "feed_id": feed_id
        }
        data_str = json.dumps(payload)
        data_bytes = data_str.encode('utf-8')
        publisher.publish(topic_path, data=data_bytes)
        # batch_count += 1
        # if batch_count >= 5:
        #     print("Published 5 messages, sleeping for 10 seconds...")
        #     time.sleep(5)
        #     batch_count = 0  # Reset counter after sleep

    return 'Completed datasets batch processing.'
