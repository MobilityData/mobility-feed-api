import unittest

from tasks.bounding_boxes.test_rebuild_missing_bounding_boxes import (
    get_parameters,
)


class TestTasksExecutor(unittest.TestCase):
    def test_get_parameters(self):
        """
        Test the get_parameters function to ensure it correctly extracts parameters from the payload.
        """
        payload = {
            "dry_run": True,
        }

        (
            dry_run,
            prod_env,
        ) = get_parameters(payload)

        self.assertTrue(dry_run)
        self.assertFalse(prod_env)
