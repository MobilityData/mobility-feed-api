#
#   MobilityData 2025
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#


import os
import unittest
from datetime import datetime
from unittest.mock import mock_open
from unittest.mock import patch, MagicMock

from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.helpers.tests.test_shared.test_utils.database_utils import default_db_url
from tasks.dataset_files.rebuild_missing_dataset_files import (
    rebuild_missing_dataset_files,
    rebuild_missing_dataset_files_handler,
    get_datasets_with_missing_files_query,
    process_dataset,
)


class TestRebuildMissingDatasetFiles(unittest.TestCase):
    def setUp(self):
        os.environ["DATASETS_BUCKET_NAME"] = "mock_bucket"

    @patch(
        "tasks.dataset_files.rebuild_missing_dataset_files.rebuild_missing_dataset_files"
    )
    def test_handler_calls_main_function(self, mock_rebuild_func):
        mock_rebuild_func.return_value = {"message": "test", "total_processed": 0}
        payload = {"dry_run": True, "after_date": "2024-01-01", "latest_only": False}

        response = rebuild_missing_dataset_files_handler(payload)

        self.assertEqual(response["message"], "test")
        mock_rebuild_func.assert_called_once_with(
            dry_run=True, after_date="2024-01-01", latest_only=False
        )

    @with_db_session(db_url=default_db_url)
    def test_get_datasets_with_missing_files_query_filters(self, db_session: Session):
        after_date = datetime(2024, 1, 1)
        query = get_datasets_with_missing_files_query(
            db_session, after_date, latest_only=True
        )
        sql = str(query)
        self.assertIn("gtfsdataset.downloaded_at", sql)
        self.assertIn("gtfsdataset.latest", sql)

    @with_db_session(db_url=default_db_url)
    @patch("tasks.dataset_files.rebuild_missing_dataset_files.process_dataset")
    def test_rebuild_missing_dataset_files_dry_run(
        self, process_mock, db_session: Session
    ):
        response = rebuild_missing_dataset_files(
            db_session=db_session,
            dry_run=True,
            after_date="2023-01-01",
            latest_only=True,
        )

        self.assertIn("Dry run", response["message"])
        process_mock.assert_not_called()

    @with_db_session(db_url=default_db_url)
    @patch("tasks.dataset_files.rebuild_missing_dataset_files.process_dataset")
    def test_rebuild_missing_dataset_files_processing(
        self, process_mock, db_session: Session
    ):
        response = rebuild_missing_dataset_files(
            db_session=db_session,
            dry_run=False,
            after_date=None,
            latest_only=True,
        )

        self.assertIn("completed", response["message"])
        self.assertGreaterEqual(response["total_processed"], 0)
        self.assertTrue(process_mock.called or response["total_processed"] == 0)

    @patch("builtins.open", new_callable=mock_open)
    @patch("tasks.dataset_files.rebuild_missing_dataset_files.urllib.request.urlopen")
    @patch("tasks.dataset_files.rebuild_missing_dataset_files.storage.Client")
    @patch("tasks.dataset_files.rebuild_missing_dataset_files.zipfile.ZipFile")
    @patch(
        "tasks.dataset_files.rebuild_missing_dataset_files.tempfile.TemporaryDirectory"
    )
    def test_process_dataset_latest(
        self, tmpdir_mock, zipfile_mock, storage_mock, urlopen_mock, open_mock
    ):
        dataset = MagicMock()
        dataset.hosted_url = "http://example.com"
        dataset.stable_id = "mock-id"
        dataset.latest = True

        tmpdir_mock.return_value.__enter__.return_value = "/tmp/test"
        zipfile_mock.return_value.__enter__.return_value.extractall = MagicMock()

        mock_response = MagicMock()
        mock_response.read = MagicMock(side_effect=[b"zip content", b""])
        urlopen_mock.return_value.__enter__.return_value = mock_response

        mock_file = MagicMock()
        mock_file.read.return_value = b"file content"
        open_mock.return_value.__enter__.return_value = mock_file

        mock_blob = MagicMock()
        mock_blob.upload_from_filename = MagicMock()
        mock_blob.make_public = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        storage_mock.return_value.bucket.return_value = mock_bucket

        with patch("os.path.getsize", return_value=123), patch(
            "os.walk", return_value=[("/tmp/test", [], ["file1.txt"])]
        ):
            process_dataset(dataset)

        file_obj = dataset.gtfsfiles[0]
        self.assertEqual(file_obj.file_name, "file1.txt")
        self.assertIsNotNone(file_obj.hosted_url)
        mock_blob.upload_from_filename.assert_called_once()
        mock_blob.make_public.assert_called_once()

    @patch("builtins.open", new_callable=mock_open)
    @patch("tasks.dataset_files.rebuild_missing_dataset_files.urllib.request.urlopen")
    @patch("tasks.dataset_files.rebuild_missing_dataset_files.storage.Client")
    @patch("tasks.dataset_files.rebuild_missing_dataset_files.zipfile.ZipFile")
    @patch(
        "tasks.dataset_files.rebuild_missing_dataset_files.tempfile.TemporaryDirectory"
    )
    def test_process_dataset_not_latest(
        self, tmpdir_mock, zipfile_mock, storage_mock, urlopen_mock, open_mock
    ):
        dataset = MagicMock()
        dataset.hosted_url = "http://example.com"
        dataset.stable_id = "mock-id"
        dataset.latest = False

        tmpdir_mock.return_value.__enter__.return_value = "/tmp/test"
        zipfile_mock.return_value.__enter__.return_value.extractall = MagicMock()

        mock_response = MagicMock()
        mock_response.read = MagicMock(side_effect=[b"zip content", b""])
        urlopen_mock.return_value.__enter__.return_value = mock_response

        mock_file = MagicMock()
        mock_file.read.return_value = b"file content"
        open_mock.return_value.__enter__.return_value = mock_file

        mock_blob = MagicMock()
        mock_blob.upload_from_filename = MagicMock()
        mock_blob.make_public = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        storage_mock.return_value.bucket.return_value = mock_bucket

        with patch("os.path.getsize", return_value=123), patch(
            "os.walk", return_value=[("/tmp/test", [], ["file1.txt"])]
        ):
            process_dataset(dataset)

        file_obj = dataset.gtfsfiles[0]
        self.assertEqual(file_obj.file_name, "file1.txt")
        self.assertIsNone(file_obj.hosted_url)
        mock_blob.upload_from_filename.assert_not_called()
        mock_blob.make_public.assert_not_called()
