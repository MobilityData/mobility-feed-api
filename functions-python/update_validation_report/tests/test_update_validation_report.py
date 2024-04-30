import os
import unittest
from unittest import mock
from unittest.mock import MagicMock, patch, Mock

from faker import Faker
from google.cloud import storage

from test_utils.database_utils import default_db_url
from update_validation_report.src.main import (
    update_dataset_metadata,
    get_latest_datasets,
    get_dataset_blobs_for_validation,
    update_validation_report,
)

faker = Faker()


def _create_storage_blob(name, metadata):
    """Create a mock storage blob."""
    blob = MagicMock(spec=storage.Blob)
    blob.metadata = metadata
    blob.name = name
    blob.patch = Mock(return_value=None)
    return blob


class TestUpdateReportProcessor(unittest.TestCase):
    @patch("os.getenv")
    @patch("google.cloud.storage.Blob")
    @patch("requests.get")
    def test_update_dataset_metadata(self, mock_get, mock_blob, mock_getenv):
        """Test update_dataset_metadata function."""
        max_retry = "3"
        mock_getenv.side_effect = lambda var_name, default=None: {
            "WEB_VALIDATOR_URL": faker.url(),
            "MAX_RETRY": max_retry,
            "BATCH_SIZE": "2",
            "SLEEP_TIME": "0",
        }.get(var_name, default)
        validator_version = "1.0.1"
        mock_get.return_value = MagicMock(status_code=200, content=validator_version)

        blob1 = _create_storage_blob(
            f"{faker.word()}/dataset1",
            {"retry": max_retry, "latest_validator_version": validator_version},
        )
        blob2 = _create_storage_blob(
            f"{faker.word()}/dataset2",
            {
                "retry": "2",
                "latest_validator_version": faker.pystr(min_chars=3, max_chars=5),
            },
        )
        blob3 = _create_storage_blob(f"{faker.word()}/dataset3", {})

        mock_blob.side_effect = [blob1, blob2, blob3]
        dataset_blobs = [blob1, blob2, blob3]

        expected_result = ["dataset2", "dataset3"]
        result = update_dataset_metadata(dataset_blobs, validator_version)

        self.assertEqual(result, expected_result)
        # Ensure that metadata update is attempted with the correct version and retry count
        blob1.patch.assert_not_called()
        blob2.patch.assert_called_once()
        for blob in dataset_blobs:
            self.assertEqual(
                blob.metadata["latest_validator_version"], validator_version
            )
            self.assertLessEqual(int(blob.metadata["retry"]), int(max_retry))

    def test_get_latest_datasets(self):
        """Test get_latest_datasets function."""
        session = MagicMock()
        session.query.return_value.filter.return_value.all = MagicMock()
        get_latest_datasets(session)
        session.query.assert_called_once()

    @patch("google.cloud.storage.Client")
    def test_get_dataset_blobs_for_validation(self, mock_client):
        """Test get_dataset_blobs_for_validation function."""
        # Setup mock storage client and bucket
        mock_bucket = Mock()
        mock_client.return_value.bucket.return_value = mock_bucket

        # Setup mock blobs and existence results
        mock_system_errors_blob = Mock(spec=storage.Blob)
        mock_dataset_blob = Mock(spec=storage.Blob)
        mock_system_errors_blob.exists.return_value = False
        mock_dataset_blob.exists.return_value = True

        mock_bucket.blob.side_effect = lambda name: {
            "feed1/dataset1/system_errors_1.0.json": mock_system_errors_blob,
            "feed1/dataset1/dataset_1.0.json": mock_dataset_blob,
        }[name]

        # Input parameters
        bucket_name = "test-bucket"
        validator_version = "1.0"
        latest_datasets = [("feed1", "dataset1")]

        result = get_dataset_blobs_for_validation(
            bucket_name, validator_version, latest_datasets
        )

        # Assertions
        self.assertIn(mock_system_errors_blob, result)
        self.assertEqual(len(result), 1)
        mock_system_errors_blob.exists.assert_called_once()
        mock_dataset_blob.exists.assert_called_once()

    @mock.patch.dict(
        os.environ,
        {
            "FEEDS_DATABASE_URL": default_db_url,
            "WEB_VALIDATOR_URL": faker.url(),
            "MAX_RETRY": "2",
            "BATCH_SIZE": "2",
            "SLEEP_TIME": "0",
        },
    )
    @patch("google.cloud.storage.Blob", autospec=True)
    @patch("requests.get", autospec=True)
    @patch("google.cloud.storage.Client", autospec=True)
    @patch("update_validation_report.src.main.Logger", autospec=True)
    def test_update_validation_report(
        self, mock_logger, mock_client, mock_get, mock_blob
    ):
        """Test update_validation_report function."""
        response = update_validation_report(None)
        self.assertEqual(response[0]["message"], "Updated 0 validation report(s).")
