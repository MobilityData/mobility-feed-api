import os
import unittest
from unittest import mock
from unittest.mock import MagicMock, patch, Mock

from faker import Faker
from google.cloud import storage

from test_utils.database_utils import default_db_url
from update_validation_report.src.main import (
    get_latest_datasets_without_validation_reports,
    get_datasets_for_validation,
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
    def test_get_latest_datasets(self):
        """Test get_latest_datasets function."""
        session = MagicMock()
        session.query.return_value.filter.return_value.all = MagicMock()
        get_latest_datasets_without_validation_reports(session, "1.0.1")
        session.query.assert_called_once()

    @patch("google.cloud.storage.Client")
    def test_get_datasets_for_validation(self, mock_client):
        """Test get_datasets_for_validation function"""
        test_dataset_id = "dataset1"
        test_feed_id = "feed1"

        def create_dataset_blob(name, exists):
            mock_dataset_blob = Mock(spec=storage.Blob)
            mock_dataset_blob.exists.return_value = exists
            mock_dataset_blob.name = name
            return mock_dataset_blob

        # Setup mock storage client and bucket
        mock_bucket = Mock()
        mock_client.return_value.bucket.return_value = mock_bucket

        # Setup mock blobs and existence results
        mock_dataset_blob_exists = create_dataset_blob(
            f"{test_feed_id}/{test_dataset_id}/{test_dataset_id}.zip", True
        )
        mock_dataset_blob_not_exists = create_dataset_blob(
            f"{test_feed_id}/{test_dataset_id}1/{test_dataset_id}1.zip", False
        )

        mock_bucket.blob.side_effect = lambda name: {
            f"{test_feed_id}/{test_dataset_id}/{test_dataset_id}.zip": mock_dataset_blob_exists,
            f"{test_feed_id}/{test_dataset_id}1/{test_dataset_id}1.zip": mock_dataset_blob_not_exists,
        }[name]

        # Input parameters
        nonexistent_dataset = (test_feed_id, f"{test_dataset_id}2")
        latest_datasets = [
            (test_feed_id, test_dataset_id),
            (test_feed_id, f"{test_dataset_id}1"),
            nonexistent_dataset,
        ]

        result = get_datasets_for_validation(latest_datasets)

        # Assertions
        self.assertEqual(len(result), 1)
        mock_dataset_blob_exists.exists.assert_called_once()
        mock_dataset_blob_not_exists.exists.assert_called_once()
        # Only the existing dataset should be returned
        self.assertEqual(result[0][0], test_feed_id)
        self.assertEqual(result[0][1], test_dataset_id)

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
    @patch(
        "update_validation_report.src.main.get_latest_datasets_without_validation_reports",
        autospec=True,
        return_value=[("feed1", "dataset1")]
    )
    @patch(
        "update_validation_report.src.main.get_datasets_for_validation",
        autospec=True,
        return_value=[("feed1", "dataset1")]
    )
    @patch("google.cloud.storage.Blob", autospec=True)
    @patch("requests.get", autospec=True)
    @patch("google.cloud.storage.Client", autospec=True)
    @patch("update_validation_report.src.main.Logger", autospec=True)
    @patch("google.cloud.workflows_v1.WorkflowsClient", autospec=True)
    @patch("google.cloud.workflows.executions_v1.ExecutionsClient", autospec=True)
    @patch("google.cloud.workflows.executions_v1.Execution", autospec=True)
    def test_update_validation_report(
        self,
        execution_mock,
        executions_client_mock,
        workflows_client_mock,
        mock_logger,
        mock_client,
        mock_get,
        mock_blob,
        mock_get_latest_datasets,
        mock_get_datasets_for_validation,
    ):
        """Test update_validation_report function."""
        mock_get.return_value.json.return_value = {"version": "1.0.1"}
        response = update_validation_report(None)
        self.assertTrue("message" in response[0])
        self.assertTrue("dataset_workflow_triggered" in response[0])
        self.assertEqual(response[1], 200)
        self.assertEqual(response[0]["dataset_workflow_triggered"], ['dataset1'])
