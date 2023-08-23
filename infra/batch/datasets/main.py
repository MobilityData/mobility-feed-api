import os
from datetime import datetime

from google.cloud import storage
import functions_framework
import requests
from hashlib import md5
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


def upload_dataset(url, bucket_name, stable_id):
    """
    Uploads a dataset to a GCP bucket
    :param url: dataset feed's producer url
    :param bucket_name: name of the GCP bucket
    :param stable_id: the dataset stable id
    :return: true if the dataset has been updated, false otherwise
    """
    # Retrieve data
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, stream=True, headers=headers)
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
        latest_hash = bytes.fromhex(blob.md5_hash).hex()
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
        timestamp = current_time.strftime("%Y%m%d%H%M%S")
        blob = bucket.blob(f"{stable_id}/{timestamp}.zip")
        blob.upload_from_string(content)
        return True
    return False


def create_bucket(bucket_name):
    storage_client = storage.Client()
    # Check if the bucket already exists
    bucket = storage_client.lookup_bucket(bucket_name)
    if bucket is None:
        # If not, create the bucket
        bucket = storage_client.create_bucket(bucket_name)
        print(f'Bucket {bucket} created.')
    else:
        print(f'Bucket {bucket_name} already exists.')


def create_test_file(bucket_name, file_name):
    # Create a storage client
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(file_name)

    # Write data to the blob
    blob.upload_from_string('Changing the content of the file test')


# Register an HTTP function with the Functions Framework
@functions_framework.http
def batch_dataset(request):
    bucket_name = "mobility-datasets" # TODO this should be an env variable
    create_bucket(bucket_name)

    POSTGRES_USER = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_DB = os.getenv("POSTGRES_DB")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST")

    SQLALCHEMY_DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=True)
    sql_statement = text("select stable_id, producer_url from feed where status='active' and authentication_type='0' limit 2")

    results = engine.execute(sql_statement).all()
    print(f"Retrieved {len(results)} active feeds.")

    for result in results:
        stable_id = result[0]
        producer_url = result[1]
        dataset_uploaded = upload_dataset(producer_url, bucket_name, stable_id)
        if dataset_uploaded:
            # TODO update hash in dataset table
            print("TODO update")

    return 'Completed datasets batch processing.'
