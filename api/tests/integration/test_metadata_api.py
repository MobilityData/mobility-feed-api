# coding: utf-8
import os

from fastapi.testclient import TestClient

from tests.test_utils.token import authHeaders


def test_metadata_get(client: TestClient):
    """Test case for metadata_get"""
    test_hash = "1234567890123456789012345678901234567890"
    test_version = "v1.2.3"
    version_info_path = os.path.join(os.path.dirname(__file__), "../../src/version_info")
    with open(version_info_path, "w") as file:
        file.write("[DEFAULT]\n")
        file.write(f"LONG_COMMIT_HASH={test_hash}\n")
        file.write(f"SHORT_COMMIT_HASH={test_hash[:7]}\n")
        file.write(f"EXTRACTED_VERSION={test_version}")

    response = client.request(
        "GET",
        "/v1/metadata",
        headers=authHeaders,
    )

    # Validate that the response reads from version_info
    assert response.json()["commit_hash"] == test_hash
    assert response.json()["version"] == test_version

    assert response.status_code == 200
