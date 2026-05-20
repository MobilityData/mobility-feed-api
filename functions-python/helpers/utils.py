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
import time
import urllib3.exceptions
from datetime import date, datetime, timezone
from logging import Logger
from typing import Optional

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.util.ssl_ import create_urllib3_context
from pathlib import Path


def create_bucket(bucket_name):
    """
    Creates GCP storage bucket if it doesn't exist
    :param bucket_name: name of the bucket to create
    """
    from google.cloud import storage

    storage_client = storage.Client()
    bucket = storage_client.lookup_bucket(bucket_name)
    if bucket is None:
        bucket = storage_client.create_bucket(bucket_name)
        logging.info(f"Bucket {bucket} created.")
    else:
        logging.info(f"Bucket {bucket_name} already exists.")


def download_from_gcs(bucket_name: str, blob_path: str, local_path: str) -> str:
    """
    Download a file from GCS to a local path.

    Args:
        bucket_name: Name of the bucket (e.g. "my-bucket")
        blob_path: Path to the file in the bucket (e.g. "folder1/file.txt")
        local_path: Where to save locally (e.g. "/tmp/file.txt")

    Returns:
        The absolute path to the downloaded file.
    """
    from google.cloud import storage

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_path)

    Path(local_path).parent.mkdir(
        parents=True, exist_ok=True
    )  # Create parent directories if they don't exist
    blob.download_to_filename(local_path)

    return str(Path(local_path).resolve())


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


def create_feed_ssl_context(trusted_certs: bool = False):
    """
    Create a urllib3 SSL context suitable for GTFS feed HTTP requests.

    Enables legacy server connect (ssl.OP_LEGACY_SERVER_CONNECT) to handle
    servers with DH key issues. When trusted_certs=True, hostname verification
    and certificate validation are disabled (use only for known problematic feeds).
    """
    ctx = create_urllib3_context()
    ctx.load_default_certs()
    # This is the only way to make urllib3 work with legacy servers
    # More information: https://github.com/urllib3/urllib3/issues/2653#issuecomment-1165418616
    ctx.options |= 0x4  # ssl.OP_LEGACY_SERVER_CONNECT
    if trusted_certs:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def build_feed_request_params(
    url: str,
    feed_id: Optional[str] = None,
    authentication_type=0,
    api_key_parameter_name: Optional[str] = None,
    credentials: Optional[str] = None,
) -> tuple:
    """
    Build HTTP request headers and resolve the final URL for a feed request.

    Handles:
    - Per-feed User-Agent overrides via config DB (feed_download/http_headers)
    - Default mobile browser User-Agent + Referer fallback
    - Auth type 1: API key appended as a URL query parameter
    - Auth type 2: API key injected as a request header

    Returns:
        (headers, resolved_url) ready to pass to any HTTP method.
    """
    from shared.common.config_reader import get_config_value

    headers = get_config_value(
        namespace="feed_download", key="http_headers", feed_id=feed_id
    )
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Mobile Safari/537.36",
            "Referer": url,
        }

    auth_type = int(authentication_type) if authentication_type is not None else 0

    # authentication_type == 1 -> the credentials are passed in the url
    # Careful, some URLs may already contain a query string
    # (e.g. http://api.511.org/transit/datafeeds?operator_id=CE)
    if auth_type == 1 and api_key_parameter_name and credentials:
        separator = "&" if "?" in url else "?"
        url += f"{separator}{api_key_parameter_name}={credentials}"

    # authentication_type == 2 -> the credentials are passed in the header
    if auth_type == 2 and api_key_parameter_name and credentials:
        headers[api_key_parameter_name] = credentials

    return headers, url


_ZIP_CONTENT_TYPES = frozenset(
    {
        "application/zip",
        "application/x-zip",
        "application/x-zip-compressed",
        "application/gtfs+zip",
    }
)
_ZIP_MAGIC = b"\x50\x4b\x03\x04"  # PK\x03\x04 — ZIP local file header signature


def _parse_content_type(raw: Optional[str]) -> Optional[str]:
    """Return the normalised MIME type from a raw Content-Type header, or None."""
    if not raw:
        return None
    return raw.split(";")[0].strip().lower()


def _is_zip_from_content_type(content_type: Optional[str]) -> Optional[bool]:
    """Infer is_zip from a normalised Content-Type string.

    Returns True/False for known types, None for ambiguous ones
    (e.g. application/octet-stream) where magic-byte verification is needed.
    """
    if content_type is None:
        return None
    if content_type in _ZIP_CONTENT_TYPES:
        return True
    if content_type == "application/octet-stream":
        return None  # ambiguous — caller should verify via magic bytes
    return False


