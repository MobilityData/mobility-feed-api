import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
from preprocessed_analytics.src.processors.gtfs_analytics_processor import (
    GTFSAnalyticsProcessor,
)


class TestGTFSAnalyticsProcessor(unittest.TestCase):
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
        self.processor = GTFSAnalyticsProcessor(self.run_date)

    @patch(
        "preprocessed_analytics.src.processors.gtfs_analytics_processor.GTFSAnalyticsProcessor.get_latest_data"
    )
    @patch(
        "preprocessed_analytics.src.processors.gtfs_analytics_processor.GTFSAnalyticsProcessor.process_feed_data"
    )
    @patch(
        "preprocessed_analytics.src.processors.gtfs_analytics_processor.GTFSAnalyticsProcessor.save"
    )
    @patch(
        "preprocessed_analytics.src.processors.gtfs_analytics_processor.GTFSAnalyticsProcessor"
        ".update_analytics_files"
    )
    def test_run(
        self,
        mock_update_analytics_files,
        mock_save,
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

        # Assert that save was called once
        mock_save.assert_called_once()

        # Assert that update_analytics_files was called once
        mock_update_analytics_files.assert_called_once()

    def test_process_feed_data(self):
        # Create mock feed and dataset
        mock_feed = MagicMock()
        mock_feed.stable_id = "feed1"
        mock_feed.locations = [
            MagicMock(
                country_code="US",
                country="United States",
                municipality="City",
                subdivision_name="State",
            )
        ]
        mock_feed.provider = "Provider1"
        mock_feed.created_at = datetime(2024, 8, 1)

        mock_dataset = MagicMock()
        mock_dataset.stable_id = "dataset1"
        mock_dataset.downloaded_at = datetime(2024, 8, 2)
        mock_dataset.locations = mock_feed.locations
        mock_dataset.validation_reports = [
            MagicMock(validated_at=datetime(2024, 8, 20))
        ]
        mock_dataset.validation_reports[0].notices = [
            MagicMock(notice_code="error1", severity="ERROR"),
            MagicMock(notice_code="warning1", severity="WARNING"),
            MagicMock(notice_code="info1", severity="INFO"),
        ]
        mock_dataset.validation_reports[0].features = [MagicMock(name="feature1")]

        # Run process_feed_data
        self.processor.process_feed_data(mock_feed, mock_dataset, {})

        # Assert the data was appended correctly
        self.assertEqual(len(self.processor.data), 1)
        self.assertEqual(len(self.processor.feed_metrics_data), 1)
        self.assertEqual(len(self.processor.features_metrics_data), 1)
        self.assertEqual(len(self.processor.notices_metrics_data), 3)

    @patch(
        "preprocessed_analytics.src.processors.gtfs_analytics_processor.GTFSAnalyticsProcessor._save_blob"
    )
    @patch(
        "preprocessed_analytics.src.processors.gtfs_analytics_processor.GTFSAnalyticsProcessor._load_json"
    )
    def test_save(self, mock_load_json, mock_save_blob):
        # Mock the return values of _load_json
        mock_load_json.return_value = ([], MagicMock())

        # Call save
        self.processor.save()

        # Assert that _load_json was called for each metrics file
        self.assertEqual(mock_load_json.call_count, 3)

        # Assert that _save_blob was called three times
        self.assertEqual(mock_save_blob.call_count, 3)

    def test_process_features(self):
        # Create mock features
        mock_features = [MagicMock(name="feature1"), MagicMock(name="feature2")]

        # Process features
        self.processor._process_features(mock_features)

        # Assert features_metrics_data was updated correctly
        self.assertEqual(len(self.processor.features_metrics_data), 2)

    def test_process_notices(self):
        # Create mock notices
        mock_notices = [
            MagicMock(notice_code="error1", severity="ERROR"),
            MagicMock(notice_code="warning1", severity="WARNING"),
            MagicMock(notice_code="info1", severity="INFO"),
        ]

        # Process notices
        self.processor._process_notices(mock_notices)

        # Assert notices_metrics_data was updated correctly
        self.assertEqual(len(self.processor.notices_metrics_data), 3)
        self.assertEqual(self.processor.notices_metrics_data[0]["notice"], "error1")
        self.assertEqual(self.processor.notices_metrics_data[1]["notice"], "warning1")
        self.assertEqual(self.processor.notices_metrics_data[2]["notice"], "info1")
