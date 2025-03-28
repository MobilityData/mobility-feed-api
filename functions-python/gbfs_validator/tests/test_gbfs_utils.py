import unittest
from unittest.mock import patch, MagicMock

from gbfs_utils import (
    fetch_gbfs_data,
)


class TestGbfsUtils(unittest.TestCase):
    def setUp(self):
        self.stable_id = "test_stable_id"

    @patch("requests.get")
    def test_fetch_gbfs_files(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"key": "value"}
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = fetch_gbfs_data("http://example.com")
        self.assertEqual(result, {"key": "value"})
        mock_get.assert_called_once_with("http://example.com")
