# coding: utf-8
import os

from fastapi.testclient import TestClient

from feeds_gen.models.basic_feed import BasicFeed  # noqa: F401
from feeds_gen.models.gtfs_feed import GtfsFeed  # noqa: F401

# to load those environment variables
import test_database


def test_feeds_get(client: TestClient):
    """Test case for feeds_get
    
    """
    params = [("limit", 10),     ("offset", 0),     ("filter", 'status=active'),     ("sort", '+provider')]
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
    """Test case for feeds_gtfs_get

    
    """

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
    """Test case for feeds_gtfs_id_get

    
    """

    headers = {
        "ApiKeyAuth": "special-key",
    }
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}".format(id='mdb-1'),
        headers=headers,
    )

    # uncomment below to assert the status code of the HTTP response
    assert response.status_code == 200


def test_feeds_gtfs_rt_get(client: TestClient):
    """Test case for feeds_gtfs_get


    """

    params = [("limit", 10), ("offset", 0), ("filter", 'status=active'), ("sort", '+provider'),
              ("bounding_latitudes", '41.46,42.67'), ("bounding_longitudes", '-78.58,-87-29'),
              ("bounding_filter_method", 'completely_enclosed')]
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
    """Test case for feeds_gtfs_id_get


    """

    headers = {
        "ApiKeyAuth": "special-key",
    }
    response = client.request(
        "GET",
        "/v1/gtfs_rt_feeds/{id}".format(id='mdb-1561'),
        headers=headers,
    )

    assert response.status_code == 200


def test_feeds_id_get(client: TestClient):
    """Test case for feeds_id_get

    
    """

    headers = {
        "ApiKeyAuth": "special-key",
    }
    response = client.request(
        "GET",
        "/v1/feeds/{id}".format(id='mdb-1'),
        headers=headers,
    )

    assert response.status_code == 200
