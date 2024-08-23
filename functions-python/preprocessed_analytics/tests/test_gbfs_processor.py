import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
from preprocessed_analytics.src.processors.gbfs_analytics_processor import (
    GBFSAnalyticsProcessor,
)


class TestGBFSAnalyticsProcessor(unittest.TestCase):
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
        self.processor = GBFSAnalyticsProcessor(self.run_date)

    @patch(
        "preprocessed_analytics.src.processors.gbfs_analytics_processor.GBFSAnalyticsProcessor.get_latest_data"
    )
    @patch(
        "preprocessed_analytics.src.processors.gbfs_analytics_processor.GBFSAnalyticsProcessor.process_feed_data"
    )
    @patch(
        "preprocessed_analytics.src.processors.gbfs_analytics_processor.GBFSAnalyticsProcessor.save"
    )
    @patch(
        "preprocessed_analytics.src.processors.gbfs_analytics_processor."
        "GBFSAnalyticsProcessor.update_analytics_files"
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
        mock_query.all.return_value = [("feed1", "snapshot1"), ("feed2", "snapshot2")]

        # Run the processor's run method
        self.processor.run()

        # Assert that get_latest_data was called
        mock_get_latest_data.assert_called_once()

        # Assert that process_feed_data was called twice (once for each feed-snapshot pair)
        self.assertEqual(mock_process_feed_data.call_count, 2)
        mock_process_feed_data.assert_any_call("feed1", "snapshot1")
        mock_process_feed_data.assert_any_call("feed2", "snapshot2")

        # Assert that save was called once
        mock_save.assert_called_once()

        # Assert that update_analytics_files was called once
        mock_update_analytics_files.assert_called_once()

    def test_process_feed_data(self):
        # Create mock feed and snapshot
        mock_feed = MagicMock()
        mock_feed.stable_id = "feed1"
        mock_feed.gbfsversions = [MagicMock(version="v1"), MagicMock(version="v2")]
        mock_feed.locations = [
            MagicMock(
                country_code="US",
                country="United States",
                municipality="City",
                subdivision_name="State",
            )
        ]
        mock_feed.operator = "Operator1"
        mock_feed.created_at = datetime(2024, 8, 1)

        mock_snapshot = MagicMock()
        mock_snapshot.stable_id = "snapshot1"
        mock_snapshot.gbfsvalidationreports = [
            MagicMock(validated_at=datetime(2024, 8, 20))
        ]
        mock_snapshot.gbfsvalidationreports[0].gbfsnotices = [
            MagicMock(keyword="keyword1", gbfs_file="file1", schema_path="path1"),
            MagicMock(keyword="keyword2", gbfs_file="file2", schema_path="path2"),
        ]

        # Run process_feed_data
        self.processor.process_feed_data(mock_feed, mock_snapshot)

        # Assert the data was appended correctly
        self.assertEqual(len(self.processor.data), 1)
        self.assertEqual(len(self.processor.feed_metrics_data), 1)
        self.assertEqual(len(self.processor.versions_metrics_data), 2)
        self.assertEqual(len(self.processor.notices_metrics_data), 2)

    @patch(
        "preprocessed_analytics.src.processors.gbfs_analytics_processor.GBFSAnalyticsProcessor._save_blob"
    )
    @patch(
        "preprocessed_analytics.src.processors.gbfs_analytics_processor.GBFSAnalyticsProcessor._load_json"
    )
    def test_save(self, mock_load_json, mock_save_blob):
        # Mock the return values of _load_json
        mock_load_json.return_value = ([], MagicMock())

        # Call save
        self.processor.save()

        # Assert that _load_json was called for each metrics file
        self.assertEqual(mock_load_json.call_count, 3)

        # Assert that _save_json was called once
        self.assertEqual(mock_save_blob.call_count, 3)

    def test_process_versions(self):
        # Create a mock feed with versions
        mock_feed = MagicMock()
        mock_feed.gbfsversions = [MagicMock(version="v1"), MagicMock(version="v2")]

        # Process versions
        self.processor._process_versions(mock_feed)

        # Assert versions_metrics_data was updated correctly
        self.assertEqual(len(self.processor.versions_metrics_data), 2)
        self.assertEqual(self.processor.versions_metrics_data[0]["version"], "v1")
        self.assertEqual(self.processor.versions_metrics_data[1]["version"], "v2")

    def test_process_notices(self):
        # Create mock notices
        mock_notices = [
            MagicMock(keyword="keyword1", gbfs_file="file1", schema_path="path1"),
            MagicMock(keyword="keyword2", gbfs_file="file2", schema_path="path2"),
        ]

        # Process notices
        self.processor._process_notices(mock_notices)

        # Assert notices_metrics_data was updated correctly
        self.assertEqual(len(self.processor.notices_metrics_data), 2)
        self.assertEqual(self.processor.notices_metrics_data[0]["keyword"], "keyword1")
        self.assertEqual(self.processor.notices_metrics_data[1]["keyword"], "keyword2")
