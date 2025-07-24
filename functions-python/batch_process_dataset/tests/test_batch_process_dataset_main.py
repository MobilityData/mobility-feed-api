import base64
import datetime
import json
import os
import unittest
from hashlib import sha256
from typing import Final
from unittest.mock import patch, MagicMock, Mock, mock_open

import faker

from main import (
    DatasetProcessor,
    DatasetFile,
    process_dataset,
)
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsfeed
from test_shared.test_utils.database_utils import default_db_url
from cloudevents.http import CloudEvent

public_url = (
    f'http://this-dont-exists-{datetime.datetime.now().strftime("%Y%m%d%H%S")}.com'
)
file_content: Final[bytes] = b"Test content"
file_hash: Final[str] = sha256(file_content).hexdigest()
test_hosted_public_url = "https://the-no-existent-url.com"


def create_cloud_event(mock_data):
    # Helper function to create a mock CloudEvent
    # Convert data to JSON and then to base64
    encoded_data = base64.b64encode(json.dumps(mock_data).encode()).decode()
    return CloudEvent(
        {
            "type": "event.type",
            "source": "event.source",
            "id": "event-id",
            "time": "2021-08-19T12:34:56Z",
            "subject": "event/subject",
        },
        {"message": {"data": encoded_data}},
    )


