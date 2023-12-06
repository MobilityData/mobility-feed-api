import os

from google.cloud import storage
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import requests


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


def download_url_content(url, with_retry=False):
    """
    Downloads the content of a URL
    """
    # Fix DH Key issues in server side
    try:
        requests.packages.urllib3.disable_warnings()
        requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
        requests.packages.urllib3.contrib.pyopenssl.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
    except AttributeError:
        # no pyopenssl support used / needed / available
        pass
    headers = {
        'User-Agent':
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'
    }
    http_session = requests.Session()
    retry = Retry(
        total=1,
        backoff_factor=0.1,
        status_forcelist=[500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retry) if not with_retry else HTTPAdapter()
    http_session.mount('http://', adapter)
    http_session.mount('https://', adapter)
    try:
        response = http_session.get(url, headers=headers, verify=False, timeout=120, stream=True)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(e)
        raise Exception("Exception -- Connection timeout error")
