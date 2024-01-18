import datetime
import unittest
from hashlib import sha256
from typing import Final
from unittest.mock import patch, MagicMock
from batch_process_dataset.src.main import DatasetProcessor, DatasetFile

public_url = (
    f'http://this-dont-exists-{datetime.datetime.now().strftime("%Y%m%d%H%S")}.com'
)
file_content: Final[bytes] = b"Test content"
file_hash: Final[str] = sha256(file_content).hexdigest()


class TestDatasetProcessor(unittest.TestCase):
    @patch("batch_process_dataset.src.main.DatasetProcessor.upload_file_to_storage")
    @patch("batch_process_dataset.src.main.DatasetProcessor.download_content")
    def test_upload_dataset_diff_hash(
        self, mock_download_url_content, upload_file_to_storage
    ):
        """
        Test upload_dataset method of DatasetProcessor class with different hash from the latest one
        """
        mock_blob = MagicMock()
        mock_blob.public_url = public_url
        upload_file_to_storage.return_value = mock_blob
        mock_download_url_content.return_value = file_hash

        processor = DatasetProcessor(
            public_url,
            "feed_id",
            "feed_stable_id",
            "execution_id",
            "different_hash",
            "bucket_name",
            0,
            None,
        )
        with patch.object(processor, "date", "mocked_timestamp"):
            result = processor.upload_dataset()

        self.assertIsNotNone(result)
        mock_download_url_content.assert_called_once()
        self.assertIsInstance(result, DatasetFile)
        self.assertEqual(result.hosted_url, public_url)
        self.assertEqual(result.file_sha256_hash, file_hash)
        # Upload to storage is called twice, one for the latest and one for the timestamped one
        self.assertEqual(upload_file_to_storage.call_count, 2)

    @patch("batch_process_dataset.src.main.DatasetProcessor.upload_file_to_storage")
    @patch("batch_process_dataset.src.main.DatasetProcessor.download_content")
    def test_upload_dataset_same_hash(
        self, mock_download_url_content, upload_file_to_storage
    ):
        """
        Test upload_dataset method of DatasetProcessor class with the hash from the latest one
        """
        mock_blob = MagicMock()
        mock_blob.public_url = public_url
        upload_file_to_storage.return_value = mock_blob
        mock_download_url_content.return_value = file_hash

        processor = DatasetProcessor(
            public_url,
            "feed_id",
            "feed_stable_id",
            "execution_id",
            file_hash,
            "bucket_name",
            0,
            None,
        )

        result = processor.upload_dataset()

        self.assertIsNone(result)
        upload_file_to_storage.blob.assert_not_called()
        mock_blob.make_public.assert_not_called()
        mock_download_url_content.assert_called_once()

    @patch("batch_process_dataset.src.main.DatasetProcessor.upload_file_to_storage")
    @patch("batch_process_dataset.src.main.DatasetProcessor.download_content")
    def test_upload_dataset_download_exception(
        self, mock_download_url_content, upload_file_to_storage
    ):
        """
        Test upload_dataset method of DatasetProcessor class with the hash from the latest one
        """
        mock_blob = MagicMock()
        mock_blob.public_url = public_url
        upload_file_to_storage.return_value = mock_blob
        mock_download_url_content.side_effect = Exception("Download failed")

        processor = DatasetProcessor(
            public_url,
            "feed_id",
            "feed_stable_id",
            "execution_id",
            "latest_hash",
            "bucket_name",
            0,
            None,
        )

        with self.assertRaises(Exception):
            processor.upload_dataset()
