# coding: utf-8
from fastapi.testclient import TestClient

import test_database


def test_datasets_gtfs_id_get(client: TestClient):
    """Test case for datasets_gtfs_id_get

    
    """

    headers = {
        "ApiKeyAuth": "special-key",
    }
    response = client.request(
        "GET",
        "/v1/datasets/gtfs/{id}".format(id='9d4feb5a-adc2-4852-91ad-0cb80c701fa6'),
        headers=headers,
    )

    assert response.status_code == 200


def test_feeds_gtfs_id_datasets_get(client: TestClient):
    """Test case for feeds_gtfs_id_datasets_get

    
    """
    params = [("latest", False),     ("limit", 10),     ("offset", 0),     ("filter", 'status=active'),     ("sort", '+provider'),     ("bounding_latitudes", '41.46,42.67'),     ("bounding_longitudes", '-78.58,-87.29'),     ("bounding_filter_method", 'completely_enclosed')]
    headers = {
        "ApiKeyAuth": "special-key",
    }
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets".format(id='116e51b1-9d91-41a3-8894-56eda76c3036'),
        headers=headers,
        params=params,
    )

    assert response.status_code == 200
