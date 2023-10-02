# coding: utf-8
from fastapi.testclient import TestClient

from test_utils.database import TEST_GTFS_FEED_STABLE_IDS, TEST_GTFS_RT_FEED_STABLE_ID


def test_feeds_get(client: TestClient):
    """Test case for feeds_get"""
    params = [
        ("limit", 10),
        ("offset", 0),
        ("filter", "status=active"),
        ("sort", "+provider"),
    ]
    headers = {
        "ApiKeyAuth": "special-key",
    }
    response = client.request(
        "GET",
        "/v1/feeds",
        headers=headers,
        params=params,
    )

    assert response.status_code == 200


def test_feeds_gtfs_get(client: TestClient):
    """Test case for feeds_gtfs_get"""

    params = []
    headers = {
        "ApiKeyAuth": "special-key",
    }
    response = client.request(
        "GET",
        "/v1/gtfs_feeds",
        headers=headers,
        params=params,
    )

    assert response.status_code == 200


def test_feeds_gtfs_id_get(client: TestClient):
    """Test case for feeds_gtfs_id_get"""

    headers = {
        "ApiKeyAuth": "special-key",
    }
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}".format(id=TEST_GTFS_FEED_STABLE_IDS[0]),
        headers=headers,
    )

    # uncomment below to assert the status code of the HTTP response
    assert response.status_code == 200


def test_feeds_gtfs_rt_get(client: TestClient):
    """Test case for feeds_gtfs_get"""

    params = [("limit", 10), ("offset", 0), ("filter", "status=active"), ("sort", "+provider")]
    headers = {
        "ApiKeyAuth": "special-key",
    }
    response = client.request(
        "GET",
        "/v1/gtfs_rt_feeds",
        headers=headers,
        params=params,
    )

    # uncomment below to assert the status code of the HTTP response
    assert response.status_code == 200


def test_feeds_gtfs_rt_id_get(client: TestClient):
    """Test case for feeds_gtfs_id_get"""

    headers = {
        "ApiKeyAuth": "special-key",
    }
    response = client.request(
        "GET",
        "/v1/gtfs_rt_feeds/{id}".format(id=TEST_GTFS_RT_FEED_STABLE_ID),
        headers=headers,
    )

    assert response.status_code == 200


def test_feeds_id_get(client: TestClient):
    """Test case for feeds_id_get"""

    headers = {
        "ApiKeyAuth": "special-key",
    }
    response = client.request(
        "GET",
        "/v1/feeds/{id}".format(id=TEST_GTFS_FEED_STABLE_IDS[0]),
        headers=headers,
    )

    assert response.status_code == 200
