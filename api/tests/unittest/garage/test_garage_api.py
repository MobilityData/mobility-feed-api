from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from garage.impl.garage_access import GARAGE_FEATURE_FLAG_ID
from main import app
from shared.common.error_handling import endpoint_not_implemented, garage_not_permitted

USER_HEADERS = {"x-goog-authenticated-user-id": "accounts.google.com:user-1"}
UPLOAD_BODY = {"name": "my feed"}

# Every Garage endpoint, as (method, path, json body).
ENDPOINTS = [
    ("GET", "/v1/garage/datasets", None),
    ("POST", "/v1/garage/datasets:upload", UPLOAD_BODY),
    ("GET", "/v1/garage/datasets/ds-1", None),
    ("DELETE", "/v1/garage/datasets/ds-1", None),
]

client = TestClient(app)


@pytest.fixture
def flag_enabled():
    """Patch the users database and the flag lookup; yields the flag lookup mock."""
    with patch("garage.impl.garage_access.UsersDatabase") as users_database, patch(
        "garage.impl.garage_access.feature_flag_enabled"
    ) as feature_flag_enabled:
        users_database.return_value.start_db_session.return_value.__enter__.return_value = MagicMock()
        yield feature_flag_enabled


@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_missing_identity_is_401(method, path, body, flag_enabled):
    response = client.request(method, path, json=body)
    assert response.status_code == 401
    flag_enabled.assert_not_called()


@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_without_flag_is_403(method, path, body, flag_enabled):
    flag_enabled.return_value = False
    response = client.request(method, path, json=body, headers=USER_HEADERS)
    assert response.status_code == 403
    assert response.json() == {"detail": garage_not_permitted}
    assert flag_enabled.call_args.args[1:] == ("user-1", GARAGE_FEATURE_FLAG_ID)


@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_with_flag_is_501(method, path, body, flag_enabled):
    flag_enabled.return_value = True
    response = client.request(method, path, json=body, headers=USER_HEADERS)
    assert response.status_code == 501
    assert response.json() == {"detail": endpoint_not_implemented}


def test_invalid_body_is_422(flag_enabled):
    flag_enabled.return_value = True
    response = client.post("/v1/garage/datasets:upload", json={}, headers=USER_HEADERS)
    assert response.status_code == 422


def test_invalid_body_without_flag_is_403(flag_enabled):
    """Access is checked before the body is validated, so the schema is not revealed to other users."""
    flag_enabled.return_value = False
    response = client.post("/v1/garage/datasets:upload", json={}, headers=USER_HEADERS)
    assert response.status_code == 403


def test_datasets_collection_does_not_accept_post(flag_enabled):
    """Datasets are created through `datasets:upload` only."""
    flag_enabled.return_value = True
    response = client.post("/v1/garage/datasets", json=UPLOAD_BODY, headers=USER_HEADERS)
    assert response.status_code == 405