def perform_head_request(
    feed_id: str,
    stable_id: str,
    producer_url: str,
    authentication_type: str,
    api_key_parameter_name: Optional[str],
    credentials: Optional[str],
    timeout_seconds: int,
    request_type: str = "http_head",
    fallback_to_get: bool = False,
):
    """Execute an HTTP HEAD request for a single feed and return an unsaved model instance.

    Handles authentication, user-agent, and legacy SSL — identical to the GET path
    in download_and_get_hash, just using HEAD instead.

    When fallback_to_get=True and HEAD fails (any non-2xx or exception), a lightweight
    GET request is made instead: only the first 4 bytes of the body are read to check
    for the ZIP magic signature (PK\\x03\\x04), then the connection is released.
    The stored request_type reflects which method produced the final result.

    Note: request_url in the result is always the original producer_url (never the
    credential-bearing resolved URL) to avoid persisting secrets.
    """
    from shared.database_gen.sqlacodegen_models import GtfsFeedAvailabilityCheck

    checked_at = datetime.now(timezone.utc)
    status_code = None
    latency_ms = None
    error_message = None
    error_type = None
    success = False
    content_type = None
    is_zip = None
    actual_request_type = request_type  # may be overridden to "http_get" on fallback
    headers = None
    resolved_url = producer_url

    try:
        headers, resolved_url = build_feed_request_params(
            producer_url,
            feed_id=feed_id,
            authentication_type=authentication_type,
            api_key_parameter_name=api_key_parameter_name,
            credentials=credentials,
        )
        ctx = create_feed_ssl_context()
        start = time.monotonic()
        with urllib3.PoolManager(ssl_context=ctx) as http:
            r = http.request(
                "HEAD",
                resolved_url,
                headers=headers,
                redirect=True,
                timeout=urllib3.Timeout(connect=timeout_seconds, read=timeout_seconds),
            )
        latency_ms = int((time.monotonic() - start) * 1000)
        status_code = r.status
        success = status_code < 400
        content_type = _parse_content_type(r.headers.get("Content-Type"))
        is_zip = _is_zip_from_content_type(content_type)
    except urllib3.exceptions.MaxRetryError as exc:
        error_type = "ConnectionError"
        error_message = str(exc)
        logging.warning(
            "Connection error for feed %s (%s): %s", stable_id, producer_url, exc
        )
    except urllib3.exceptions.TimeoutError as exc:
        error_type = "Timeout"
        error_message = str(exc)
        logging.warning(
            "Timeout checking feed %s (%s): %s", stable_id, producer_url, exc
        )
    except urllib3.exceptions.HTTPError as exc:
        error_type = type(exc).__name__
        error_message = str(exc)
        logging.warning("HTTP error for feed %s (%s): %s", stable_id, producer_url, exc)

    if not success and fallback_to_get:
        logging.info(
            "HEAD failed for feed %s (%s) [status=%s error=%s], trying GET fallback",
            stable_id,
            producer_url,
            status_code,
            error_type,
        )
        actual_request_type = "http_get"
        status_code = None
        latency_ms = None
        error_message = None
        error_type = None
        content_type = None
        is_zip = None
        success = False
        try:
            ctx = create_feed_ssl_context()
            start = time.monotonic()
            with urllib3.PoolManager(ssl_context=ctx) as http:
                r = http.request(
                    "GET",
                    resolved_url,
                    headers=headers,
                    redirect=True,
                    preload_content=False,
                    timeout=urllib3.Timeout(
                        connect=timeout_seconds, read=timeout_seconds
                    ),
                )
                latency_ms = int((time.monotonic() - start) * 1000)
                status_code = r.status
                success = status_code < 400
                content_type = _parse_content_type(r.headers.get("Content-Type"))
                first_bytes = r.read(4)
                r.release_conn()
            is_zip = (
                first_bytes == _ZIP_MAGIC
                if first_bytes
                else _is_zip_from_content_type(content_type)
            )
        except urllib3.exceptions.MaxRetryError as exc:
            error_type = "ConnectionError"
            error_message = str(exc)
            logging.warning(
                "GET fallback connection error for feed %s (%s): %s",
                stable_id,
                producer_url,
                exc,
            )
        except urllib3.exceptions.TimeoutError as exc:
            error_type = "Timeout"
            error_message = str(exc)
            logging.warning(
                "GET fallback timeout for feed %s (%s): %s",
                stable_id,
                producer_url,
                exc,
            )
        except urllib3.exceptions.HTTPError as exc:
            error_type = type(exc).__name__
            error_message = str(exc)
            logging.warning(
                "GET fallback HTTP error for feed %s (%s): %s",
                stable_id,
                producer_url,
                exc,
            )

    return GtfsFeedAvailabilityCheck(
        feed_id=feed_id,
        checked_at=checked_at,
        request_url=producer_url,
        request_type=actual_request_type,
        status_code=status_code,
        latency_ms=latency_ms,
        error_message=error_message,
        error_type=error_type,
        success=success,
        content_type=content_type,
        is_zip=is_zip,
    )


