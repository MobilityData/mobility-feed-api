import logging
import unittest
from unittest.mock import patch, MagicMock

import pytest

from middleware.request_context import RequestContext
from utils.logger import GCPLogHandler


class TestGCPLogHandler(unittest.TestCase):
    @patch("utils.logger.get_config")
    def test_get_trace(self, mock_get_config):
        # Test the get_trace method
        mock_get_config.return_value = "PROJECT_ID"
        handler = GCPLogHandler()
        request_context = {"trace_id": "TRACE_ID"}
        trace = handler.get_trace(request_context)
        self.assertEqual(trace, "projects/PROJECT_ID/traces/TRACE_ID")

    @patch("utils.logger.get_config")
    def test_get_trace_no_trace(self, mock_get_config):
        # Test the get_trace method
        mock_get_config.return_value = "PROJECT_ID"
        handler = GCPLogHandler()
        self.assertEqual(handler.get_trace({}), "")

    def test_get_http_request(self):
        # Test the get_http_request method
        handler = GCPLogHandler()
        record = MagicMock()
        record.context = {"http_request": "HTTP_REQUEST"}
        http_request = handler.get_http_request(record)
        self.assertEqual(http_request, "HTTP_REQUEST")


async def assert_async_emit(mock_get_logger, mock_json_dumps, mock_get_request_context, message):
    handler = GCPLogHandler()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0, msg="MESSAGE", args=(), exc_info=None
    )
    record.msg = message
    request_context = RequestContext(
        scope={
            "headers": [
                (b"x-cloud-trace-context", b"TRACE_ID/SPAN_ID;o=1"),
            ]
        }
    )
    request_context.span_id = "SPAN_ID"
    request_context.trace_sampled = True
    request_context.user_id = "USER_ID"
    mock_get_request_context.return_value = request_context.__dict__
    await handler.async_emit(record)
    mock_get_logger.return_value.info.assert_called_once_with(mock_json_dumps.return_value)


class TestAsyncGCPLogHandler(unittest.IsolatedAsyncioTestCase):
    @patch("utils.logger.get_request_context")
    @patch("json.dumps")
    @patch("logging.getLogger")
    @pytest.mark.asyncio
    async def test_async_emit_json(self, mock_get_logger, mock_json_dumps, mock_get_request_context):
        # Test the assert_async_emit method with json payload
        # this is needed as @pytest.mark.parametrize is not supported with patch in IsolatedAsyncioTestCase
        await assert_async_emit(mock_get_logger, mock_json_dumps, mock_get_request_context, {"json": "payload"})

    @patch("utils.logger.get_request_context")
    @patch("json.dumps")
    @patch("logging.getLogger")
    @pytest.mark.asyncio
    async def test_async_emit_text(self, mock_get_logger, mock_json_dumps, mock_get_request_context):
        # Test the assert_async_emit method with text payload
        # this is needed as @pytest.mark.parametrize is not supported with patch in IsolatedAsyncioTestCase
        await assert_async_emit(mock_get_logger, mock_json_dumps, mock_get_request_context, "text payload")

    @patch("utils.logger.get_request_context")
    @patch("json.dumps")
    @patch("logging.getLogger")
    @pytest.mark.asyncio
    async def test_async_emit_no_message(self, mock_get_logger, mock_json_dumps, mock_get_request_context):
        # Test the assert_async_emit method with text payload
        # this is needed as @pytest.mark.parametrize is not supported with patch in IsolatedAsyncioTestCase
        await assert_async_emit(mock_get_logger, mock_json_dumps, mock_get_request_context, None)
