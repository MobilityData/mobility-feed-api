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
import zipfile
import urllib3.exceptions
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from logging import Logger
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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


def get_feed_credentials(stable_id: str) -> Optional[str]:
    """Return the API credential for a feed from the FEEDS_CREDENTIALS env var, or None."""
    try:
        import json

        feeds_credentials = json.loads(os.getenv("FEEDS_CREDENTIALS", "{}"))
        return feeds_credentials.get(stable_id, None)
    except Exception as exc:
        logging.warning("Could not parse FEEDS_CREDENTIALS: %s", exc)
        return None


def _get_http_headers_override(feed_id: Optional[str]) -> Optional[dict]:
    """Return the feed_download/http_headers config override, or None.

    Returns None when the config database is unreachable so that callers fall back to
    the default headers instead of failing. This keeps the local verifier script usable
    without a database.
    """
    try:
        from shared.common.config_reader import get_config_value

        return get_config_value(
            namespace="feed_download", key="http_headers", feed_id=feed_id
        )
    except Exception as exc:
        logging.warning(
            "Could not read feed_download/http_headers for feed %s, "
            "falling back to default headers: %s",
            feed_id,
            exc,
        )
        return None


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
    headers = _get_http_headers_override(feed_id)
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Mobile Safari/537.36",
            "Referer": url,
        }

    try:
        auth_type = int(authentication_type) if authentication_type is not None else 0
    except (ValueError, TypeError):
        logging.warning(
            "Invalid authentication_type %r for feed %s, defaulting to 0 (no auth)",
            authentication_type,
            feed_id,
        )
        auth_type = 0

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


def _log_redirects(stable_id: str, producer_url: str, redirect_urls: list) -> None:
    """Log redirect URLs that differ from the original producer_url."""
    unique = [u for u in dict.fromkeys(redirect_urls) if u != producer_url]
    if unique:
        logging.info(
            "Feed %s (%s) redirected through: %s", stable_id, producer_url, unique
        )


def _sanitize_error_message(
    message: Optional[str], resolved_url: str, producer_url: str
) -> Optional[str]:
    """Replace resolved_url (may contain credentials) with producer_url in error messages."""
    if message and resolved_url != producer_url:
        return message.replace(resolved_url, producer_url)
    return message


REDACTED = "***REDACTED***"

_SECRET_HEADER_NAMES = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "api-key",
        "apikey",
        "token",
        "access-token",
        "x-access-token",
        "x-auth-token",
    }
)


def _is_secret_name(name: str, api_key_parameter_name: Optional[str] = None) -> bool:
    """Return True when a header or query parameter name carries a credential.

    Underscores and hyphens are treated as equivalent so that both api_key and api-key
    are matched.
    """
    lowered = name.strip().lower()
    if lowered.replace("_", "-") in _SECRET_HEADER_NAMES:
        return True
    if not api_key_parameter_name:
        return False
    return lowered.replace("_", "-") == api_key_parameter_name.strip().lower().replace(
        "_", "-"
    )


def sanitize_headers(
    headers: Optional[dict], api_key_parameter_name: Optional[str] = None
) -> Optional[dict]:
    """Return a copy of headers with credential values replaced by REDACTED.

    Names are always preserved, only values are redacted.
    """
    if headers is None:
        return None
    return {
        name: (
            REDACTED if _is_secret_name(name, api_key_parameter_name) else str(value)
        )
        for name, value in headers.items()
    }


def sanitize_url(
    url: Optional[str], api_key_parameter_name: Optional[str] = None
) -> Optional[str]:
    """Return url with credential query-parameter values and userinfo redacted."""
    if not url:
        return url
    try:
        parsed = urlsplit(url)
    except ValueError:
        return REDACTED

    netloc = parsed.netloc
    if "@" in netloc:
        netloc = f"{REDACTED}@{netloc.rsplit('@', 1)[1]}"

    query = parsed.query
    if query:
        query = urlencode(
            [
                (
                    name,
                    (
                        REDACTED
                        if _is_secret_name(name, api_key_parameter_name)
                        else value
                    ),
                )
                for name, value in parse_qsl(query, keep_blank_values=True)
            ],
            safe="*",
        )

    return urlunsplit((parsed.scheme, netloc, parsed.path, query, parsed.fragment))


_EXTERNAL_IP_URL = "https://checkip.amazonaws.com"
_external_ip_cache: Optional[str] = None


