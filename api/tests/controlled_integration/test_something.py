from ..test_utils.token import authHeaders


def test_search_by_subdivision(client):
    """Test search by subdivision"""

    params = [
        ("subdivision_name", "Ontario"),
    ]
    response = client.request(
        "GET",
        "/v1/gtfs_feeds",
        headers=authHeaders,
        params=params,
    )
    assert response.status_code == 200

    # Response should be a list of 2 feeds (according to the test data)
    feeds = response.json()
    assert isinstance(feeds, list), "Response should be a list."
    assert len(feeds) == 2, f"Expected 2 feeds for subdivision Ontario, got {len(feeds)}."
    assert feeds[0]["id"] == "mdb-2"
    assert feeds[1]["id"] == "mdb-3"
