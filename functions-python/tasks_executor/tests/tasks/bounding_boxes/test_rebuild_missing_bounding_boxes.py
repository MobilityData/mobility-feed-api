import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

from tasks.missing_bounding_boxes.rebuild_missing_bounding_boxes import (
    get_parameters,
    rebuild_missing_bounding_boxes,
)


class TestTasksExecutor(unittest.TestCase):
    def test_get_parameters(self):
        payload = {"dry_run": True}
        dry_run, after_date = get_parameters(payload)
        self.assertTrue(dry_run)
        self.assertIsNone(after_date)

    def test_get_parameters_with_valid_after_date(self):
        payload = {"dry_run": False, "after_date": "2024-06-01"}
        dry_run, after_date = get_parameters(payload)
        self.assertFalse(dry_run)
        self.assertEqual(after_date, "2024-06-01")
        # Check ISO format
        try:
            datetime.fromisoformat(after_date)
        except ValueError:
            self.fail(f"after_date '{after_date}' is not a valid ISO date string")

    def test_get_parameters_with_string_bool(self):
        payload = {"dry_run": "false", "after_date": None}
        dry_run, after_date = get_parameters(payload)
        self.assertFalse(dry_run)
        self.assertIsNone(after_date)

    def test_get_parameters_missing_keys(self):
        payload = {}
        dry_run, after_date = get_parameters(payload)
        self.assertTrue(dry_run)
        self.assertIsNone(after_date)

    @patch(
        "tasks.missing_bounding_boxes.rebuild_missing_bounding_boxes.get_feeds_with_missing_bounding_boxes_query"
    )
    def test_rebuild_missing_bounding_boxes_dry_run(self, mock_query):
        # Mock Gtfsdataset and Gtfsfeed objects
        mock_dataset1 = MagicMock()
        mock_dataset1.stable_id = "dataset1"
        mock_dataset1.hosted_url = "http://example.com/dataset1"
        mock_feed1 = MagicMock()
        mock_feed1.stable_id = "feed1"
        mock_feed1.gtfsdatasets = [mock_dataset1]

        mock_dataset2 = MagicMock()
        mock_dataset2.stable_id = "dataset2"
        mock_dataset2.hosted_url = "http://example.com/dataset2"
        mock_feed2 = MagicMock()
        mock_feed2.stable_id = "feed2"
        mock_feed2.gtfsdatasets = [mock_dataset2]

        mock_query.return_value.filter.return_value = mock_query.return_value
        mock_query.return_value.all.return_value = [mock_feed1, mock_feed2]

        result = rebuild_missing_bounding_boxes(
            dry_run=True, after_date=None, db_session=MagicMock()
        )
        self.assertIn("Dry run", result["message"])
        self.assertEqual(result["total_processed"], 2)

    @patch(
        "tasks.missing_bounding_boxes.rebuild_missing_bounding_boxes.publish_messages"
    )
    @patch(
        "tasks.missing_bounding_boxes.rebuild_missing_bounding_boxes.get_feeds_with_missing_bounding_boxes_query"
    )
    def test_rebuild_missing_bounding_boxes_publish(self, mock_query, mock_publish):
        # Mock Gtfsdataset and Gtfsfeed objects
        mock_dataset = MagicMock()
        mock_dataset.stable_id = "dataset1"
        mock_dataset.hosted_url = "http://example.com/dataset1"
        mock_feed = MagicMock()
        mock_feed.stable_id = "feed1"
        mock_feed.gtfsdatasets = [mock_dataset]

        mock_query.return_value.filter.return_value = mock_query.return_value
        mock_query.return_value.all.return_value = [mock_feed]
        mock_publish.return_value = None

        result = rebuild_missing_bounding_boxes(
            dry_run=False, after_date=None, db_session=MagicMock()
        )
        self.assertIn("Successfully published", result["message"])
        self.assertEqual(result["total_processed"], 1)

    @patch(
        "tasks.missing_bounding_boxes.rebuild_missing_bounding_boxes.get_feeds_with_missing_bounding_boxes_query"
    )
    def test_rebuild_missing_bounding_boxes_invalid_after_date(self, mock_query):
        mock_query.return_value.filter.return_value = mock_query.return_value
        mock_query.return_value.all.return_value = []
        # Should log a warning and not raise
        result = rebuild_missing_bounding_boxes(
            dry_run=True, after_date="not-a-date", db_session=MagicMock()
        )
        self.assertIn("Dry run", result["message"])
        self.assertEqual(result["total_processed"], 0)


if __name__ == "__main__":
    unittest.main()
