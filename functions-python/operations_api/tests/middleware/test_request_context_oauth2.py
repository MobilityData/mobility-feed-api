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
from fastapi import HTTPException
from unittest.mock import patch
from starlette.datastructures import Headers
from middleware.request_context_oauth2 import RequestContext


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


@patch("middleware.request_context_oauth2.get_tokeninfo_response")
def test_request_context_initialization(
    mock_get_tokeninfo_response, scope, monkeypatch
):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("LOCAL_ENV", "true")

    mock_get_tokeninfo_response.return_value.status_code = 200
    mock_get_tokeninfo_response.return_value.json.return_value = {
        "email": "test-email@example.com",
        "audience": "test-client-id",
        "email_verified": True,
        "expires_in": 3600,
    }

    mocked_scope = scope("test_token_test_request_context_initialization")
    request_context = RequestContext(mocked_scope)

    assert request_context.host == "example.com"
    assert request_context.protocol == "https"
    assert request_context.client_host == "192.168.1.1"
    assert request_context.server_ip == "127.0.0.1"
    assert request_context.client_user_agent == "test-agent"
    assert request_context.iap_jwt_assertion == "test-assertion"
    assert request_context.trace_id == "trace-id"
    assert request_context.span_id == "span-id"
    assert request_context.trace_sampled is True
    assert (
        request_context.user_email == "test-email@example.com"
    )  # Mock the email extraction


def test_request_context_missing_authorization(scope, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("LOCAL_ENV", "False")

    mocked_scope = scope("test_token_test_request_context_missing_authorization")
    headers = Headers(scope=mocked_scope)
    headers._list = [(k, v) for k, v in headers._list if k != b"authorization"]
    mocked_scope["headers"] = headers.raw

    with pytest.raises(HTTPException) as exc_info:
        RequestContext(mocked_scope)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Authorization header not found"


@patch("middleware.request_context_oauth2.get_tokeninfo_response")
def test_request_context_invalid_token(mock_get_tokeninfo_response, scope, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("LOCAL_ENV", "False")

    mock_get_tokeninfo_response.return_value.status_code = 400

    with pytest.raises(HTTPException) as exc_info:
        RequestContext(scope("test_token_test_request_context_invalid_token"))
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid access token"
