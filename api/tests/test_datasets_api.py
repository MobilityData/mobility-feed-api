# coding: utf-8
from fastapi.testclient import TestClient

from .test_utils.database import TEST_DATASET_STABLE_IDS
from .test_utils.token import authHeaders


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
        "/v1/gtfs_feeds/{id}/datasets".format(id=TEST_DATASET_STABLE_IDS[0]),
        headers=authHeaders,
        params=params,
    )

    assert response.status_code == 200
