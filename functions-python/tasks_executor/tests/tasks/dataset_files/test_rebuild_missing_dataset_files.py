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
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.helpers.tests.test_shared.test_utils.database_utils import default_db_url
from tasks.dataset_files.rebuild_missing_dataset_files import (
    rebuild_missing_dataset_files,
    rebuild_missing_dataset_files_handler,
    get_datasets_with_missing_files_query,
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
            dry_run=True, after_date="2024-01-01", latest_only=False, dataset_id=None
        )

    @with_db_session(db_url=default_db_url)
    def test_get_datasets_with_missing_files_query_filters(self, db_session: Session):
        after_date = datetime(2024, 1, 1)
        query = get_datasets_with_missing_files_query(
            db_session, after_date, latest_only=True
        )
        sql = str(query)
        self.assertIn("gtfsdataset.downloaded_at", sql)
        self.assertIn(
            "(feed JOIN gtfsfeed ON feed.id = gtfsfeed.id) "
            "ON gtfsfeed.latest_dataset_id = gtfsdataset.id",
            sql,
        )

    @with_db_session(db_url=default_db_url)
    @patch("tasks.dataset_files.rebuild_missing_dataset_files.publish_messages")
    def test_rebuild_missing_dataset_files_dry_run(
        self, publish_mock, db_session: Session
    ):
        response = rebuild_missing_dataset_files(
            db_session=db_session,
            dry_run=True,
            after_date="2023-01-01",
            latest_only=True,
        )

        self.assertIn("Dry run", response["message"])
        publish_mock.assert_not_called()

    @with_db_session(db_url=default_db_url)
    @patch("tasks.dataset_files.rebuild_missing_dataset_files.publish_messages")
    def test_rebuild_missing_dataset_files_processing(
        self, publish_mock, db_session: Session
    ):
        response = rebuild_missing_dataset_files(
            db_session=db_session,
            dry_run=False,
            after_date=None,
            latest_only=True,
        )

        self.assertIn("completed", response["message"])
        self.assertGreaterEqual(response["total_processed"], 0)
        self.assertTrue(publish_mock.called or response["total_processed"] == 0)


class TestRebuildSpecificDatasetFiles(unittest.TestCase):
    @patch(
        "tasks.dataset_files.rebuild_missing_dataset_files.rebuild_missing_dataset_files"
    )
    def test_handler_calls_main_function(self, mock_rebuild_func):
        mock_rebuild_func.return_value = {"message": "test", "total_processed": 0}
        payload = {"dry_run": True, "after_date": "2024-01-01", "latest_only": False}

        response = rebuild_missing_dataset_files_handler(payload)

        self.assertEqual(response["message"], "test")
        mock_rebuild_func.assert_called_once_with(
            dry_run=True, after_date="2024-01-01", latest_only=False, dataset_id=None
        )

    @patch(
        "tasks.dataset_files.rebuild_missing_dataset_files.rebuild_missing_dataset_files"
    )
    def test_handler_forwards_dataset_id(self, mock_rebuild_func):
        payload = {
            "dry_run": False,
            "after_date": None,
            "latest_only": True,
            "dataset_id": "ds-123",
        }

        rebuild_missing_dataset_files_handler(payload)

        mock_rebuild_func.assert_called_once_with(
            dry_run=False, after_date=None, latest_only=True, dataset_id="ds-123"
        )

    def test_rebuild_with_specific_dataset_id_publishes_one_message(self):
        dataset_stable_id = "ds-123"
        fake_feed = SimpleNamespace(
            producer_url="https://example.com",
            stable_id="feed-stable",
            id=42,
            authentication_type=None,
            authentication_info_url=None,
            api_key_parameter_name=None,
        )
        fake_dataset = SimpleNamespace(
            stable_id=dataset_stable_id, hash="abc123", feed=fake_feed
        )

        # Mock the chained SQLAlchemy calls:
        # db_session.query(Gtfsdataset).filter(...).options(...).count()/all()
        db_session = MagicMock()
        query_mock = MagicMock()
        filter_mock = MagicMock()
        options_mock = MagicMock()

        db_session.query.return_value = query_mock
        query_mock.filter.return_value = filter_mock
        filter_mock.options.return_value = options_mock

        options_mock.count.return_value = 1
        options_mock.all.return_value = [fake_dataset]

        with patch.dict(
            os.environ,
            {"PROJECT_ID": "test-project", "DATASET_PROCESSING_TOPIC_NAME": "topic"},
            clear=False,
        ), patch(
            "tasks.dataset_files.rebuild_missing_dataset_files.get_datasets_with_missing_files_query"
        ) as get_query_mock, patch(
            "tasks.dataset_files.rebuild_missing_dataset_files.publish_messages"
        ) as mock_publish:
            from tasks.dataset_files.rebuild_missing_dataset_files import (
                rebuild_missing_dataset_files,
                Gtfsdataset,
            )

            result = rebuild_missing_dataset_files(
                db_session=db_session,
                dry_run=False,
                after_date=None,
                latest_only=True,  # ignored when dataset_id is provided
                dataset_id=dataset_stable_id,
            )

            # Asserts
            get_query_mock.assert_not_called()  # bypasses generic query when dataset_id is set
            db_session.query.assert_called_once_with(Gtfsdataset)
            query_mock.filter.assert_called_once()  # filtered by stable_id
            options_mock.count.assert_called_once()
            options_mock.all.assert_called_once()

            self.assertEqual(result["total_processed"], 1)
            mock_publish.assert_called_once()

            messages_arg, project_id_arg, _topic_arg = mock_publish.call_args[0]
            self.assertEqual(project_id_arg, "test-project")
            self.assertEqual(len(messages_arg), 1)
            self.assertEqual(messages_arg[0]["dataset_stable_id"], dataset_stable_id)
