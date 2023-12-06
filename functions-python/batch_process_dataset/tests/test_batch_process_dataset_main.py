import datetime
import unittest
from hashlib import sha256
from typing import Final
from unittest.mock import patch, MagicMock, call
from batch_process_dataset.src.main import DatasetProcessor, DatasetFile

public_url = f'http://this-dont-exists-{datetime.datetime.now().strftime("%Y%m%d%H%S")}.com'
file_content: Final[bytes] = b'Test content'
file_hash: Final[str] = sha256(file_content).hexdigest()


class TestDatasetProcessor(unittest.TestCase):

    @patch('batch_process_dataset.src.main.DatasetProcessor.download_content')
    @patch('google.cloud.storage.Client.get_bucket')
    def test_upload_dataset_diff_hash(self, mock_get_bucket, mock_download_url_content):
        """
        Test upload_dataset method of DatasetProcessor class with different hash from the latest one
        """
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.public_url = public_url
        mock_bucket.blob.return_value = mock_blob
        mock_get_bucket.return_value = mock_bucket
        mock_download_url_content.return_value = file_content

        processor = DatasetProcessor(public_url, "feed_id", "feed_stable_id",
                                     "latest_hash", "bucket_name")
        with patch.object(processor, 'date', 'mocked_timestamp'):
            result = processor.upload_dataset()

        self.assertIsNotNone(result)
        mock_download_url_content.assert_called_once()
        self.assertIsInstance(result, DatasetFile)
        self.assertEqual(result.hosted_url, public_url)
        self.assertEqual(result.file_sha256_hash, file_hash)
        mock_bucket.blob.assert_has_calls(
            [
                call("feed_stable_id/feed_stable_id-mocked_timestamp.zip"),
                call("feed_stable_id/latest.zip")
            ],
            any_order=True
        )
        self.assertEqual(mock_bucket.blob.call_count, 2)
        self.assertEqual(mock_blob.make_public.call_count, 2)

    @patch('batch_process_dataset.src.main.DatasetProcessor.download_content')
    @patch('google.cloud.storage.Client.get_bucket')
    def test_upload_dataset_same_hash(self, mock_get_bucket, mock_download_url_content):
        """
        Test upload_dataset method of DatasetProcessor class with the hash from the latest one
        """
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.public_url = public_url
        mock_bucket.blob.return_value = mock_blob
        mock_get_bucket.return_value = mock_bucket
        mock_download_url_content.return_value = file_content

        processor = DatasetProcessor(public_url, "feed_id", "feed_stable_id",
                                     file_hash, "bucket_name")

        result = processor.upload_dataset()

        self.assertIsNone(result)
        mock_bucket.blob.assert_not_called()
        mock_blob.make_public.assert_not_called()
        mock_download_url_content.assert_called_once()

    @patch('batch_process_dataset.src.main.DatasetProcessor.download_content')
    @patch('google.cloud.storage.Client.get_bucket')
    def test_upload_dataset_download_exception(self, mock_get_bucket, mock_download_url_content):
        """
        Test upload_dataset method of DatasetProcessor class with the hash from the latest one
        """
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.public_url = public_url
        mock_bucket.blob.return_value = mock_blob
        mock_get_bucket.return_value = mock_bucket
        mock_download_url_content.side_effect = exception = Exception("Download failed")

        processor = DatasetProcessor(public_url, "feed_id", "feed_stable_id",
                                     "latest_hash", "bucket_name")

        with self.assertRaises(Exception) as context:
            processor.upload_dataset()

