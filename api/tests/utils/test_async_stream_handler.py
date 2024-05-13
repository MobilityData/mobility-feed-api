import unittest
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from utils.logger import AsyncStreamHandler


class TestAsyncStreamHandler(unittest.IsolatedAsyncioTestCase):
    @pytest.mark.asyncio
    @patch("asyncio.get_event_loop")
    async def test_async_emit(self, mock_get_event_loop):
        mock_event_loop = AsyncMock()
        mock_get_event_loop.return_value = mock_event_loop

        handler = AsyncStreamHandler()
        record = MagicMock()
        await handler.async_emit(record)
        mock_event_loop.run_in_executor.assert_called()

    @pytest.mark.asyncio
    @patch("asyncio.get_event_loop")
    @patch.object(AsyncStreamHandler, "async_emit", new_callable=AsyncMock)
    async def test_emit(self, mock_async_emit, mock_get_event_loop):
        mock_event_loop = AsyncMock()
        mock_get_event_loop.return_value = mock_event_loop

        handler = AsyncStreamHandler()
        record = MagicMock()
        handler.emit(record)

        mock_async_emit.assert_called_once_with(record)
