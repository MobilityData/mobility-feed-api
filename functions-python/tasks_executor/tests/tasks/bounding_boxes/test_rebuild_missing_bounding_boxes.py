import unittest
from datetime import datetime

from tasks.missing_bounding_boxes.rebuild_missing_bounding_boxes import get_parameters


class TestTasksExecutor(unittest.TestCase):
    def test_get_parameters(self):
        """
        Test the get_parameters function to ensure it correctly extracts parameters from the payload.
        """
        payload = {
            "dry_run": True,
        }

        dry_run, after_date = get_parameters(payload)
        self.assertTrue(dry_run)
        self.assertIsNone(after_date)

    def test_get_parameters_with_valid_after_date(self):
        """
        Test get_parameters returns a valid ISO date string for after_date.
        """
        payload = {
            "dry_run": False,
            "after_date": "2024-06-01",
        }

        dry_run, after_date = get_parameters(payload)
        self.assertFalse(dry_run)
        # Check that after_date is a valid ISO date string
        try:
            datetime.fromisoformat(after_date)
        except ValueError:
            self.fail(f"after_date '{after_date}' is not a valid ISO date string")
