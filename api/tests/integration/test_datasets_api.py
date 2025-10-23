# coding: utf-8
from fastapi.testclient import TestClient

from tests.test_utils.database import TEST_DATASET_STABLE_IDS, TEST_GTFS_FEED_STABLE_IDS
from tests.test_utils.token import authHeaders


def test_datasets_gtfs_id_get(client: TestClient):
    """Test case for datasets_gtfs_id_get"""

    response = client.request(
        "GET",
        "/v1/datasets/gtfs/{id}".format(id=TEST_DATASET_STABLE_IDS[0]),
        headers=authHeaders,
    )

    assert response.status_code == 200


def test_feeds_gtfs_id_datasets_get(client: TestClient):
    """Test case for feeds_gtfs_id_datasets_get"""
    params = [
        ("latest", False),
        ("limit", 10),
        ("offset", 0),
        ("filter", "status=active"),
        ("sort", "+provider"),
        ("bounding_latitudes", "41.46,42.67"),
        ("bounding_longitudes", "-78.58,-87.29"),
        ("bounding_filter_method", "completely_enclosed"),
    ]
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets".format(id=TEST_GTFS_FEED_STABLE_IDS[0]),
        headers=authHeaders,
        params=params,
    )

    assert response.status_code == 200


def test_feeds_gtfs_datasets_latest_get(client: TestClient):
    """Test case for feeds_gtfs_id_datasets_get"""
    params = [
        ("latest", True),
        ("limit", 10),
        ("offset", 0),
        ("filter", "status=active"),
        ("sort", "+provider"),
    ]
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets".format(id=TEST_GTFS_FEED_STABLE_IDS[0]),
        headers=authHeaders,
        params=params,
    )

    assert response.status_code == 200
    json_response = response.json()
    assert len(json_response) == 1, "Expected only the latest datasets"
    assert json_response[0]["id"] == TEST_DATASET_STABLE_IDS[1]  # dataset-2


def test_feeds_wrong_gtfs_id_datasets_get(client: TestClient):
    """Test case for feeds_gtfs_id_datasets_get where the gtfs feed id does not exist"""

    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets".format(id="nonexistent"),
        headers=authHeaders,
    )

    assert response.status_code == 404


def test_feeds_gtfs_id_no_datasets_get(client: TestClient):
    """Test case for feeds_gtfs_id_datasets_get where the gtfs feed does not have any dataset"""

    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets".format(id="mdb-20"),
        headers=authHeaders,
    )

    assert response.status_code == 200
    assert len(response.json()) == 0, "Expected no datasets, but got some"
