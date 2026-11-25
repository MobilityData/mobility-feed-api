from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from shared.common import user_data_retention, user_data_storage
from shared.common.user_data_paths import (
    dataset_upload_prefix,
    task_files_prefix,
    upload_object_name,
    user_prefix,
    user_storage_key,
)


class TestUserDataPaths:
    def test_user_key_is_stable_and_hides_the_user_id(self):
        key = user_storage_key("abcdefghijklmnopqrstuvwxyz12")
        assert key == user_storage_key("abcdefghijklmnopqrstuvwxyz12")
        assert key != user_storage_key("abcdefghijklmnopqrstuvwxyz13")
        assert len(key) == 32 and "abcdefghij" not in key

    def test_object_names_sit_under_the_user_prefix(self):
        key = user_storage_key("user-1")
        assert user_prefix("user-1") == f"{key}/"
        assert upload_object_name("user-1", "ds-1") == f"{key}/uploads/ds-1/source.zip"
        assert task_files_prefix("user-1", "task-1") == f"{key}/tasks/task-1/"


def _blob(name):
    blob = MagicMock()
    blob.name = name
    return blob


@pytest.fixture
def datasets_bucket():
    bucket = MagicMock()
    with patch.object(user_data_storage, "_datasets_bucket", return_value=bucket), patch.object(
        user_data_storage, "_signing_credentials", return_value="credentials"
    ):
        yield bucket


@pytest.fixture
def task_outputs_bucket():
    bucket = MagicMock()
    bucket.name = "task-outputs"
    with patch.object(user_data_storage, "_task_outputs_bucket", return_value=bucket):
        yield bucket


class TestSignUpload:
    def test_signs_a_size_limited_put_for_the_upload_object(self, datasets_bucket, monkeypatch):
        monkeypatch.setenv("USER_DATASET_MAX_UPLOAD_BYTES", "1000")
        blob = datasets_bucket.blob.return_value
        blob.generate_signed_url.return_value = "https://signed/put"

        upload = user_data_storage.sign_upload("user-1", "ds-1")

        datasets_bucket.blob.assert_called_once_with(upload_object_name("user-1", "ds-1"))
        kwargs = blob.generate_signed_url.call_args.kwargs
        assert kwargs["method"] == "PUT"
        assert kwargs["version"] == "v4"
        assert kwargs["credentials"] == "credentials"
        assert kwargs["headers"] == {"Content-Type": "application/zip", "x-goog-content-length-range": "1,1000"}
        assert upload.url == "https://signed/put"
        assert upload.method == "PUT"
        assert upload.headers == kwargs["headers"]

    def test_default_max_size(self, monkeypatch):
        monkeypatch.delenv("USER_DATASET_MAX_UPLOAD_BYTES", raising=False)
        assert user_data_storage.max_upload_bytes() == user_data_storage.DEFAULT_MAX_UPLOAD_BYTES


class TestTaskFiles:
    def test_public_urls_of_every_output_file_sorted_by_name(self, task_outputs_bucket):
        prefix = task_files_prefix("user-1", "task-1")
        task_outputs_bucket.list_blobs.return_value = [_blob(f"{prefix}b.parquet"), _blob(f"{prefix}a/report.json")]

        files = user_data_storage.task_files("user-1", "task-1")

        task_outputs_bucket.list_blobs.assert_called_once_with(prefix=prefix)
        base = f"https://storage.googleapis.com/task-outputs/{prefix}"
        assert files == [("a/report.json", f"{base}a/report.json"), ("b.parquet", f"{base}b.parquet")]

    def test_no_output_yet(self, task_outputs_bucket):
        task_outputs_bucket.list_blobs.return_value = []
        assert user_data_storage.task_files("user-1", "task-1") == []

    def test_object_names_are_url_encoded(self):
        assert (
            user_data_storage.public_url("task-outputs", "k/tasks/task-1/my file.parquet")
            == "https://storage.googleapis.com/task-outputs/k/tasks/task-1/my%20file.parquet"
        )


class TestDelete:
    def test_deletes_the_dataset_upload_from_the_datasets_bucket(self, datasets_bucket):
        upload = _blob(upload_object_name("user-1", "ds-1"))
        datasets_bucket.list_blobs.return_value = [upload]

        assert user_data_storage.delete_dataset_upload("user-1", "ds-1") == 1
        datasets_bucket.list_blobs.assert_called_once_with(prefix=dataset_upload_prefix("user-1", "ds-1"))
        upload.delete.assert_called_once()

    def test_deletes_the_task_output_from_the_task_outputs_bucket(self, task_outputs_bucket):
        output = _blob(f"{task_files_prefix('user-1', 'task-1')}stops.parquet")
        task_outputs_bucket.list_blobs.return_value = [output]

        assert user_data_storage.delete_task_files("user-1", "task-1") == 1
        task_outputs_bucket.list_blobs.assert_called_once_with(prefix=task_files_prefix("user-1", "task-1"))
        output.delete.assert_called_once()

    def test_nothing_left_is_a_no_op(self, task_outputs_bucket):
        task_outputs_bucket.list_blobs.return_value = []
        assert user_data_storage.delete_task_files("user-1", "task-1") == 0


class TestRetention:
    def test_configured_period(self, monkeypatch):
        monkeypatch.setenv("USER_DATA_RETENTION_DAYS", "7")
        created_at = datetime(2030, 1, 1, tzinfo=timezone.utc)
        assert user_data_retention.expires_at(created_at) == datetime(2030, 1, 8, tzinfo=timezone.utc)

    def test_default_period(self, monkeypatch):
        monkeypatch.delenv("USER_DATA_RETENTION_DAYS", raising=False)
        assert user_data_retention.retention() == timedelta(days=user_data_retention.DEFAULT_RETENTION_DAYS)
