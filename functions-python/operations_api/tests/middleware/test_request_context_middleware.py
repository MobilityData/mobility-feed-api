#
#   MobilityData 2024
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import pytest
from unittest.mock import patch, MagicMock
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Receive, Scope, Send

from operations_api.src.middleware.request_context_middleware import (
    RequestContextMiddleware,
)


@pytest.fixture
def scope():
    def _scope(token):
        return {
            "type": "http",
            "headers": [
                (b"host", b"example.com"),
                (b"x-forwarded-proto", b"https"),
                (b"x-forwarded-for", b"192.168.1.1"),
                (b"user-agent", b"test-agent"),
                (b"x-goog-iap-jwt-assertion", b"test-assertion"),
                (b"x-cloud-trace-context", b"trace-id/span-id;o=1"),
                (b"authorization", f"Bearer {token}".encode("utf-8")),
            ],
            "client": ("192.168.1.1", 12345),
            "server": ("127.0.0.1", 8000),
            "scheme": "https",
        }

    return _scope


@pytest.mark.asyncio
@patch("operations_api.src.middleware.request_context_middleware.RequestContext")
async def test_request_context_middleware(mock_request_context, scope, monkeypatch):
    token = "test-token"
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("LOCAL_ENV", "true")

    mock_request_context.return_value = MagicMock()

    async def mock_call_next(scope: Scope, receive: Receive, send: Send) -> None:
        response = Response("Test response")
        await response(scope, receive, send)

    middleware = RequestContextMiddleware(mock_call_next)
    request = Request(scope=scope(token))

    async def mock_send(message):
        pass

    import asyncio

    try:
        await asyncio.wait_for(
            middleware(request.scope, request.receive, mock_send), timeout=5.0
        )
    except asyncio.TimeoutError:
        pytest.fail("The test timed out")

    mock_request_context.assert_called_once_with(scope=request.scope)