def get_external_ip(timeout_seconds: int = 3) -> Optional[str]:
    """Return the egress IP address of this process, or None if it cannot be determined.

    The result is cached for the lifetime of the process. Never raises.
    """
    global _external_ip_cache
    if _external_ip_cache is not None:
        return _external_ip_cache
    try:
        with urllib3.PoolManager() as http:
            response = http.request(
                "GET",
                _EXTERNAL_IP_URL,
                timeout=urllib3.Timeout(connect=timeout_seconds, read=timeout_seconds),
                retries=False,
            )
            if response.status == 200:
                _external_ip_cache = response.data.decode("utf-8").strip() or None
    except Exception as exc:
        logging.warning("Could not determine external IP address: %s", exc)
    return _external_ip_cache


@dataclass
class FeedRequestDiagnostics:
    """Request and response detail for a feed download attempt, safe to log and store."""

    request_url: Optional[str] = None
    resolved_url: Optional[str] = None
    request_headers: Optional[dict] = None
    response_headers: Optional[dict] = None
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None
    redirect_urls: Optional[list] = None
    external_ip: Optional[str] = None
    content_type: Optional[str] = None
    is_zip: Optional[bool] = None
    downloaded_bytes: Optional[int] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def success(self) -> bool:
        return (
            self.error_type is None
            and self.status_code is not None
            and 200 <= self.status_code < 300
        )

    def as_dict(self) -> dict:
        return asdict(self)


class FeedDownloadError(Exception):
    """Raised when a feed download fails, carrying the diagnostics of the attempt."""

    def __init__(self, message: str, diagnostics: FeedRequestDiagnostics):
        super().__init__(message)
        self.diagnostics = diagnostics


@dataclass
class FeedDownloadResult:
    """Outcome of a successful feed download."""

    file_hash: Optional[str]
    is_zip: Optional[bool]
    diagnostics: FeedRequestDiagnostics


def build_availability_check(
    diagnostics: FeedRequestDiagnostics,
    feed_id: str,
    source: str,
    request_type: str = "http_get",
    checked_at: Optional[datetime] = None,
):
    """Map diagnostics onto a GtfsFeedAvailabilityCheck row.

    source is one of 'availability_check' or 'dataset_download'.
    """
    from shared.database_gen.sqlacodegen_models import GtfsFeedAvailabilityCheck

    return GtfsFeedAvailabilityCheck(
        feed_id=feed_id,
        checked_at=checked_at or datetime.now(timezone.utc),
        request_url=diagnostics.request_url,
        resolved_url=diagnostics.resolved_url,
        request_type=request_type,
        status_code=diagnostics.status_code,
        latency_ms=diagnostics.latency_ms,
        error_message=diagnostics.error_message,
        error_type=diagnostics.error_type,
        success=diagnostics.success,
        content_type=diagnostics.content_type,
        is_zip=diagnostics.is_zip,
        source=source,
        request_headers=diagnostics.request_headers,
        response_headers=diagnostics.response_headers,
        redirect_urls=diagnostics.redirect_urls,
        external_ip=diagnostics.external_ip,
    )


def _execute_http_request(
    method: str,
    url: str,
    headers: Optional[dict],
    timeout_seconds: int,
    read_bytes: int = 0,
) -> tuple:
    """Execute a single HTTP request and return a result tuple.

    Returns:
        (status_code, latency_ms, resp_headers, first_bytes, error_type, error_message, redirect_urls)
        redirect_urls is a list of URLs the request was redirected through.
        On network/timeout errors, status_code/latency_ms/resp_headers are None,
        first_bytes is b'', and redirect_urls is [].
    """
    preload = read_bytes == 0
    try:
        ctx = create_feed_ssl_context()
        retries = urllib3.Retry(redirect=10, connect=1, read=0, status=0)
        with urllib3.PoolManager(ssl_context=ctx) as http:
            start = time.monotonic()
            r = http.request(
                method,
                url,
                headers=headers,
                retries=retries,
                preload_content=preload,
                timeout=urllib3.Timeout(connect=timeout_seconds, read=timeout_seconds),
            )
            latency_ms = int((time.monotonic() - start) * 1000)
            status_code = r.status
            resp_headers = r.headers
            first_bytes = r.read(read_bytes) if not preload else b""
            if not preload:
                r.release_conn()
            redirect_urls = [
                h.redirect_location
                for h in (r.retries.history or [])
                if h.redirect_location
            ]
        return (
            status_code,
            latency_ms,
            resp_headers,
            first_bytes,
            None,
            None,
            redirect_urls,
        )
    except urllib3.exceptions.MaxRetryError as exc:
        return None, None, None, b"", "ConnectionError", str(exc), []
    except urllib3.exceptions.TimeoutError as exc:
        return None, None, None, b"", "Timeout", str(exc), []
    except urllib3.exceptions.HTTPError as exc:
        return None, None, None, b"", type(exc).__name__, str(exc), []


