#
#   MobilityData 2026
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
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from flask import Flask

import main
from garage.access_middleware import USER_DATASETS_FEATURE_FLAG_ID, garage_enabled
from main import app

USER_HEADERS = {
    "x-goog-authenticated-user-id": "accounts.google.com:user-1",
    "Authorization": "Bearer token",
}
CREATE_BODY = {"name": "my feed", "source": "upload", "size_bytes": 10}

# Every Garage endpoint, as (method, path, json body).
ENDPOINTS = [
    ("GET", "/v1/garage/datasets", None),
    ("POST", "/v1/garage/datasets", CREATE_BODY),
    ("GET", "/v1/garage/datasets/ds-1", None),
    ("DELETE", "/v1/garage/datasets/ds-1", None),
]

client = TestClient(app)


def test_only_garage_routes_registered():
    """The function serves the Garage endpoints and nothing else."""
    api_paths = {
        route.path
        for route in app.routes
        if not route.path.startswith(("/docs", "/redoc", "/openapi"))
    }
    assert api_paths == {
        "/v1/garage/datasets",
        "/v1/garage/datasets/{id}",
    }


@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_missing_token_is_401(method, path, body):
    with patch("garage.access_middleware.garage_enabled") as enabled:
        response = client.request(method, path, json=body)
    assert response.status_code == 401
    assert "details" in response.json()
    enabled.assert_not_called()


@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_without_flag_is_403(method, path, body):
    with patch(
        "garage.access_middleware.garage_enabled", return_value=False
    ) as enabled:
        response = client.request(method, path, json=body, headers=USER_HEADERS)
    assert response.status_code == 403
    assert "details" in response.json()
    enabled.assert_called_once_with("user-1")


@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_with_flag_is_501(method, path, body):
    with patch("garage.access_middleware.garage_enabled", return_value=True):
        response = client.request(method, path, json=body, headers=USER_HEADERS)
    assert response.status_code == 501
    assert response.json() == {"details": "This endpoint is not implemented yet."}


def test_invalid_body_is_400():
    with patch("garage.access_middleware.garage_enabled", return_value=True):
        response = client.post(
            "/v1/garage/datasets", json={"name": "x"}, headers=USER_HEADERS
        )
    assert response.status_code == 400
    assert "details" in response.json()


def test_cors_preflight_skips_access_check():
    with patch("garage.access_middleware.garage_enabled") as enabled:
        response = client.options(
            "/v1/garage/datasets",
            headers={
                "Origin": "https://mobilitydatabase.org",
                "Access-Control-Request-Method": "POST",
            },
        )
    assert response.status_code == 200
    enabled.assert_not_called()


@patch("garage.access_middleware.feature_flag_enabled", return_value=True)
def test_garage_enabled_reads_the_flag(feature_flag_enabled):
    session = MagicMock()
    assert garage_enabled("user-1", db_session=session) is True
    feature_flag_enabled.assert_called_once_with(
        session, "user-1", USER_DATASETS_FEATURE_FLAG_ID
    )


def test_function_entry_point_bridges_to_the_app():
    flask_app = Flask(__name__)
    with flask_app.test_request_context(
        "/v1/garage/datasets", method="GET", headers=USER_HEADERS
    ) as ctx, patch("garage.access_middleware.garage_enabled", return_value=True):
        response = main.main(ctx.request)
    assert response.status_code == 501


def test_function_entry_point_returns_500_on_error():
    flask_app = Flask(__name__)
    with flask_app.test_request_context("/v1/garage/datasets") as ctx, patch.object(
        main, "app", side_effect=RuntimeError("boom")
    ):
        response = main.main(ctx.request)
    assert response.status_code == 500
