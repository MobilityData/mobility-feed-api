import base64
import datetime
import json
import os
import tempfile
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
    @patch("main.DatasetProcessor.upload_files_to_storage")
    @patch("main.DatasetProcessor.download_content")
    @patch("main.DatasetProcessor.unzip_files")
    def test_upload_dataset_diff_hash(
        self, mock_unzip_files, mock_download_url_content, upload_files_to_storage
    ):
        """
        Test upload_dataset method of DatasetProcessor class with different hash from the latest one
        """
        mock_blob = MagicMock()
        mock_blob.public_url = public_url
        mock_blob.path = public_url
        upload_files_to_storage.return_value = mock_blob, []
        mock_download_url_content.return_value = file_hash, True
        mock_unzip_files.return_value = [mock_blob, mock_blob]

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
            result = processor.upload_dataset("feed_id")

        self.assertIsNotNone(result)
        mock_download_url_content.assert_called_once()
        self.assertIsInstance(result, DatasetFile)
        self.assertEqual(
            result.hosted_url,
            f"{test_hosted_public_url}/feed_stable_id/feed_stable_id-mocked_timestamp"
            f"/feed_stable_id-mocked_timestamp.zip",
        )
        self.assertEqual(result.file_sha256_hash, file_hash)
        self.assertEqual(upload_files_to_storage.call_count, 1)

    @patch("main.DatasetProcessor.upload_files_to_storage")
    @patch("main.DatasetProcessor.download_content")
    def test_upload_dataset_same_hash(
        self, mock_download_url_content, upload_files_to_storage
    ):
        """
        Test upload_dataset method of DatasetProcessor class with the hash from the latest one
        """
        mock_blob = MagicMock()
        mock_blob.public_url = public_url
        upload_files_to_storage.return_value = mock_blob
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

        result = processor.upload_dataset("feed_id")

        self.assertIsNone(result)
        upload_files_to_storage.blob.assert_not_called()
        mock_blob.make_public.assert_not_called()
        mock_download_url_content.assert_called_once()

    @patch("main.DatasetProcessor.upload_files_to_storage")
    @patch("main.DatasetProcessor.download_content")
    def test_upload_dataset_not_zip(
        self, mock_download_url_content, upload_files_to_storage
    ):
        """
        Test upload_dataset method of DatasetProcessor class with a non zip file
        """
        mock_blob = MagicMock()
        mock_blob.public_url = public_url
        upload_files_to_storage.return_value = mock_blob
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

        result = processor.upload_dataset("feed_id")

        self.assertIsNone(result)
        upload_files_to_storage.blob.assert_not_called()
        mock_blob.make_public.assert_not_called()
        mock_download_url_content.assert_called_once()

    @patch("main.DatasetProcessor.upload_files_to_storage")
    @patch("main.DatasetProcessor.download_content")
    def test_upload_dataset_download_exception(
        self, mock_download_url_content, upload_files_to_storage
    ):
        """
        Test upload_dataset method of DatasetProcessor class with the hash from the latest one
        """
        mock_blob = MagicMock()
        mock_blob.public_url = public_url
        upload_files_to_storage.return_value = mock_blob
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
            processor.upload_dataset("feed_id")

    def test_upload_files_to_storage(self):
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
            result, _ = processor.upload_files_to_storage(
                source_file_path, dataset_id, extracted_file_path
            )
            self.assertEqual(result.public_url, public_url)
            mock_client.get_bucket.assert_called_with(bucket_name)
            mock_bucket.blob.assert_called_with(
                f"feed_stable_id/{dataset_id}/{dataset_id}.zip"
            )
            mock_blob.upload_from_filename.assert_called()

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
        result = processor.process_from_producer_url(feed_id)

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
    @patch("main.DatasetProcessor.upload_files_to_storage")
    @patch("main.DatasetProcessor.unzip_files")
    @patch("main.download_from_gcs")
    def test_process_from_bucket_latest_happy_path(
        self,
        mock_download_from_gcs,
        mock_unzip_files,
        mock_upload_files_to_storage,
        mock_create_dataset_entities,
        _,
    ):
        # Arrange
        mock_blob = MagicMock()
        mock_upload_files_to_storage.return_value = (
            mock_blob,
            [],
        )  # (blob, extracted_files)
        mock_unzip_files.return_value = (
            "/tmp/extracted"  # not used deeply because upload is mocked
        )

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

        # Assert: function returns None in current implementation
        self.assertIsNone(result.zipped_size)

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

        # Assert: upload of extracted files happened with skip_dataset_upload=True
        mock_upload_files_to_storage.assert_called_once()
        u_args, u_kwargs = mock_upload_files_to_storage.call_args
        # args: (source_file_path, dataset_stable_id, extracted_files_path, ...)
        self.assertEqual(u_args[1], "dataset-stable-id-123")
        self.assertEqual(u_kwargs.get("skip_dataset_upload"), True)

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

    @patch("main.get_hash_from_file", return_value="fakehash123")
    @patch("google.cloud.storage.Client")
    def test_upload_files_to_storage_branches(self, mock_client_cls, mock_get_hash):
        # Arrange global mocks
        mock_blob_latest = Mock()
        mock_blob_versioned = Mock()
        mock_blob_extracted = Mock()

        # configure bucket.blob() to return different blobs in sequence
        mock_bucket = Mock()
        # First call scenario (dataset uploads happen): two blobs for latest.zip + versioned.zip
        # Second call scenario (skip dataset upload): blobs created only for extracted file(s)
        blob_side_effects = [mock_blob_latest, mock_blob_versioned, mock_blob_extracted]
        mock_bucket.blob.side_effect = blob_side_effects

        mock_client = Mock()
        mock_client.get_bucket.return_value = mock_bucket
        mock_client_cls.return_value = mock_client

        # Create processor
        from main import DatasetProcessor

        processor = DatasetProcessor(
            producer_url="https://example.com/feed.zip",
            feed_id="feed_id",
            feed_stable_id="feed_stable_id",
            execution_id="execution_id",
            latest_hash="hash",
            bucket_name="bucket-name",
            authentication_type=0,
            api_key_parameter_name=None,
            public_hosted_datasets_url="https://public-hosted",
        )

        # --- SCENARIO A: extracted path DOES NOT exist; dataset uploaded (skip_dataset_upload=False)
        src_path = "/tmp/fake-src.zip"  # not read, only passed to upload_from_filename
        dataset_id_A = "datasetA"
        non_existing_path = "/tmp/this/path/does/not/exist"

        result_blob_A, extracted_A = processor.upload_files_to_storage(
            source_file_path=src_path,
            dataset_stable_id=dataset_id_A,
            extracted_files_path=non_existing_path,
            public=True,
            skip_dataset_upload=False,
        )

        # Asserts Scenario A
        self.assertIs(result_blob_A, mock_blob_versioned)  # last dataset upload blob
        self.assertEqual(extracted_A, [])  # no extracted files
        # two dataset uploads: latest.zip + versioned zip
        self.assertEqual(mock_bucket.blob.call_count, 2)
        mock_blob_latest.upload_from_filename.assert_called_once_with(src_path)
        mock_blob_versioned.upload_from_filename.assert_called_once_with(src_path)

        # --- SCENARIO B: extracted path EXISTS; includes a file and a directory
        with tempfile.TemporaryDirectory() as tmpdir:
            extracted_dir = os.path.join(tmpdir, "extracted")
            os.makedirs(extracted_dir, exist_ok=True)
            # create one file
            file_path = os.path.join(extracted_dir, "stops.txt")
            with open(file_path, "wb") as f:
                f.write(b"stop_id,stop_name\n1,A\n")
            # create a subdirectory to ensure we skip non-files
            os.makedirs(os.path.join(extracted_dir, "subdir"), exist_ok=True)

            dataset_id_B = "datasetB"
            # Reset call counters for clarity
            mock_bucket.blob.reset_mock()

            result_blob_B, extracted_B = processor.upload_files_to_storage(
                source_file_path=src_path,
                dataset_stable_id=dataset_id_B,
                extracted_files_path=extracted_dir,
                public=False,  # ensure no make_public called
                skip_dataset_upload=True,  # skip dataset zips
            )

            # Asserts Scenario B
            self.assertIsNone(result_blob_B)  # because skip_dataset_upload=True
            # Only one extracted file should be uploaded
            self.assertEqual(len(extracted_B), 1)
            self.assertEqual(extracted_B[0].file_name, "stops.txt")
            self.assertEqual(extracted_B[0].file_size_bytes, os.path.getsize(file_path))
            self.assertEqual(extracted_B[0].hash, "fakehash123")
            self.assertIsNone(extracted_B[0].hosted_url)  # public=False → no hosted_url

            # bucket.blob called once for the extracted file
            mock_bucket.blob.assert_called_once_with(
                f"feed_stable_id/{dataset_id_B}/extracted/stops.txt"
            )
            mock_blob_extracted.upload_from_filename.assert_called_once_with(file_path)
            # No make_public in this branch
            self.assertFalse(getattr(mock_blob_extracted, "make_public").called)

        # Sanity: hash function used for extracted file
        mock_get_hash.assert_called_with(file_path)
