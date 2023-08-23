from google.cloud import storage
import functions_framework
import requests
from hashlib import md5
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


def get_file_md5_hash(bucket_name, file_name):
    """
    Returns file MD5 hash in hexadecimal format
    :param bucket_name: Name of the GCP bucket
    :param file_name: the file name
    :return: the hexadecimal format of the MD5 hash
    """
    # Retrieve file
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(file_name)
    blob.reload()

    # Get and decode the MD5 hash
    if blob.exists():
        md5_hash = blob.md5_hash
        hex_md5_hash = bytes.fromhex(md5_hash).hex()
        return hex_md5_hash
    else:
        print(f"File {file_name} does not exist in bucket {bucket_name}.")
        return 0


def upload_file_from_url(url, bucket_name, file_name):
    """
    Uploads a file to GCP bucket from a URL
    :param url: file url
    :param bucket_name: name of the GCP
    :param file_name: name of the file in GCP
    :return: the file hash
    """
    # Create a storage client
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(file_name)

    # Retrieve data
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, stream=True, headers=headers)
    content = response.content
    file_md5_hash = md5(content).hexdigest()
    print(f"File hash is {file_md5_hash}")

    # Upload file
    blob.upload_from_string(content)
    return file_md5_hash


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
    bucket_name = "mobility-datasets"
    url = "http://smttracker.com/downloads/gtfs/cascobaylines-portland-me-usa.zip"
    create_bucket(bucket_name)
    upload_file_from_url(url, bucket_name, "test/test.zip")
    # create_test_file(bucket_name, "test.txt")
    print("Hello we are inside the code")
    print("Redeployment test 2")
    print("Redeployment test 3")
    print(request)
    # Return an HTTP response
    return 'Function has run successfully yay'