def perform_request(
    feed_id: str,
    stable_id: str,
    producer_url: str,
    authentication_type: str,
    api_key_parameter_name: Optional[str],
    credentials: Optional[str],
    timeout_seconds: int,
    fallback_to_get: bool = False,
):
    """Execute an HTTP HEAD (with optional GET fallback) for a feed availability check.

    Tries HEAD first. When fallback_to_get=True and HEAD fails (non-2xx or any
    exception), retries with a lightweight GET that reads only 4 bytes to detect
    the ZIP magic signature (PK\\x03\\x04). The stored request_type reflects which
    method produced the final result.

    Note: request_url is always the original producer_url (never the
    credential-bearing resolved URL) to avoid persisting secrets.
    """
    from shared.database_gen.sqlacodegen_models import GtfsFeedAvailabilityCheck

    checked_at = datetime.now(timezone.utc)
    headers, resolved_url = build_feed_request_params(
        producer_url,
        feed_id=feed_id,
        authentication_type=authentication_type,
        api_key_parameter_name=api_key_parameter_name,
        credentials=credentials,
    )

    (
        status_code,
        latency_ms,
        resp_headers,
        _,
        error_type,
        error_message,
        redirect_urls,
    ) = _execute_http_request("HEAD", resolved_url, headers, timeout_seconds)
    error_message = _sanitize_error_message(error_message, resolved_url, producer_url)
    request_type = "http_head"
    success = status_code is not None and status_code < 400
    content_type = _parse_content_type(
        resp_headers.get("Content-Type") if resp_headers else None
    )
    is_zip = _is_zip_from_content_type(content_type)

    if error_type:
        logging.warning(
            "HEAD %s for feed %s (%s): %s",
            error_type,
            stable_id,
            producer_url,
            error_message,
        )
    _log_redirects(stable_id, producer_url, redirect_urls)

    if not success and fallback_to_get:
        logging.info(
            "HEAD failed for feed %s (%s) [status=%s error=%s], trying GET fallback",
            stable_id,
            producer_url,
            status_code,
            error_type,
        )
        (
            status_code,
            latency_ms,
            resp_headers,
            first_bytes,
            error_type,
            error_message,
            redirect_urls,
        ) = _execute_http_request(
            "GET", resolved_url, headers, timeout_seconds, read_bytes=4
        )
        error_message = _sanitize_error_message(
            error_message, resolved_url, producer_url
        )
        request_type = "http_get"
        success = status_code is not None and status_code < 400
        content_type = _parse_content_type(
            resp_headers.get("Content-Type") if resp_headers else None
        )
        is_zip = (
            first_bytes == _ZIP_MAGIC
            if first_bytes
            else _is_zip_from_content_type(content_type)
        )
        if error_type:
            logging.warning(
                "GET fallback %s for feed %s (%s): %s",
                error_type,
                stable_id,
                producer_url,
                error_message,
            )
        _log_redirects(stable_id, producer_url, redirect_urls)

    return GtfsFeedAvailabilityCheck(
        feed_id=feed_id,
        checked_at=checked_at,
        request_url=producer_url,
        resolved_url=sanitize_url(resolved_url, api_key_parameter_name),
        request_type=request_type,
        status_code=status_code,
        latency_ms=latency_ms,
        error_message=error_message,
        error_type=error_type,
        success=success,
        content_type=content_type,
        is_zip=is_zip,
        source="availability_check",
        request_headers=sanitize_headers(headers, api_key_parameter_name),
        response_headers=sanitize_headers(dict(resp_headers) if resp_headers else None),
        redirect_urls=[
            sanitize_url(u, api_key_parameter_name) for u in (redirect_urls or [])
        ],
    )


