import unittest
from unittest.mock import patch

from utils.logger import HttpRequest, LogRecord, AsyncStreamHandler, GCPLogHandler, Logger


class TestLogger(unittest.TestCase):
    def test_http_request(self):
        http_request = HttpRequest(
            "GET", "http://localhost", 200, 100, "user-agent", "127.0.0.1", "127.0.0.1", 0.1, "http"
        )
        self.assertEqual(http_request.requestMethod, "GET")

    def test_log_record(self):
        http_request = {"requestMethod": "GET"}
        log_record = LogRecord("user_id", http_request, "trace", "spanId", True, "textPayload", {"json": "payload"})
        self.assertEqual(log_record.user_id, "user_id")

    @patch("asyncio.get_event_loop")
    def test_async_stream_handler(self, mock_get_event_loop):
        handler = AsyncStreamHandler()
        self.assertEqual(handler.loop, mock_get_event_loop.return_value)

    @patch("logging.getLogger")
    @patch("logging.StreamHandler")
    def test_gcp_log_handler(self, mock_stream_handler, mock_get_logger):
        handler = GCPLogHandler()
        self.assertEqual(handler.logger, mock_get_logger.return_value)

    @patch("logging.getLogger")
    @patch("logging.StreamHandler")
    def test_logger(self, mock_stream_handler, mock_get_logger):
        logger = Logger("test")
        self.assertEqual(logger.logger, mock_get_logger.return_value)
