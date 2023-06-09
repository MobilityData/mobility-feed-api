# coding: utf-8

from fastapi.testclient import TestClient


from feeds.models.dataset import Dataset  # noqa: F401


def test_datasets_gtfs_get(client: TestClient):
    """Test case for datasets_gtfs_get

    
    """
    params = [("limit", 10),     ("offset", 0),     ("filter", 'status=active'),     ("sort", '+provider'),     ("bounding_latitudes", '41.46,42.67'),     ("bounding_longitudes", '-78.58,-87-29'),     ("bounding_filter_method", 'completely_enclosed')]
    headers = {
        "ApiKeyAuth": "special-key",
    }
    response = client.request(
        "GET",
        "/datasets/gtfs",
        headers=headers,
        params=params,
    )

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200


def test_datasets_gtfs_id_get(client: TestClient):
    """Test case for datasets_gtfs_id_get

    
    """

    headers = {
        "ApiKeyAuth": "special-key",
    }
    response = client.request(
        "GET",
        "/datasets/gtfs/{id}".format(id='dataset_0'),
        headers=headers,
    )

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200


def test_feeds_gtfs_id_datasets_get(client: TestClient):
    """Test case for feeds_gtfs_id_datasets_get

    
    """
    params = [("latest", False),     ("limit", 10),     ("offset", 0),     ("filter", 'status=active'),     ("sort", '+provider'),     ("bounding_latitudes", '41.46,42.67'),     ("bounding_longitudes", '-78.58,-87-29'),     ("bounding_filter_method", 'completely_enclosed')]
    headers = {
        "ApiKeyAuth": "special-key",
    }
    response = client.request(
        "GET",
        "/feeds/gtfs/{id}/datasets".format(id='feed_0'),
        headers=headers,
        params=params,
    )

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200