class TestDatasetProcessor(unittest.TestCase):
    @patch("main.DatasetProcessor.upload_file_to_storage")
    @patch("main.DatasetProcessor.download_content")
    def test_upload_dataset_diff_hash(
        self, mock_download_url_content, upload_file_to_storage
    ):
        """
        Test upload_dataset method of DatasetProcessor class with different hash from the latest one
        """
        mock_blob = MagicMock()
        mock_blob.public_url = public_url
        mock_blob.path = public_url
        upload_file_to_storage.return_value = mock_blob, []
        mock_download_url_content.return_value = file_hash, True, "path/file"

        processor = DatasetProcessor(
            public_url,
            "feed_id",
            "feed_stable_id",
            "execution_id",
            "different_hash",
            "bucket_name",
            0,
            None,
            test_hosted_public_url,
        )
        with patch.object(processor, "date", "mocked_timestamp"):
            result = processor.upload_dataset()

        self.assertIsNotNone(result)
        mock_download_url_content.assert_called_once()
        self.assertIsInstance(result, DatasetFile)
        self.assertEqual(
            result.hosted_url,
            f"{test_hosted_public_url}/feed_stable_id/feed_stable_id-mocked_timestamp"
            f"/feed_stable_id-mocked_timestamp.zip",
        )
        self.assertEqual(result.file_sha256_hash, file_hash)
        self.assertEqual(upload_file_to_storage.call_count, 1)

    @patch("main.DatasetProcessor.upload_file_to_storage")
    @patch("main.DatasetProcessor.download_content")
    def test_upload_dataset_same_hash(
        self, mock_download_url_content, upload_file_to_storage
    ):
        """
        Test upload_dataset method of DatasetProcessor class with the hash from the latest one
        """
        mock_blob = MagicMock()
        mock_blob.public_url = public_url
        upload_file_to_storage.return_value = mock_blob
        mock_download_url_content.return_value = file_hash, True, "path/file"

        processor = DatasetProcessor(
            public_url,
            "feed_id",
            "feed_stable_id",
            "execution_id",
            file_hash,
            "bucket_name",
            0,
            None,
            test_hosted_public_url,
        )

        result = processor.upload_dataset()

        self.assertIsNone(result)
        upload_file_to_storage.blob.assert_not_called()
        mock_blob.make_public.assert_not_called()
        mock_download_url_content.assert_called_once()

    @patch("main.DatasetProcessor.upload_file_to_storage")
    @patch("main.DatasetProcessor.download_content")
    def test_upload_dataset_not_zip(
        self, mock_download_url_content, upload_file_to_storage
    ):
        """
        Test upload_dataset method of DatasetProcessor class with a non zip file
        """
        mock_blob = MagicMock()
        mock_blob.public_url = public_url
        upload_file_to_storage.return_value = mock_blob
        mock_download_url_content.return_value = file_hash, False, "path/file"

        processor = DatasetProcessor(
            public_url,
            "feed_id",
            "feed_stable_id",
            "execution_id",
            file_hash,
            "bucket_name",
            0,
            None,
            test_hosted_public_url,
        )

        result = processor.upload_dataset()

        self.assertIsNone(result)
        upload_file_to_storage.blob.assert_not_called()
        mock_blob.make_public.assert_not_called()
        mock_download_url_content.assert_called_once()

    @patch("main.DatasetProcessor.upload_file_to_storage")
    @patch("main.DatasetProcessor.download_content")
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
            test_hosted_public_url,
        )

        with self.assertRaises(Exception):
            processor.upload_dataset()

    def test_upload_file_to_storage(self):
        bucket_name = "test-bucket"
        source_file_path = "path/to/source/file"
        extracted_file_path = "path/to/source/file"

        mock_blob = Mock()
        mock_blob.public_url = public_url
        mock_bucket = Mock()
        mock_bucket.blob.return_value = mock_blob
        mock_client = Mock()
        mock_client.get_bucket.return_value = mock_bucket

        # Mock open function
        mock_file = mock_open()

        with patch("google.cloud.storage.Client", return_value=mock_client), patch(
            "builtins.open", mock_file
        ):
            processor = DatasetProcessor(
                public_url,
                "feed_id",
                "feed_stable_id",
                "execution_id",
                "latest_hash",
                bucket_name,
                0,
                None,
                test_hosted_public_url,
            )
            dataset_id = faker.Faker().uuid4()
            result, _ = processor.upload_file_to_storage(
                source_file_path, dataset_id, extracted_file_path
            )
            self.assertEqual(result.public_url, public_url)
            mock_client.get_bucket.assert_called_with(bucket_name)
            mock_bucket.blob.assert_called_with(
                f"feed_stable_id/{dataset_id}/{dataset_id}.zip"
            )
            mock_blob.upload_from_file.assert_called()

            # Assert that the file was opened in binary read mode
            mock_file.assert_called_with(source_file_path, "rb")

    @patch.dict(
        os.environ, {"FEEDS_CREDENTIALS": '{"test_stable_id": "test_credentials"}'}
    )
    @with_db_session(db_url=default_db_url)
    def test_process(self, db_session):
        feeds = db_session.query(Gtfsfeed).all()
        feed_id = feeds[0].id

        producer_url = "https://testproducer.com/data"
        feed_stable_id = "test_stable_id"
        execution_id = "test_execution_id"
        latest_hash = "old_hash"
        bucket_name = "test-bucket"
        authentication_type = 1
        api_key_parameter_name = "test_api_key"
        new_hash = "new_hash_value"

        processor = DatasetProcessor(
            producer_url,
            feed_id,
            feed_stable_id,
            execution_id,
            latest_hash,
            bucket_name,
            authentication_type,
            api_key_parameter_name,
            test_hosted_public_url,
        )

        processor.upload_dataset = MagicMock(
            return_value=DatasetFile(
                stable_id="test_stable_id",
                file_sha256_hash=new_hash,
                hosted_url="https://example.com/new_data",
            )
        )
        db_url = os.getenv("TEST_FEEDS_DATABASE_URL", default=default_db_url)
        os.environ["FEEDS_DATABASE_URL"] = db_url
        result = processor.process()

        self.assertIsNotNone(result)
        self.assertEqual(result.file_sha256_hash, new_hash)
        processor.upload_dataset.assert_called_once()

    @patch.dict(
        os.environ,
        {"FEEDS_CREDENTIALS": '{"not_what_u_r_looking_4": "test_credentials"}'},
    )
    @with_db_session(db_url=default_db_url)
    def test_fails_authenticated_feed_not_creds(self, db_session):
        feeds = db_session.query(Gtfsfeed).all()
        feed_id = feeds[0].id

        producer_url = "https://testproducer.com/data"
        feed_stable_id = "test_stable_id"
        execution_id = "test_execution_id"
        latest_hash = "old_hash"
        bucket_name = "test-bucket"
        authentication_type = 1
        api_key_parameter_name = "test_api_key"

        with self.assertRaises(Exception) as context:
            DatasetProcessor(
                producer_url,
                feed_id,
                feed_stable_id,
                execution_id,
                latest_hash,
                bucket_name,
                authentication_type,
                api_key_parameter_name,
                test_hosted_public_url,
            )
        self.assertEqual(
            str(context.exception),
            "Error getting feed credentials for feed test_stable_id",
        )

    @patch.dict(
        os.environ,
        {"FEEDS_CREDENTIALS": "not a JSON string"},
    )
    @with_db_session(db_url=default_db_url)
    def test_fails_authenticated_feed_creds_invalid(self, db_session):
        feeds = db_session.query(Gtfsfeed).all()
        feed_id = feeds[0].id

        producer_url = "https://testproducer.com/data"
        feed_stable_id = "test_stable_id"
        execution_id = "test_execution_id"
        latest_hash = "old_hash"
        bucket_name = "test-bucket"
        authentication_type = 1
        api_key_parameter_name = "test_api_key"

        with self.assertRaises(Exception) as context:
            DatasetProcessor(
                producer_url,
                feed_id,
                feed_stable_id,
                execution_id,
                latest_hash,
                bucket_name,
                authentication_type,
                api_key_parameter_name,
                test_hosted_public_url,
            )
        self.assertEqual(
            str(context.exception),
            "Error getting feed credentials for feed test_stable_id",
        )

    @patch.dict(
        os.environ, {"FEEDS_CREDENTIALS": '{"test_stable_id": "test_credentials"}'}
    )
    def test_process_no_change(self):
        feed_id = "test"
        producer_url = "https://testproducer.com/data"
        feed_stable_id = "test_stable_id"
        execution_id = "test_execution_id"
        latest_hash = "old_hash"
        bucket_name = "test-bucket"
        authentication_type = 1
        api_key_parameter_name = "test_api_key"

        processor = DatasetProcessor(
            producer_url,
            feed_id,
            feed_stable_id,
            execution_id,
            latest_hash,
            bucket_name,
            authentication_type,
            api_key_parameter_name,
            test_hosted_public_url,
        )

        processor.upload_dataset = MagicMock(return_value=None)
        processor.create_dataset = MagicMock()
        result = processor.process()

        self.assertIsNone(result)
        processor.create_dataset.assert_not_called()

    @patch("main.DatasetTraceService")
    @patch("main.DatasetProcessor")
    def test_process_dataset_normal_execution(
        self, mock_dataset_processor, mock_dataset_trace
    ):
        db_url = os.getenv("TEST_FEEDS_DATABASE_URL", default=default_db_url)
        os.environ["FEEDS_DATABASE_URL"] = db_url

        # Mock data for the CloudEvent
        mock_data = {
            "execution_id": "test_execution_id",
            "producer_url": "https://testproducer.com/data",
            "feed_stable_id": "test_stable_id",
            "feed_id": "test_feed_id",
            "dataset_id": "test_dataset_id",
            "dataset_hash": "test_dataset_hash",
            "authentication_type": 0,
            "api_key_parameter_name": None,
        }

        cloud_event = create_cloud_event(mock_data)

        # Mock the process method of DatasetProcessor
        mock_dataset_processor_instance = mock_dataset_processor.return_value
        mock_dataset_processor_instance.process.return_value = None

        mock_dataset_trace.save.return_value = None
        mock_dataset_trace.get_by_execution_and_stable_ids.return_value = 0
        # Call the function
        process_dataset(cloud_event)

        # Assertions
        mock_dataset_processor.assert_called_once()
        mock_dataset_processor_instance.process.assert_called_once()

    @patch("main.DatasetTraceService")
    @patch("main.DatasetProcessor")
    def test_process_dataset_exception_caught(
        self,
        mock_dataset_processor,
        mock_dataset_trace,
    ):
        db_url = os.getenv("TEST_FEEDS_DATABASE_URL", default=default_db_url)
        os.environ["FEEDS_DATABASE_URL"] = db_url

        # Mock empty data for the CloudEvent
        mock_data = {}

        cloud_event = create_cloud_event(mock_data)

        # Mock the process method of DatasetProcessor
        mock_dataset_processor_instance = mock_dataset_processor.return_value
        mock_dataset_processor_instance.process.return_value = None

        mock_dataset_trace.save.return_value = None
        mock_dataset_trace.get_by_execution_and_stable_ids.return_value = 0

        # Call the function
        process_dataset(cloud_event)

    @patch("main.DatasetTraceService")
    def test_process_dataset_missing_stable_id(self, mock_dataset_trace):
        db_url = os.getenv("TEST_FEEDS_DATABASE_URL", default=default_db_url)
        os.environ["FEEDS_DATABASE_URL"] = db_url

        # Mock data for the CloudEvent
        mock_data = {
            "execution_id": "test_execution_id",
            "producer_url": "https://testproducer.com/data",
            "feed_stable_id": "",
            "feed_id": "test_feed_id",
            "dataset_id": "test_dataset_id",
            "dataset_hash": "test_dataset_hash",
            "authentication_type": 0,
            "api_key_parameter_name": None,
        }

        cloud_event = create_cloud_event(mock_data)

        mock_dataset_trace.save.return_value = None
        mock_dataset_trace.get_by_execution_and_stable_ids.return_value = 0
        # Call the function
        result = process_dataset(cloud_event)
        assert (
            result
            == "Function completed with errors, missing stable= or execution_id=test_execution_id"
        )