def download_feed(
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
    max_bytes: Optional[int] = None,
    timeout_seconds: Optional[int] = None,
) -> FeedDownloadResult:
    """Download a feed to file_path and return its hash along with request diagnostics.

    max_bytes stops the download once that many bytes have been read, which lets callers
    inspect the response without storing the whole dataset. The returned hash is None in
    that case because the file is incomplete.

    Raises FeedDownloadError carrying a FeedRequestDiagnostics on any failure.
    """
    logger = logger or logging.getLogger(__name__)
    producer_url = url
    resolved_url = url
    hash_object = hashlib.new(hash_algorithm)
    diagnostics = FeedRequestDiagnostics(
        request_url=sanitize_url(producer_url, api_key_parameter_name)
    )
    truncated = False

    try:
        ctx = create_feed_ssl_context(trusted_certs=trusted_certs)

        headers, resolved_url = build_feed_request_params(
            producer_url,
            feed_id=feed_id,
            authentication_type=authentication_type,
            api_key_parameter_name=api_key_parameter_name,
            credentials=credentials,
        )
        diagnostics.resolved_url = sanitize_url(resolved_url, api_key_parameter_name)
        diagnostics.request_headers = sanitize_headers(headers, api_key_parameter_name)

        timeout = (
            urllib3.Timeout(connect=timeout_seconds, read=timeout_seconds)
            if timeout_seconds
            else None
        )
        request_kwargs = {"timeout": timeout} if timeout else {}

        with urllib3.PoolManager(ssl_context=ctx) as http:
            start = time.monotonic()
            with http.request(
                "GET",
                resolved_url,
                preload_content=False,
                headers=headers,
                redirect=True,
                **request_kwargs,
            ) as r, open(file_path, "wb") as out_file:
                diagnostics.latency_ms = int((time.monotonic() - start) * 1000)
                diagnostics.status_code = r.status
                diagnostics.response_headers = sanitize_headers(dict(r.headers))
                diagnostics.redirect_urls = [
                    sanitize_url(h.redirect_location, api_key_parameter_name)
                    for h in (r.retries.history or [])
                    if h.redirect_location
                ]
                diagnostics.content_type = _parse_content_type(
                    r.headers.get("Content-Type")
                )

                if not 200 <= r.status < 300:
                    raise ValueError(f"Invalid HTTP response code: [{r.status}]")

                logger.info(f"HTTP response code: [{r.status}]")
                total = 0
                while True:
                    data = r.read(chunk_size)
                    if not data:
                        break
                    hash_object.update(data)
                    out_file.write(data)
                    total += len(data)
                    if max_bytes is not None and total >= max_bytes:
                        truncated = True
                        break
                r.release_conn()
                diagnostics.downloaded_bytes = total

        diagnostics.is_zip = zipfile.is_zipfile(file_path) or (
            _is_zip_from_content_type(diagnostics.content_type) or False
        )
        return FeedDownloadResult(
            file_hash=None if truncated else hash_object.hexdigest(),
            is_zip=diagnostics.is_zip,
            diagnostics=diagnostics,
        )
    except Exception as exc:
        diagnostics.error_type = type(exc).__name__
        # Collapse the credential-bearing resolved URL onto the producer URL, then the
        # producer URL onto its sanitized form, so neither can leak through the message.
        message = _sanitize_error_message(str(exc), resolved_url, producer_url)
        if message and producer_url != diagnostics.request_url:
            message = message.replace(producer_url, diagnostics.request_url)
        diagnostics.error_message = message
        diagnostics.external_ip = get_external_ip()
        logger.warning(
            "Feed download failed for %s: %s",
            diagnostics.request_url,
            diagnostics.as_dict(),
        )
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                logger.error(f"Delete file: [{file_path}]")
        raise FeedDownloadError(str(exc), diagnostics) from exc


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
    return download_feed(
        url,
        file_path,
        hash_algorithm=hash_algorithm,
        chunk_size=chunk_size,
        feed_id=feed_id,
        authentication_type=authentication_type,
        api_key_parameter_name=api_key_parameter_name,
        credentials=credentials,
        logger=logger,
        trusted_certs=trusted_certs,
    ).file_hash


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


def create_http_gtfs_datasets_comparer_task(
    feed_stable_id: str,
    base_dataset_stable_id: str,
    new_dataset_stable_id: str,
    disallow_overwrite: bool = True,
) -> None:
    """
    Create a Cloud Task to run the gtfs-datasets-comparer function for a pair of datasets.

    disallow_overwrite: when True (default) the comparer skips the pair if its changelog
    already exists; pass False to force regeneration/overwrite.
    """
    from google.cloud import tasks_v2
    import json

    client = tasks_v2.CloudTasksClient()
    body = json.dumps(
        {
            "feed_stable_id": feed_stable_id,
            "base_dataset_stable_id": base_dataset_stable_id,
            "new_dataset_stable_id": new_dataset_stable_id,
            "disallow_overwrite": disallow_overwrite,
        }
    ).encode()
    queue_name = os.getenv("GTFS_CHANGE_TRACKER_QUEUE")
    project_id = os.getenv("PROJECT_ID")
    gcp_region = os.getenv("GCP_REGION")
    gcp_env = os.getenv("ENVIRONMENT")

    create_http_task(
        client,
        body,
        f"https://{gcp_region}-{project_id}.cloudfunctions.net/gtfs-datasets-comparer-{gcp_env}",
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