def download_and_get_hash(
    url,
    file_path,
    hash_algorithm="sha256",
    chunk_size=8192,
    feed_id=None,
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

        ctx = create_feed_ssl_context(trusted_certs=trusted_certs)

        headers, url = build_feed_request_params(
            url,
            feed_id=feed_id,
            authentication_type=authentication_type,
            api_key_parameter_name=api_key_parameter_name,
            credentials=credentials,
        )

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
    timeout_s: int = 1800,  # 30 minutes
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
        timeout_s=timeout_s,
    )


def create_http_pmtiles_builder_task(
    stable_id: str,
    dataset_stable_id: str,
) -> None:
    """
    Create a task to generate PMTiles for a dataset.
    """
    from google.cloud import tasks_v2
    import json

    client = tasks_v2.CloudTasksClient()
    body = json.dumps(
        {"feed_stable_id": stable_id, "dataset_stable_id": dataset_stable_id}
    ).encode()
    queue_name = os.getenv("PMTILES_BUILDER_QUEUE")
    project_id = os.getenv("PROJECT_ID")
    gcp_region = os.getenv("GCP_REGION")
    gcp_env = os.getenv("ENVIRONMENT")

    create_http_task(
        client,
        body,
        f"https://{gcp_region}-{project_id}.cloudfunctions.net/pmtiles-builder-{gcp_env}",
        project_id,
        gcp_region,
        queue_name,
    )


def get_execution_id(json_payload: dict, stable_id: Optional[str]) -> str:
    """
    Extracts the execution_id from the JSON payload.
    If not present, defaults to today's date in YYYY-MM-DD format followed by a hyphen and the stable_id if provided.
    """
    execution_id = json_payload.get("execution_id")
    if not execution_id:
        execution_id = f"{str(date.today())}"
        if stable_id:
            execution_id += f"-{stable_id}"
        else:
            # Even this should not happen, but just in case we are defaulting it to the current time
            execution_id += f"-{datetime.now().strftime('%H:%M:%S')}"
    return execution_id


def check_maximum_executions(
    execution_id: str, stable_id: str, logger: Logger, maximum_executions: int = 1
) -> str:
    """
    Checks if the dataset has been executed more than the maximum allowed times.
    If it has, returns an error message; otherwise, returns None.
    :param execution_id: The ID of the execution.
    :param stable_id: The stable ID of the dataset.
    :param logger: Logger instance to log messages.
    :param maximum_executions: The maximum number of allowed executions.
    :return: Error message if the maximum executions are exceeded, otherwise None.
    """
    from shared.dataset_service.main import DatasetTraceService

    trace_service = DatasetTraceService()
    trace = trace_service.get_by_execution_and_stable_ids(execution_id, stable_id)
    executions = len(trace) if trace else 0
    logger.info(
        f"Function executed times={executions}/{maximum_executions} "
        f"in execution=[{execution_id}] "
    )

    if executions > 0:
        if executions >= maximum_executions:
            message = (
                f"Function already executed maximum times "
                f"in execution: [{execution_id}]"
            )
            logger.warning(message)
            return message
    return None


def record_execution_trace(
    execution_id,
    stable_id,
    status,
    logger=None,
    dataset_file=None,
    error_message=None,
):
    """
    Record the trace in the datastore
    """
    from shared.dataset_service.main import DatasetTraceService
    from shared.dataset_service.dataset_service_commons import DatasetTrace
    from shared.helpers.logger import get_logger

    trace_service = DatasetTraceService()

    (logger if logger else get_logger()).info(
        f"Recording trace in execution: [{execution_id}] with status: [{status}]"
    )
    trace = DatasetTrace(
        trace_id=None,
        stable_id=stable_id,
        status=status,
        execution_id=execution_id,
        file_sha256_hash=dataset_file.file_sha256_hash if dataset_file else None,
        hosted_url=dataset_file.hosted_url if dataset_file else None,
        error_message=error_message,
        timestamp=datetime.now(),
    )
    trace_service.save(trace)


def detect_encoding(
    filename: str, sample_size: int = 100_000, logger: Optional[logging.Logger] = None
) -> str:
    """Detect file encoding using a small sample of the file.
    If detections fails or if UTF-8 is detected, defaults to 'utf-8-sig' to handle BOM.
    """
    from charset_normalizer import from_bytes

    with open(filename, "rb") as f:
        raw = f.read(sample_size)
    result = from_bytes(raw).best()

    if result is None:
        logger = logger or logging.getLogger(__name__)
        logger.warning(
            "Encoding detection failed for %s, defaulting to utf-8-sig", filename
        )
        return "utf-8-sig"

    enc = result.encoding.lower()

    # If UTF-8 is detected, always use utf-8-sig to strip BOM if present
    # Treat ascii as UTF-8, since it's a subset of UTF-8 and it will prevent errors where UTF-8 characters are present
    # after the first 100K characters of the file.
    if enc in ("ascii", "utf_8", "utf-8", "utf8", "utf8mb4"):
        return "utf-8-sig"

    return enc
