# coding: utf-8
from fastapi.testclient import TestClient

from tests.test_utils.token import authHeaders


def test_gbfs_populate(client: TestClient):
    """Test case for gbfs populate"""

    response = client.request(
        "GET",
        "/v1/search",
        headers=authHeaders,
    )

    assert response.status_code == 200
    json_response = response.json()
    assert json_response["total"] == 4

    results = json_response["results"]
    assert len(results) == 4, "There should be 4 results in the response"

    feed_1 = next((item for item in results if item["id"] == "gbfs-feed_1"), None)
    feed_2 = next((item for item in results if item["id"] == "gbfs-feed_2"), None)
    feed_3 = next((item for item in results if item["id"] == "gbfs-feed_3"), None)
    feed_4 = next((item for item in results if item["id"] == "gbfs-feed_4"), None)
    assert feed_1["status"] == "active"
    assert feed_2["status"] == "deprecated", "Feed 2 should be deprecated since it was removed in the 2nd systems.csv"
    assert feed_3["status"] == "active"
    assert feed_4["status"] == "active"

    assert feed_3["provider"] == "Feed 3 modified", "Feed 3 name was modified in the 2nd systems.csv"
