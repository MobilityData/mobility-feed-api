#
#   MobilityData 2023
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
import json
import os
import unittest
from unittest.mock import patch, Mock
from unittest import mock

from flask import Request

from main import (
    get_idp_response,
    IDP_TOKEN_URL,
    HEADERS,
    tokens_post,
    TokenPostResponseError,
)
from functions_framework import create_app

fake_token = (
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJGYWtlIFRva2VuIiwiaWF0IjoxNjcyNTMxMjAwLCJleHAiOjE2NzI2MT"
    "c2MDAsImF1ZCI6Ind3dy5leGFtcGxlLmNvbSIsInN1YiI6Impyb2NrZXRAZXhhbXBsZS5jb20iLCJHaXZlbk5hbWUiOiJKb2hubnkif"
    "Q.X2qWwdBAqlCh76tVemxFvR-gdZOA6m_naklq5HgtcTA"
)


def get_source_path(file: str):
    path = os.path.abspath(__file__[: __file__.rindex("/")])
    source = f"{path}/../src/{file}"
    return source


@mock.patch.dict(os.environ, {"GCP_IDP_API_KEY": "gcp_idp_api_test_key"})
@patch("requests.post")
def test_get_idp_response__valid_request(mock_post):
    # Mock the response from IDP requests.post
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "mock_access_token"}
    mock_post.return_value = mock_response
    refresh_token = "mock_refresh_token"

    idp_response = get_idp_response(refresh_token)

    assert idp_response.status_code == 200
    assert idp_response.json() == {"access_token": "mock_access_token"}

    mock_post.assert_called_once_with(
        f"{IDP_TOKEN_URL}?key=gcp_idp_api_test_key",
        headers=HEADERS,
        data='{"grant_type": "refresh_token", "refresh_token": "mock_refresh_token", "audiences": "feed_api"}',
    )


def test_tokens_post_get_method():
    """
    Test that POST method is required for POST /tokens
    """
    response = tokens_post(Request({"REQUEST_METHOD": "GET"}))
    assert response.status_code == 405
    assert (
        response.data
        == json.dumps(
            TokenPostResponseError("Invalid request method.").__dict__
        ).encode()
    )


def test_tokens_post_invalid_media_type():
    """
    Test that a missing refresh_token returns a 400 error
    """
    response = tokens_post(Request({"REQUEST_METHOD": "POST"}))
    assert response.status_code == 415
    assert (
        response.data
        == json.dumps(
            TokenPostResponseError("Unsupported Media Type.").__dict__
        ).encode()
    )


def test_tokens_post_no_json_data():
    """
    Test that a missing refresh_token returns a 400 error
    """
    response = tokens_post(
        Request({"REQUEST_METHOD": "POST", "CONTENT_TYPE": "application/json"})
    )
    assert response.status_code == 400
    assert (
        response.data
        == json.dumps(TokenPostResponseError("Bad Request.").__dict__).encode()
    )


def test_tokens_post_missing_refresh_token():
    """
    Test that a missing refresh_token returns a 400 error
    """
    request_json = {
        "key1": "value1",
    }

    source = get_source_path("main.py")
    target = "tokens_post"
    http_client = create_app(target, source, "http").test_client()

    response = http_client.post(
        "/tokens", data=json.dumps(request_json), content_type="application/json"
    )
    assert response.status_code == 400
    assert (
        response.data
        == json.dumps(
            TokenPostResponseError("Missing refresh_token.").__dict__
        ).encode()
    )


@mock.patch.dict(os.environ, {"GCP_IDP_API_KEY": "gcp_idp_api_test_key"})
@patch("requests.post")
def test_tokens_valid_request(mock_post):
    """
    Test token_post with a valid request
    """
    # Mock the response from IDP requests.post
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": fake_token,
        "token_type": "Bearer",
    }
    mock_post.return_value = mock_response
    request_json = {
        "refresh_token": fake_token,
    }

    source = get_source_path("main.py")
    target = "tokens_post"
    http_client = create_app(target, source, "http").test_client()

    response = http_client.post(
        "/tokens", data=json.dumps(request_json), content_type="application/json"
    )
    assert response.status_code == 200
    assert (
        response.data
        == json.dumps(
            {
                "access_token": fake_token,
                "expiration_datetime_utc": "2023-01-02T00:00:00Z",
                "token_type": "Bearer",
            }
        ).encode()
    )


if __name__ == "__main__":
    unittest.main()
