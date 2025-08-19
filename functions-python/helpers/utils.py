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
import hashlib
import logging
import os
import ssl

import requests
import urllib3
from google.cloud import storage
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.util.ssl_ import create_urllib3_context


def create_bucket(bucket_name):
    """
    Creates GCP storage bucket if it doesn't exist
    :param bucket_name: name of the bucket to create
    """
    storage_client = storage.Client()
    bucket = storage_client.lookup_bucket(bucket_name)
    if bucket is None:
        bucket = storage_client.create_bucket(bucket_name)
        logging.info(f"Bucket {bucket} created.")
    else:
        logging.info(f"Bucket {bucket_name} already exists.")


def download_url_content(url, with_retry=False):
    """
    Downloads the content of a URL
    """
    # Fix DH Key issues in server side
    try:
        requests.packages.urllib3.disable_warnings()
        requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += ":HIGH:!DH:!aNULL"
        requests.packages.urllib3.contrib.pyopenssl.util.ssl_.DEFAULT_CIPHERS += (
            ":HIGH:!DH:!aNULL"
        )
    except AttributeError:
        # no pyopenssl support used / needed / available
        pass
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
    }
    http_session = requests.Session()
    retry = Retry(
        total=1,
        backoff_factor=0.1,
        status_forcelist=[500, 502, 503, 504],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry) if not with_retry else HTTPAdapter()
    http_session.mount("http://", adapter)
    http_session.mount("https://", adapter)
    try:
        response = http_session.get(
            url, headers=headers, verify=False, timeout=120, stream=True
        )
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(e)
        raise e


def get_hash_from_file(file_path, hash_algorithm="sha256", chunk_size=8192):
    """
    Returns the hash of a file
    """
    hash_object = hashlib.new(hash_algorithm)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hash_object.update(chunk)
    return hash_object.hexdigest()


def download_and_get_hash(
    url,
    file_path,
    hash_algorithm="sha256",
    chunk_size=8192,
    authentication_type=0,
    api_key_parameter_name=None,
    credentials=None,
    logger=None,
    trusted_certs=False,  # If True, disables SSL verification
):
    """
    Downloads the content of a URL and stores it in a file and returns the hash of the file
    """
    logger = logger or logging.getLogger(__name__)
    try:
        hash_object = hashlib.new(hash_algorithm)

        # This the only way to make urllib3 work with legacy servers
        # More information: https://github.com/urllib3/urllib3/issues/2653#issuecomment-1165418616
        ctx = create_urllib3_context()
        ctx.load_default_certs()
        ctx.options |= 0x4  # ssl.OP_LEGACY_SERVER_CONNECT

        # authentication_type == 1 -> the credentials are passed in the url
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Mobile Safari/537.36"
        }
        # Careful, some URLs may already contain a query string
        # (e.g. http://api.511.org/transit/datafeeds?operator_id=CE)
        if authentication_type == 1 and api_key_parameter_name and credentials:
            separator = "&" if "?" in url else "?"
            url += f"{separator}{api_key_parameter_name}={credentials}"

        # authentication_type == 2 -> the credentials are passed in the header
        if authentication_type == 2 and api_key_parameter_name and credentials:
            headers[api_key_parameter_name] = credentials

        if trusted_certs:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        with urllib3.PoolManager(ssl_context=ctx) as http:
            with http.request(
                "GET", url, preload_content=False, headers=headers, redirect=True
            ) as r, open(file_path, "wb") as out_file:
                if 200 <= r.status < 300:
                    logger.info(f"HTTP response code: [{r.status}]")
                    while True:
                        data = r.read(chunk_size)
                        if not data:
                            break
                        hash_object.update(data)
                        out_file.write(data)
                    r.release_conn()
                else:
                    raise ValueError(f"Invalid HTTP response code: [{r.status}]")
        return hash_object.hexdigest()
    except Exception as e:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                logger.error(f"Delete file: [{file_path}]")

        raise e


def create_http_task(
    client,  # type: tasks_v2.CloudTasksClient
    body: bytes,
    url: str,
    project_id: str,
    gcp_region: str,
    queue_name: str,
) -> None:
    from shared.common.gcp_utils import create_http_task_with_name
    from google.cloud import tasks_v2
    from google.protobuf import timestamp_pb2

    proto_time = timestamp_pb2.Timestamp()
    proto_time.GetCurrentTime()

    create_http_task_with_name(
        client=client,
        body=body,
        url=url,
        project_id=project_id,
        gcp_region=gcp_region,
        queue_name=queue_name,
        task_name=None,  # No specific task name provided
        task_time=proto_time,
        http_method=tasks_v2.HttpMethod.POST,
    )
