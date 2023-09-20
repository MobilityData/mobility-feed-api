# coding: utf-8

from fastapi.testclient import TestClient


def test_metadata_get(client: TestClient):
    """Test case for metadata_get"""

    headers = {
        "ApiKeyAuth": "special-key",
    }
    response = client.request(
        "GET",
        "/v1/metadata",
        headers=headers,
    )

    assert response.status_code == 200
