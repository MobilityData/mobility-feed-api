"""Upload URLs and file URLs for the user data buckets, and deletion of uploads and task outputs.

There are two buckets. Uploads go to a private datasets bucket (USER_DATASETS_BUCKET_NAME) through
signed URLs and are never readable by users. Task outputs go to a public task outputs bucket
(USER_TASK_OUTPUTS_BUCKET_NAME) that anyone can read by exact object name but not list, so their
URLs are plain and need no signing.

Nothing here reads or writes the buckets with the caller's own identity. It impersonates the user
data service account (USER_DATA_SERVICE_ACCOUNT), the only principal that can write to either
bucket, and signs upload URLs with that account's key through the IAM Credentials API. The caller's
own service account only needs the Token Creator role on the user data service account.
"""

import functools
import os
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

import google.auth
from google.auth import impersonated_credentials
from google.cloud import storage

from shared.common.user_data_paths import (
    dataset_upload_prefix,
    task_files_prefix,
    upload_object_name,
)

UPLOAD_URL_TTL = timedelta(minutes=15)
UPLOAD_CONTENT_TYPE = "application/zip"
# Default maximum size of an uploaded file, overridable with USER_DATASET_MAX_UPLOAD_BYTES.
DEFAULT_MAX_UPLOAD_BYTES = 500 * 1024 * 1024
_STORAGE_SCOPE = "https://www.googleapis.com/auth/devstorage.read_write"
_PUBLIC_URL_BASE = "https://storage.googleapis.com"


@dataclass(frozen=True)
class SignedUpload:
    url: str
    method: str
    headers: Dict[str, str]
    expires_at: datetime


def max_upload_bytes() -> int:
    return int(os.getenv("USER_DATASET_MAX_UPLOAD_BYTES", DEFAULT_MAX_UPLOAD_BYTES))


@functools.lru_cache(maxsize=1)
def _signing_credentials():
    source_credentials, _ = google.auth.default()
    return impersonated_credentials.Credentials(
        source_credentials=source_credentials,
        target_principal=os.environ["USER_DATA_SERVICE_ACCOUNT"],
        target_scopes=[_STORAGE_SCOPE],
    )


@functools.lru_cache(maxsize=1)
def _client() -> storage.Client:
    return storage.Client(project=os.getenv("PROJECT_ID"), credentials=_signing_credentials())


def _datasets_bucket() -> storage.Bucket:
    """The private bucket holding uploads."""
    return _client().bucket(os.environ["USER_DATASETS_BUCKET_NAME"])


def _task_outputs_bucket() -> storage.Bucket:
    """The public bucket holding task outputs."""
    return _client().bucket(os.environ["USER_TASK_OUTPUTS_BUCKET_NAME"])


def public_url(bucket_name: str, object_name: str) -> str:
    return f"{_PUBLIC_URL_BASE}/{bucket_name}/{urllib.parse.quote(object_name)}"


def sign_upload(user_id: str, dataset_id: str) -> SignedUpload:
    """A signed PUT URL for the dataset's file. GCS refuses a file over the maximum size."""
    headers = {
        "Content-Type": UPLOAD_CONTENT_TYPE,
        "x-goog-content-length-range": f"0,{max_upload_bytes()}",
    }
    url = (
        _datasets_bucket()
        .blob(upload_object_name(user_id, dataset_id))
        .generate_signed_url(
            version="v4",
            expiration=UPLOAD_URL_TTL,
            method="PUT",
            headers=headers,
            credentials=_signing_credentials(),
        )
    )
    return SignedUpload(url=url, method="PUT", headers=headers, expires_at=datetime.now(timezone.utc) + UPLOAD_URL_TTL)


def task_files(user_id: str, task_id: str) -> List[Tuple[str, str]]:
    """The task's output files as (name relative to the task, public URL), sorted by name."""
    bucket = _task_outputs_bucket()
    prefix = task_files_prefix(user_id, task_id)
    names = sorted(blob.name[len(prefix) :] for blob in bucket.list_blobs(prefix=prefix))
    return [(name, public_url(bucket.name, f"{prefix}{name}")) for name in names]


def delete_dataset_upload(user_id: str, dataset_id: str) -> int:
    """Delete the dataset's upload from the datasets bucket. Returns how many objects were deleted."""
    return _delete_prefix(_datasets_bucket(), dataset_upload_prefix(user_id, dataset_id))


def delete_task_files(user_id: str, task_id: str) -> int:
    """Delete the task's output from the task outputs bucket. Returns how many objects were deleted.

    Deleting the output is the only way to stop its public URLs from working.
    """
    return _delete_prefix(_task_outputs_bucket(), task_files_prefix(user_id, task_id))


def _delete_prefix(bucket: storage.Bucket, prefix: str) -> int:
    """Safe to call again after a partial failure: objects already gone are simply not listed."""
    deleted = 0
    for blob in bucket.list_blobs(prefix=prefix):
        blob.delete()
        deleted += 1
    return deleted
