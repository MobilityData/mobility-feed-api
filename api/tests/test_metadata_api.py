# coding: utf-8

from fastapi.testclient import TestClient

from .test_utils.token import authHeaders


def test_metadata_get(client: TestClient):
    """Test case for metadata_get"""

    response = client.request(
        "GET",
        "/v1/metadata",
        headers=authHeaders,
    )

    assert response.status_code == 200
