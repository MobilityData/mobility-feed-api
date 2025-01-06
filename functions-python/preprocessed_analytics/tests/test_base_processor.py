import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
import pandas as pd

from processors.base_analytics_processor import (
    BaseAnalyticsProcessor,
)


class TestBaseAnalyticsProcessor(unittest.TestCase):
    @patch("processors.base_analytics_processor.start_db_session")
    @patch("processors.base_analytics_processor.storage.Client")
    def setUp(self, mock_storage_client, mock_start_db_session):
        self.mock_session = MagicMock()
        mock_start_db_session.return_value = self.mock_session

        self.mock_storage_client = mock_storage_client
        self.mock_bucket = MagicMock()
        self.mock_storage_client().bucket.return_value = self.mock_bucket

        self.run_date = datetime(2024, 8, 22)
        self.processor = BaseAnalyticsProcessor(self.run_date)

    @patch("processors.base_analytics_processor.pd.read_json")
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

    @patch("processors.base_analytics_processor.BaseAnalyticsProcessor._save_json")
    def test_save_analytics(self, _):
        self.processor.data = [{"key": "value"}]
        with self.assertRaises(NotImplementedError):
            self.processor.save_analytics()

    @patch("processors.base_analytics_processor.BaseAnalyticsProcessor._save_json")
    @patch("processors.base_analytics_processor.storage.Blob")
    def test_update_analytics_files(self, mock_blob, mock_save_json):
        mock_blob = MagicMock()
        self.mock_bucket.list_blobs.return_value = [mock_blob]
        mock_blob.name = "analytics_2024_08.json"
        mock_blob.time_created = datetime(2024, 8, 22)

        self.processor.update_analytics_files()

        mock_save_json.assert_called_once()

    @patch("processors.base_analytics_processor.BaseAnalyticsProcessor.get_latest_data")
    @patch(
        "processors.base_analytics_processor.BaseAnalyticsProcessor.process_feed_data"
    )
    @patch("processors.base_analytics_processor.BaseAnalyticsProcessor.save_analytics")
    @patch(
        "processors.base_analytics_processor.BaseAnalyticsProcessor.update_analytics_files"
    )
    @patch("processors.base_analytics_processor.BaseAnalyticsProcessor.save_summary")
    def test_run(
        self,
        mock_save_summary,
        mock_update_analytics_files,
        mock_save_analytics,
        mock_process_feed_data,
        mock_get_latest_data,
    ):
        # Create mock feed objects with a stable_id attribute
        mock_feed1 = MagicMock()
        mock_feed1.stable_id = "stable_id_1"

        mock_feed2 = MagicMock()
        mock_feed2.stable_id = "stable_id_2"

        # Mock the dataset_or_snapshot and translation data
        mock_dataset1 = MagicMock()
        mock_dataset2 = MagicMock()

        translation_data1 = "translation1"
        translation_data2 = "translation2"

        # Mock query and its all() method
        mock_query = MagicMock()
        mock_get_latest_data.return_value = mock_query
        mock_query.all.return_value = [
            (mock_feed1, mock_dataset1, translation_data1),
            (mock_feed2, mock_dataset2, translation_data2),
        ]

        # Run the processor's run method
        self.processor.run()

        # Assert that get_latest_data was called
        mock_get_latest_data.assert_called_once()

        # Assert that process_feed_data was called twice (once for each feed-dataset pair)
        self.assertEqual(mock_process_feed_data.call_count, 2)

        mock_save_analytics.assert_called_once()
        mock_update_analytics_files.assert_called_once()
        mock_save_summary.assert_called_once()
