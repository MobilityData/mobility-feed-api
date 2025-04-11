import unittest
from unittest.mock import patch, MagicMock

import faker
from requests import RequestException

from gbfs_utils import fetch_gbfs_data, save_trace_with_error, GBFSEndpoint


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

    def test_save_trace_with_error(self):
        trace = MagicMock()
        trace_service = MagicMock()
        error = faker.Faker().sentence()
        save_trace_with_error(trace, error, trace_service)
        trace_service.save.assert_called_once_with(trace)
        self.assertEqual(trace.error_message, error)

    @patch("requests.get")
    def test_get_request_metadata(self, mock_get):
        mock_get.return_value = MagicMock(
            elapsed=MagicMock(total_seconds=MagicMock(return_value=1)),
            status_code=200,
            content="content",
        )
        result = GBFSEndpoint.get_request_metadata("http://example.com")
        self.assertEqual(
            result, {"latency": 1000, "status_code": 200, "response_size_bytes": 7}
        )

    @patch("requests.get")
    def test_get_request_metadata_exception(self, mock_get):
        mock_get.side_effect = RequestException("Error")
        result = GBFSEndpoint.get_request_metadata("http://example.com")
        self.assertEqual(
            result, {"latency": None, "status_code": 400, "response_size_bytes": None}
        )
