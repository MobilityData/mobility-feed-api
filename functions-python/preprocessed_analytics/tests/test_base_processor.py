import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
import pandas as pd

from preprocessed_analytics.src.processors.base_analytics_processor import (
    BaseAnalyticsProcessor,
)


class TestBaseAnalyticsProcessor(unittest.TestCase):
    @patch(
        "preprocessed_analytics.src.processors.base_analytics_processor.start_db_session"
    )
    @patch(
        "preprocessed_analytics.src.processors.base_analytics_processor.storage.Client"
    )
    def setUp(self, mock_storage_client, mock_start_db_session):
        self.mock_session = MagicMock()
        mock_start_db_session.return_value = self.mock_session

        self.mock_storage_client = mock_storage_client
        self.mock_bucket = MagicMock()
        self.mock_storage_client().bucket.return_value = self.mock_bucket

        self.run_date = datetime(2024, 8, 22)
        self.processor = BaseAnalyticsProcessor(self.run_date)

    def test_append_new_data_if_not_exists(self):
        old_data = [
            {"feed_id": "feed1", "computed_on": ["2024-08-20"]},
            {"feed_id": "feed2", "computed_on": ["2024-08-21"]},
        ]
        new_data = [
            {"feed_id": "feed2", "computed_on": ["2024-08-22"]},
            {"feed_id": "feed3", "computed_on": ["2024-08-22"]},
        ]
        updated_data = self.processor.append_new_data_if_not_exists(
            old_data, new_data, ["feed_id"], ["computed_on"]
        )

        expected_data = [
            {"feed_id": "feed1", "computed_on": ["2024-08-20"]},
            {"feed_id": "feed2", "computed_on": ["2024-08-21", "2024-08-22"]},
            {"feed_id": "feed3", "computed_on": ["2024-08-22"]},
        ]

        self.assertEqual(updated_data, expected_data)

    @patch(
        "preprocessed_analytics.src.processors.base_analytics_processor.pd.read_json"
    )
    def test_load_json_exists(self, mock_read_json):
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_blob.download_as_text.return_value = '{"key": "value"}'
        mock_read_json.return_value = pd.DataFrame([{"key": "value"}])

        data, blob = self.processor._load_json("test.json")

        mock_read_json.assert_called_once()
        self.assertEqual(data, [{"key": "value"}])

    def test_load_json_not_exists(self):
        mock_blob = MagicMock()
        mock_blob.exists.return_value = False
        self.mock_bucket.blob.return_value = mock_blob

        data, blob = self.processor._load_json("test.json")

        mock_blob.exists.assert_called_once()
        self.assertEqual(data, [])
        self.assertEqual(blob, mock_blob)

    def test_save_blob(self):
        mock_blob = MagicMock()
        data = [{"key": "value"}]

        self.processor._save_blob(mock_blob, data)

        mock_blob.upload_from_string.assert_called_once_with(
            pd.DataFrame(data).to_json(orient="records", date_format="iso"),
            content_type="application/json",
        )
        mock_blob.make_public.assert_called_once()

    def test_save_json(self):
        mock_blob = MagicMock()
        self.mock_bucket.blob.return_value = mock_blob
        data = [{"key": "value"}]

        self.processor._save_json("test.json", data)

        mock_blob.upload_from_string.assert_called_once_with(
            pd.DataFrame(data).to_json(orient="records", date_format="iso"),
            content_type="application/json",
        )
        mock_blob.make_public.assert_called_once()

    @patch(
        "preprocessed_analytics.src.processors.base_analytics_processor.BaseAnalyticsProcessor._load_json"
    )
    @patch(
        "preprocessed_analytics.src.processors.base_analytics_processor.BaseAnalyticsProcessor._save_blob"
    )
    def test_save_metrics(self, mock_save_blob, mock_load_json):
        mock_load_json.return_value = ([], MagicMock())
        metrics_file_data = {
            "metrics.json": {
                "new_data": [{"key": "value"}],
                "keys": ["key"],
                "list_to_append": ["computed_on"],
            }
        }

        self.processor.save_metrics(metrics_file_data)

        mock_load_json.assert_called_once_with("metrics.json")
        mock_save_blob.assert_called_once()

    @patch(
        "preprocessed_analytics.src.processors.base_analytics_processor.BaseAnalyticsProcessor._save_json"
    )
    def test_save_analytics(self, _):
        self.processor.data = [{"key": "value"}]
        with self.assertRaises(NotImplementedError):
            self.processor.save_analytics()

    @patch(
        "preprocessed_analytics.src.processors.base_analytics_processor.BaseAnalyticsProcessor._save_json"
    )
    @patch(
        "preprocessed_analytics.src.processors.base_analytics_processor.storage.Blob"
    )
    def test_update_analytics_files(self, mock_blob, mock_save_json):
        mock_blob = MagicMock()
        self.mock_bucket.list_blobs.return_value = [mock_blob]
        mock_blob.name = "analytics_2024_08.json"
        mock_blob.time_created = datetime(2024, 8, 22)

        self.processor.update_analytics_files()

        mock_save_json.assert_called_once()

    @patch(
        "preprocessed_analytics.src.processors.base_analytics_processor.BaseAnalyticsProcessor.get_latest_data"
    )
    @patch(
        "preprocessed_analytics.src.processors.base_analytics_processor.BaseAnalyticsProcessor.process_feed_data"
    )
    @patch(
        "preprocessed_analytics.src.processors.base_analytics_processor.BaseAnalyticsProcessor.save_analytics"
    )
    @patch(
        "preprocessed_analytics.src.processors.base_analytics_processor.BaseAnalyticsProcessor.update_analytics_files"
    )
    def test_run(
        self,
        mock_update_analytics_files,
        mock_save_analytics,
        mock_process_feed_data,
        mock_get_latest_data,
    ):
        # Mock query and its all() method
        mock_query = MagicMock()
        mock_get_latest_data.return_value = mock_query
        mock_query.all.return_value = [("feed1", "dataset1"), ("feed2", "dataset2")]

        # Run the processor's run method
        self.processor.run()

        # Assert that get_latest_data was called
        mock_get_latest_data.assert_called_once()

        # Assert that process_feed_data was called twice (once for each feed-dataset pair)
        self.assertEqual(mock_process_feed_data.call_count, 2)
        mock_process_feed_data.assert_any_call("feed1", "dataset1")
        mock_process_feed_data.assert_any_call("feed2", "dataset2")

        # Assert that save_analytics was called once
        mock_save_analytics.assert_called_once()

        # Assert that update_analytics_files was called once
        mock_update_analytics_files.assert_called_once()
