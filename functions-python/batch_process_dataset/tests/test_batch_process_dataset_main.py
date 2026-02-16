import base64
import datetime
import json
import os
import shutil
import unittest
from hashlib import sha256
from typing import Final
from unittest.mock import patch, MagicMock, Mock

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
    @classmethod
    def setUpClass(cls):
        """Set up test environment with a dedicated working directory"""
        # Use a test-specific working directory
        cls.test_working_dir = os.path.join(
            os.path.dirname(__file__), "test_working_dir"
        )
        os.makedirs(cls.test_working_dir, exist_ok=True)
        # Set the environment variable for all tests
        os.environ["WORKING_DIR"] = cls.test_working_dir

    @classmethod
    def tearDownClass(cls):
        """Clean up the test working directory after all tests"""
        if os.path.exists(cls.test_working_dir):
            shutil.rmtree(cls.test_working_dir, ignore_errors=True)

    @patch("main.DatasetProcessor.extract_and_upload_files_from_zip")
    @patch("main.DatasetProcessor.upload_dataset_zip_to_storage")
    @patch("main.DatasetProcessor.download_content")
    def test_upload_dataset_diff_hash(
        self,
        mock_download_url_content,
        mock_upload_dataset_zip,
        mock_extract_and_upload,
    ):
        """
        Test upload_dataset method of DatasetProcessor class with different hash from the latest one
        """
        mock_blob = MagicMock()
        mock_blob.public_url = public_url
        mock_blob.path = public_url

        # Mock the new methods used in transfer_dataset
        mock_upload_dataset_zip.return_value = mock_blob
        mock_extracted_files = []  # Empty list of extracted files
        mock_extract_and_upload.return_value = mock_extracted_files
        mock_download_url_content.return_value = file_hash, True

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
            result = processor.transfer_dataset("feed_id")

        self.assertIsNotNone(result)
        mock_download_url_content.assert_called_once()
        self.assertIsInstance(result, DatasetFile)
        self.assertEqual(
            result.hosted_url,
            f"{test_hosted_public_url}/feed_stable_id/feed_stable_id-mocked_timestamp"
            f"/feed_stable_id-mocked_timestamp.zip",
        )
        self.assertEqual(result.file_sha256_hash, file_hash)
        # Verify the new methods were called
        self.assertEqual(mock_upload_dataset_zip.call_count, 1)
        self.assertEqual(mock_extract_and_upload.call_count, 1)

    @patch("main.DatasetProcessor.download_content")
    def test_upload_dataset_same_hash(self, mock_download_url_content):
        """
        Test upload_dataset method of DatasetProcessor class with the hash from the latest one
        """
        mock_download_url_content.return_value = file_hash, True

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

        result = processor.transfer_dataset("feed_id")

        self.assertIsNone(result)
        mock_download_url_content.assert_called_once()

    @patch("main.DatasetProcessor.download_content")
    def test_upload_dataset_not_zip(self, mock_download_url_content):
        """
        Test upload_dataset method of DatasetProcessor class with a non zip file
        """
        mock_download_url_content.return_value = file_hash, False

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

        result = processor.transfer_dataset("feed_id")

        self.assertIsNone(result)
        mock_download_url_content.assert_called_once()

    @patch("main.DatasetProcessor.download_content")
    def test_upload_dataset_download_exception(self, mock_download_url_content):
        """
        Test upload_dataset method of DatasetProcessor class when download fails
        """
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
            processor.transfer_dataset("feed_id")

    @patch("main.get_hash_from_file", return_value="test_file_hash_123")
    @patch("main.os.path.getsize", return_value=1024)
    @patch("main.os.remove")
    @patch("main.storage.Client")
    @patch("main.zipfile.is_zipfile", return_value=True)
    def test_extract_and_upload_files_from_zip_success(
        self,
        _mock_is_zipfile,
        mock_storage_client,
        mock_remove,
        _mock_getsize,
        _mock_get_hash,
    ):
        """
        Test extract_and_upload_files_from_zip with a valid ZIP file containing multiple files
        """
        import tempfile
        import zipfile

        # Create a real temporary ZIP file with test content
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_zip:
            zip_path = tmp_zip.name
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("stops.txt", "stop_id,stop_name\n1,Stop A\n")
                zf.writestr("routes.txt", "route_id,route_name\n1,Route 1\n")
                # Add a directory to test that it's skipped
                zf.writestr("subfolder/", "")

        try:
            # Setup mocks
            mock_blob = Mock()
            mock_blob.public_url = (
                "https://storage.googleapis.com/bucket/feed/dataset/extracted/stops.txt"
            )
            mock_bucket = Mock()
            mock_bucket.blob.return_value = mock_blob
            mock_client = Mock()
            mock_client.get_bucket.return_value = mock_bucket
            mock_storage_client.return_value = mock_client

            # Create processor
            processor = DatasetProcessor(
                producer_url="https://example.com/feed.zip",
                feed_id="test_feed_id",
                feed_stable_id="test_feed",
                execution_id="exec_123",
                latest_hash="hash123",
                bucket_name="test-bucket",
                authentication_type=0,
                api_key_parameter_name=None,
                public_hosted_datasets_url="https://public.example.com",
            )

            # Call the method
            result = processor.extract_and_upload_files_from_zip(
                zip_file_path=zip_path,
                dataset_stable_id="dataset_123",
                public=True,
            )

            # Assertions
            self.assertEqual(len(result), 2)  # 2 files, directory should be skipped
            self.assertEqual(result[0].file_name, "stops.txt")
            self.assertEqual(result[1].file_name, "routes.txt")
            self.assertEqual(result[0].file_size_bytes, 1024)
            self.assertEqual(result[0].hash, "test_file_hash_123")
            self.assertEqual(result[0].hosted_url, mock_blob.public_url)

            # Verify bucket.blob was called for each file
            self.assertEqual(mock_bucket.blob.call_count, 2)
            mock_bucket.blob.assert_any_call(
                "test_feed/dataset_123/extracted/stops.txt"
            )
            mock_bucket.blob.assert_any_call(
                "test_feed/dataset_123/extracted/routes.txt"
            )

            # Verify upload was called for each file
            self.assertEqual(mock_blob.upload_from_filename.call_count, 2)

            # Verify make_public was called (public=True)
            self.assertEqual(mock_blob.make_public.call_count, 2)

            # Verify cleanup (os.remove) was called for each extracted file
            self.assertEqual(mock_remove.call_count, 2)

        finally:
            # Cleanup the temporary ZIP file
            if os.path.exists(zip_path):
                os.remove(zip_path)

    @patch("main.storage.Client")
    @patch("main.zipfile.is_zipfile", return_value=True)
    def test_extract_and_upload_files_from_zip_not_public(
        self, mock_is_zipfile, mock_storage_client
    ):
        """
        Test extract_and_upload_files_from_zip with public=False
        """
        import tempfile
        import zipfile

        # Create a real temporary ZIP file
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_zip:
            zip_path = tmp_zip.name
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("agency.txt", "agency_id,agency_name\n1,Agency\n")

        try:
            # Setup mocks
            mock_blob = Mock()
            mock_blob.public_url = "https://storage.googleapis.com/bucket/feed/dataset/extracted/agency.txt"
            mock_bucket = Mock()
            mock_bucket.blob.return_value = mock_blob
            mock_client = Mock()
            mock_client.get_bucket.return_value = mock_bucket
            mock_storage_client.return_value = mock_client

            processor = DatasetProcessor(
                producer_url="https://example.com/feed.zip",
                feed_id="test_feed_id",
                feed_stable_id="test_feed",
                execution_id="exec_123",
                latest_hash="hash123",
                bucket_name="test-bucket",
                authentication_type=0,
                api_key_parameter_name=None,
                public_hosted_datasets_url="https://public.example.com",
            )

            # Call with public=False
            result = processor.extract_and_upload_files_from_zip(
                zip_file_path=zip_path,
                dataset_stable_id="dataset_456",
                public=False,
            )

            # Assertions
            self.assertEqual(len(result), 1)
            self.assertIsNone(result[0].hosted_url)  # Should be None when public=False

            # Verify make_public was NOT called
            mock_blob.make_public.assert_not_called()

        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)

    @patch("main.zipfile.is_zipfile", return_value=False)
    def test_extract_and_upload_files_from_zip_invalid_zip(self, mock_is_zipfile):
        """
        Test extract_and_upload_files_from_zip with an invalid ZIP file
        """
        import tempfile

        # Create a temporary non-ZIP file
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp_file:
            tmp_file.write(b"This is not a ZIP file")
            file_path = tmp_file.name

        try:
            processor = DatasetProcessor(
                producer_url="https://example.com/feed.zip",
                feed_id="test_feed_id",
                feed_stable_id="test_feed",
                execution_id="exec_123",
                latest_hash="hash123",
                bucket_name="test-bucket",
                authentication_type=0,
                api_key_parameter_name=None,
                public_hosted_datasets_url="https://public.example.com",
            )

            # Should raise ValueError for invalid ZIP
            with self.assertRaises(ValueError) as context:
                processor.extract_and_upload_files_from_zip(
                    zip_file_path=file_path,
                    dataset_stable_id="dataset_789",
                    public=True,
                )

            self.assertIn("not a valid ZIP file", str(context.exception))

        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    @patch("main.get_hash_from_file", return_value="hash_abc")
    @patch("main.storage.Client")
    @patch("main.zipfile.is_zipfile", return_value=True)
    def test_extract_and_upload_files_from_zip_cleanup_failure(
        self, mock_is_zipfile, mock_storage_client, mock_get_hash
    ):
        """
        Test that cleanup failures are caught and logged but don't stop processing
        """
        import tempfile
        import zipfile

        # Create a real temporary ZIP file
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_zip:
            zip_path = tmp_zip.name
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("test.txt", "test content\n")

        try:
            # Setup mocks
            mock_blob = Mock()
            mock_blob.public_url = "https://storage.googleapis.com/bucket/file.txt"
            mock_bucket = Mock()
            mock_bucket.blob.return_value = mock_blob
            mock_client = Mock()
            mock_client.get_bucket.return_value = mock_bucket
            mock_storage_client.return_value = mock_client

            processor = DatasetProcessor(
                producer_url="https://example.com/feed.zip",
                feed_id="test_feed_id",
                feed_stable_id="test_feed",
                execution_id="exec_123",
                latest_hash="hash123",
                bucket_name="test-bucket",
                authentication_type=0,
                api_key_parameter_name=None,
                public_hosted_datasets_url="https://public.example.com",
            )

            # Mock os.remove to fail only for extracted files (not the ZIP itself)
            original_remove = os.remove

            def mock_remove_side_effect(path):
                # Only raise exception for extracted files, not the ZIP file
                if "in-memory" in path and path != zip_path:
                    raise Exception("Cleanup failed")
                else:
                    # Allow cleanup of the ZIP file to succeed
                    original_remove(path)

            with patch("main.os.remove", side_effect=mock_remove_side_effect):
                # Should not raise exception even though cleanup fails
                result = processor.extract_and_upload_files_from_zip(
                    zip_file_path=zip_path,
                    dataset_stable_id="dataset_cleanup",
                    public=True,
                )

                # Should still return the file
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0].file_name, "test.txt")

        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)

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

        processor.transfer_dataset = MagicMock(
            return_value=DatasetFile(
                stable_id="test_stable_id",
                file_sha256_hash=new_hash,
                hosted_url="https://example.com/new_data",
            )
        )
        db_url = os.getenv("TEST_FEEDS_DATABASE_URL", default=default_db_url)
        os.environ["FEEDS_DATABASE_URL"] = db_url
        result = processor.process_from_producer_url(feed_id)

        self.assertIsNotNone(result)
        self.assertEqual(result.file_sha256_hash, new_hash)
        processor.transfer_dataset.assert_called_once()

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

        processor.transfer_dataset = MagicMock(return_value=None)
        processor.create_dataset_entities = MagicMock()
        result = processor.process_from_producer_url(feed_id)

        self.assertIsNone(result)
        processor.create_dataset_entities.assert_not_called()

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
        mock_dataset_processor_instance.process_from_producer_url.return_value = None

        mock_dataset_trace.save.return_value = None
        mock_dataset_trace.get_by_execution_and_stable_ids.return_value = 0
        # Call the function
        process_dataset(cloud_event)

        # Assertions
        mock_dataset_processor.assert_called_once()
        mock_dataset_processor_instance.process_from_producer_url.assert_called_once()

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
        mock_dataset_processor_instance.process_from_producer_url.return_value = None

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

    @patch.dict(os.environ, {"DATASETS_BUCKET_NAME": "test-bucket"})
    @patch("main.create_pipeline_tasks")
    @patch("main.DatasetProcessor.create_dataset_entities")
    @patch("main.DatasetProcessor.extract_and_upload_files_from_zip")
    @patch("main.download_from_gcs")
    def test_process_from_bucket_latest_happy_path(
        self,
        mock_download_from_gcs,
        mock_extract_and_upload,
        mock_create_dataset_entities,
        _,
    ):
        # Arrange
        mock_extracted_files = []  # Empty list of extracted files
        mock_extract_and_upload.return_value = mock_extracted_files

        processor = DatasetProcessor(
            producer_url="https://ignored-in-bucket-mode.example.com/feed.zip",
            feed_id="feed_id",
            feed_stable_id="feed_stable_id",
            execution_id="execution_id",
            latest_hash="latest_hash_value",
            bucket_name="test-bucket",  # instance field (method currently reads env, but keep consistent)
            authentication_type=0,
            api_key_parameter_name=None,
            public_hosted_datasets_url="https://hosted.example.com",
            dataset_stable_id="dataset-stable-id-123",  # REQUIRED for bucket-latest path
        )

        mock_create_dataset_entities.return_value = Mock(), True
        # Act
        result = processor.process_from_bucket(public=True)

        # Assert: function returns a DatasetFile
        self.assertIsNotNone(result)
        self.assertIsInstance(result, DatasetFile)

        # Assert: downloads from the bucket latest.zip for this feed
        mock_download_from_gcs.assert_called_once()
        args, kwargs = mock_download_from_gcs.call_args
        self.assertEqual(args[0], "test-bucket")  # bucket name
        self.assertEqual(
            args[1], "feed_stable_id/dataset-stable-id-123/dataset-stable-id-123.zip"
        )  # blob path
        self.assertIsNotNone(
            args[2]
        )  # temp file path (random), so just ensure it exists
        self.assertNotEqual(args[2], "")  # sanity

        # Assert: extract_and_upload_files_from_zip was called with the dataset stable ID
        mock_extract_and_upload.assert_called_once()
        extract_args, extract_kwargs = mock_extract_and_upload.call_args
        # First arg should be the temp zip path, second arg should be dataset_stable_id
        self.assertEqual(extract_args[1], "dataset-stable-id-123")
        self.assertEqual(extract_kwargs.get("public"), True)

        # Assert: DB update called with skip_dataset_creation=True and a DatasetFile-like object
        mock_create_dataset_entities.assert_called_once()
        c_args, c_kwargs = mock_create_dataset_entities.call_args
        self.assertIn("skip_dataset_creation", c_kwargs)
        self.assertTrue(c_kwargs["skip_dataset_creation"])
        # first positional arg should be the dataset_file object
        self.assertEqual(len(c_args), 1)
        self.assertTrue(hasattr(c_args[0], "stable_id"))
        self.assertEqual(c_args[0].stable_id, "dataset-stable-id-123")
        self.assertTrue(hasattr(c_args[0], "file_sha256_hash"))
        self.assertEqual(c_args[0].file_sha256_hash, "latest_hash_value")
        self.assertEqual(c_args[0].file_sha256_hash, "latest_hash_value")

    @with_db_session(db_url=default_db_url)
    def test_create_dataset_entities_update_existing(self, db_session):
        """
        Test create_dataset_entities when updating an existing dataset (skip_dataset_creation=True)
        This specifically tests lines 457-468 of main.py
        """
        from shared.database_gen.sqlacodegen_models import Gtfsfeed, Gtfsdataset

        # Use an existing feed from the database to avoid foreign key issues
        feeds = db_session.query(Gtfsfeed).all()
        if not feeds:
            self.skipTest("No feeds available in test database")

        test_feed = feeds[0]

        # Create an existing dataset for this feed
        existing_dataset = Gtfsdataset(
            id="existing_dataset_update_test",
            feed_id=test_feed.id,
            stable_id="dataset_existing_update",
            hash="old_hash",
            hosted_url="https://storage.example.com/old.zip",
            gtfsfiles=[],
            zipped_size_bytes=1000,
            unzipped_size_bytes=2000,
        )

        test_feed.latest_dataset = existing_dataset
        db_session.add(existing_dataset)
        db_session.commit()

        processor = DatasetProcessor(
            producer_url="https://example.com/feed.zip",
            feed_id=test_feed.id,
            feed_stable_id=test_feed.stable_id,
            execution_id="exec_456",
            latest_hash="new_hash",
            bucket_name="test-bucket",
            authentication_type=0,
            api_key_parameter_name=None,
            public_hosted_datasets_url="https://public.example.com",
        )

        # Create dataset file with new extracted files
        from main import Gtfsfile

        dataset_file = DatasetFile(
            stable_id="dataset_existing_update",
            file_sha256_hash="new_hash",
            hosted_url="https://storage.example.com/feed/dataset.zip",
            extracted_files=[
                Gtfsfile(
                    id="file3",
                    file_name="agency.txt",
                    file_size_bytes=512,
                    hosted_url="https://storage.example.com/feed/agency.txt",
                    hash="agency_hash",
                ),
            ],
            zipped_size=3000,
        )

        # Mock create_refresh_materialized_view_task inside the test
        with patch("main.create_refresh_materialized_view_task") as mock_refresh_task:
            # Call with skip_dataset_creation=True to test the selected code branch
            result_dataset, is_latest = processor.create_dataset_entities(
                dataset_file=dataset_file,
                db_session=db_session,
                skip_dataset_creation=True,
            )

            # Assertions - should return the existing dataset updated
            self.assertIsNotNone(result_dataset)
            self.assertEqual(result_dataset.id, "existing_dataset_update_test")

            # Verify line 462-463: latest_dataset.gtfsfiles updated
            self.assertEqual(len(result_dataset.gtfsfiles), 1)
            self.assertEqual(result_dataset.gtfsfiles[0].file_name, "agency.txt")

            # Verify line 464: latest_dataset.zipped_size_bytes updated
            self.assertEqual(result_dataset.zipped_size_bytes, 3000)

            # Verify line 465-467: latest_dataset.unzipped_size_bytes updated
            self.assertEqual(result_dataset.unzipped_size_bytes, 512)

            mock_refresh_task.assert_called_once()

    @with_db_session(db_url=default_db_url)
    def test_create_dataset_entities_update_existing_no_files(self, db_session):
        """
        Test create_dataset_entities with skip_dataset_creation=True and no extracted files
        This tests the else branch on line 462: dataset_file.extracted_files else []
        """
        from shared.database_gen.sqlacodegen_models import Gtfsfeed, Gtfsdataset

        # Use an existing feed from the database
        feeds = db_session.query(Gtfsfeed).all()
        if not feeds:
            self.skipTest("No feeds available in test database")

        test_feed = feeds[0]

        # Create an existing dataset for this feed
        existing_dataset = Gtfsdataset(
            id="existing_dataset_no_files_test",
            feed_id=test_feed.id,
            stable_id="dataset_no_files_test",
            hash="old_hash",
            hosted_url="https://storage.example.com/old.zip",
            gtfsfiles=[],
            zipped_size_bytes=1000,
            unzipped_size_bytes=2000,
        )

        test_feed.latest_dataset = existing_dataset
        db_session.add(existing_dataset)
        db_session.commit()

        processor = DatasetProcessor(
            producer_url="https://example.com/feed.zip",
            feed_id=test_feed.id,
            feed_stable_id=test_feed.stable_id,
            execution_id="exec_789",
            latest_hash="new_hash",
            bucket_name="test-bucket",
            authentication_type=0,
            api_key_parameter_name=None,
            public_hosted_datasets_url="https://public.example.com",
        )

        # Create dataset file with NO extracted files (None)
        dataset_file = DatasetFile(
            stable_id="dataset_no_files_test",
            file_sha256_hash="new_hash",
            hosted_url="https://storage.example.com/feed/dataset.zip",
            extracted_files=None,  # Test the else branch
            zipped_size=5000,
        )

        # Mock create_refresh_materialized_view_task inside the test
        with patch("main.create_refresh_materialized_view_task") as mock_refresh_task:
            # Call with skip_dataset_creation=True
            result_dataset, is_latest = processor.create_dataset_entities(
                dataset_file=dataset_file,
                db_session=db_session,
                skip_dataset_creation=True,
            )

            # Assertions
            self.assertIsNotNone(result_dataset)
            self.assertEqual(len(result_dataset.gtfsfiles), 0)  # Should be empty list
            self.assertEqual(result_dataset.zipped_size_bytes, 5000)
            self.assertIsNone(result_dataset.unzipped_size_bytes)  # None when no files

            mock_refresh_task.assert_called_once()
