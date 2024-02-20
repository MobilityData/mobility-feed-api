# coding: utf-8
import json
import re

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

    data = json.loads(response.text)

    # Check the format of the version. e.g. v1.2.3
    version = data.get("version")
    assert version and re.match(r"^v\d+\.\d+\.\d+", version)

    # For the commit hash, it's safe to say it should be more than 20 characters.
    commit_hash = data.get("commit_hash")
    assert commit_hash and len(commit_hash) > 20
