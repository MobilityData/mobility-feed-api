import unittest
import uuid
from unittest.mock import patch, MagicMock

import requests

from shared.dataset_service.main import Status
from gbfs_utils import (
    fetch_gbfs_files,
    upload_gbfs_file_to_bucket,
    save_trace_with_error,
    save_snapshot_and_report,
    GBFSValidator,
)


class TestGbfsUtils(unittest.TestCase):
    def setUp(self):
        self.stable_id = "test_stable_id"
        self.validator = GBFSValidator(self.stable_id)

    @patch("requests.get")
    def test_fetch_gbfs_files(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"key": "value"}
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = fetch_gbfs_files("http://example.com")
        self.assertEqual(result, {"key": "value"})
        mock_get.assert_called_once_with("http://example.com")

    @patch("gbfs_utils.upload_gbfs_file_to_bucket")
    def test_create_gbfs_json_with_bucket_paths_empty_data(self, mock_upload):
        mock_bucket = MagicMock()
        gbfs_data = {"data": {}}

        self.validator.create_gbfs_json_with_bucket_paths(mock_bucket, gbfs_data)

        mock_upload.assert_not_called()

    @patch("requests.get")
    def test_upload_gbfs_file_to_bucket(self, mock_get):
        mock_response = MagicMock()
        mock_response.content = b"file_content"
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        mock_blob = MagicMock()
        mock_blob.public_url = "http://public-url.com"
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        result = upload_gbfs_file_to_bucket(
            mock_bucket, "http://file-url.com", "destination_blob"
        )
        self.assertEqual(result, "http://public-url.com")
        mock_get.assert_called_once_with("http://file-url.com")
        mock_blob.upload_from_string.assert_called_once_with(b"file_content")
        mock_blob.make_public.assert_called_once()

    @patch("requests.get")
    def test_upload_gbfs_file_to_bucket_exception(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("Error")
        mock_bucket = MagicMock()

        result = upload_gbfs_file_to_bucket(
            mock_bucket, "http://file-url.com", "destination_blob"
        )
        self.assertIsNone(result)

    @patch("gbfs_utils.upload_gbfs_file_to_bucket")
    def test_create_gbfs_json_with_bucket_paths(self, mock_upload):
        mock_upload.return_value = "http://new-url.com"

        mock_bucket = MagicMock()
        gbfs_data = {
            "data": {"en": {"feeds": [{"url": "http://old-url.com", "name": "feed"}]}}
        }

        mock_bucket.blob.return_value.public_url = "http://new-url.com"

        self.validator.create_gbfs_json_with_bucket_paths(mock_bucket, gbfs_data)
        self.assertEqual(self.validator.hosted_url, "http://new-url.com")

    @patch("gbfs_utils.upload_gbfs_file_to_bucket")
    def test_create_gbfs_json_with_bucket_paths_2(self, mock_upload):
        mock_upload.return_value = "http://new-url.com"

        mock_bucket = MagicMock()
        gbfs_data = {"data": {"feeds": [{"url": "http://old-url.com", "name": "feed"}]}}

        mock_bucket.blob.return_value.public_url = "http://new-url.com"

        self.validator.create_gbfs_json_with_bucket_paths(mock_bucket, gbfs_data)
        self.assertEqual(self.validator.hosted_url, "http://new-url.com")

    def test_save_trace_with_error(self):
        mock_trace = MagicMock()
        mock_trace_service = MagicMock()

        save_trace_with_error(mock_trace, "An error occurred", mock_trace_service)

        mock_trace_service.save.assert_called_once_with(mock_trace)
        self.assertEqual(mock_trace.error_message, "An error occurred")
        self.assertEqual(mock_trace.status, Status.FAILED)

    def test_create_snapshot(self):
        feed_id = "test_feed_id"
        hosted_url = "http://hosted-url.com"
        self.validator.hosted_url = hosted_url

        snapshot = self.validator.create_snapshot(feed_id)

        self.assertEqual(
            snapshot.stable_id,
            f"{self.stable_id}-{self.validator.validation_timestamp}",
        )
        self.assertEqual(snapshot.feed_id, feed_id)
        self.assertEqual(snapshot.hosted_url, hosted_url)
        self.assertTrue(
            uuid.UUID(snapshot.id)
        )  # Validates that `snapshot.id` is a valid UUID

    @patch("requests.post")
    @patch("google.cloud.storage.Bucket.blob")
    def test_validate_gbfs_feed(self, mock_blob, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"summary": "validation report"}
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        mock_blob_obj = MagicMock()
        mock_blob_obj.public_url = "http://public-url.com"
        mock_blob.return_value = mock_blob_obj

        hosted_url = "http://hosted-url.com"
        self.validator.hosted_url = hosted_url
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob_obj

        result = self.validator.validate_gbfs_feed(mock_bucket)

        self.assertEqual(
            result["json_report_summary"], {"summary": "validation report"}
        )
        self.assertEqual(result["report_summary_url"], mock_blob_obj.public_url)
        mock_post.assert_called_once_with(
            self.validator.VALIDATOR_URL, json={"url": hosted_url}
        )
        mock_blob_obj.upload_from_string.assert_called_once()

    @patch("gbfs_utils.Gbfsvalidationreport")
    @patch("gbfs_utils.Gbfsnotice")
    def test_save_snapshot_and_report(self, mock_gbfsnotice, mock_gbfsvalidationreport):
        mock_session = MagicMock()
        mock_snapshot = MagicMock()
        validation_result = {
            "report_summary_url": "http://report-summary-url.com",
            "json_report_summary": {
                "filesSummary": [
                    {
                        "file": "file_name",
                        "hasErrors": True,
                        "groupedErrors": [
                            {
                                "keyword": "error_keyword",
                                "message": "error_message",
                                "schemaPath": "schema_path",
                                "count": 1,
                            }
                        ],
                    }
                ]
            },
        }

        save_snapshot_and_report(
            mock_snapshot, validation_result, db_session=mock_session
        )

        mock_session.add.assert_called_once_with(mock_snapshot)
        mock_session.commit.assert_called_once()

        mock_gbfsnotice.assert_called_once_with(
            keyword="error_keyword",
            message="error_message",
            schema_path="schema_path",
            gbfs_file="file_name",
            validation_report_id=mock_gbfsvalidationreport().id,
            count=1,
        )
