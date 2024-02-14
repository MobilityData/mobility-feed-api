# coding: utf-8
from fastapi.testclient import TestClient
from datetime import timedelta

from .test_utils.database import TEST_GTFS_FEED_STABLE_IDS, TEST_GTFS_RT_FEED_STABLE_ID, TEST_DATASET_STABLE_IDS
from .test_utils.token import authHeaders
from .test_utils.database import datasets_download_first_date


def test_feeds_get(client: TestClient):
    """Test case for feeds_get"""
    params = [
        ("limit", 10),
        ("offset", 0),
        ("filter", "status=active"),
        ("sort", "+provider"),
    ]
    response = client.request(
        "GET",
        "/v1/feeds",
        headers=authHeaders,
        params=params,
    )

    assert response.status_code == 200


def test_feeds_gtfs_get(client: TestClient):
    """Test case for feeds_gtfs_get"""

    params = []
    response = client.request(
        "GET",
        "/v1/gtfs_feeds",
        headers=authHeaders,
        params=params,
    )

    assert response.status_code == 200


def test_feeds_gtfs_id_get(client: TestClient):
    """Test case for feeds_gtfs_id_get"""
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}".format(id=TEST_GTFS_FEED_STABLE_IDS[0]),
        headers=authHeaders,
    )

    assert response.status_code == 200


def test_fetch_gtfs_feeds_with_complete_bounding_box_enclosure(client: TestClient):
    """Test fetching GTFS feeds with a bounding box filter set to 'completely_enclosed', ensuring that feeds strictly
    within the specified coordinates are fetched."""
    params = [
        ("limit", 10),
        ("offset", 0),
        ("filter", "status=active"),
        ("sort", "+provider"),
        ("dataset_latitudes", "37.6,38.24"),
        ("dataset_longitudes", "-84.9,-84.47"),
        ("bounding_filter_method", "completely_enclosed"),
    ]
    response = client.request(
        "GET",
        "/v1/gtfs_feeds",
        headers=authHeaders,
        params=params,
    )
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_fetch_gtfs_feeds_with_incorrect_filter_method(client: TestClient):
    """Test fetching GTFS feeds with an incorrectly formatted latitude value for bounding box filter, expecting a 400
    error due to malformed latitude coordinates."""

    params = [
        ("limit", 10),
        ("offset", 0),
        ("filter", "status=active"),
        ("sort", "+provider"),
        ("dataset_latitudes", "37.6, 38.24"),
        ("dataset_longitudes", "-84.9,-84.47"),
        ("bounding_filter_method", "incorrect"),
    ]
    response = client.request(
        "GET",
        "/v1/gtfs_feeds",
        headers=authHeaders,
        params=params,
    )
    assert response.status_code == 400


def test_fetch_gtfs_feeds_with_incorrect_latitude_for_bounding_box(client: TestClient):
    """Test fetching GTFS feeds with an incorrectly formatted latitude value for bounding box filter, expecting a 400
    error due to malformed latitude coordinates."""

    params = [
        ("limit", 10),
        ("offset", 0),
        ("filter", "status=active"),
        ("sort", "+provider"),
        ("dataset_latitudes", "41.46"),
        ("dataset_longitudes", "-78.58,-87-29"),
        ("bounding_filter_method", "completely_enclosed"),
    ]
    response = client.request(
        "GET",
        "/v1/gtfs_feeds",
        headers=authHeaders,
        params=params,
    )
    assert response.status_code == 422


def test_fetch_gtfs_feeds_with_malformed_bounding_box_coordinates(client: TestClient):
    """Test fetching GTFS feeds with incorrectly formatted bounding box coordinates, expecting a 400 error due to
    malformed longitude and latitude values."""

    params = [
        ("limit", 10),
        ("offset", 0),
        ("filter", "status=active"),
        ("sort", "+provider"),
        ("dataset_latitudes", "41.46,42.67"),
        ("dataset_longitudes", "-78.58,-87-29"),
        ("bounding_filter_method", "completely_enclosed"),
    ]
    response = client.request(
        "GET",
        "/v1/gtfs_feeds",
        headers=authHeaders,
        params=params,
    )
    assert response.status_code == 422


def test_fetch_gtfs_feeds_with_incomplete_latitude_in_bounding_box(client: TestClient):
    """Test fetching GTFS feeds with an incomplete latitude value in the bounding box filter, expecting a 400 error due
    to missing latitude information."""

    params = [
        ("limit", 10),
        ("offset", 0),
        ("filter", "status=active"),
        ("sort", "+provider"),
        ("dataset_latitudes", "41.46, -"),
        ("dataset_longitudes", "-78.58,-87-29"),
        ("bounding_filter_method", "completely_enclosed"),
    ]
    response = client.request(
        "GET",
        "/v1/gtfs_feeds",
        headers=authHeaders,
        params=params,
    )
    assert response.status_code == 422


def test_feeds_gtfs_rt_id_get(client: TestClient):
    """Test case for feeds_gtfs_rt_id_get"""
    response = client.request(
        "GET",
        "/v1/gtfs_rt_feeds/{id}".format(id=TEST_GTFS_RT_FEED_STABLE_ID),
        headers=authHeaders,
    )

    assert response.status_code == 200


def test_feeds_id_get(client: TestClient):
    """Test case for feeds_id_get"""
    response = client.request(
        "GET",
        "/v1/feeds/{id}".format(id=TEST_GTFS_FEED_STABLE_IDS[0]),
        headers=authHeaders,
    )

    assert response.status_code == 200


def test_get_gtfs_feed_datasets_with_download_at_before_before(client: TestClient):
    """Test case for get_gtfs_feed_datasets with a download_at filter by date before all downloads
    Expected result: empty list
    """
    before_all_downloads = datasets_download_first_date - timedelta(days=10)
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets?downloaded_before={date}".format(
            id=TEST_GTFS_FEED_STABLE_IDS[0], date=before_all_downloads
        ),
        headers=authHeaders,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_get_gtfs_feed_datasets_with_download_at_before_after(client: TestClient):
    """Test case for get_gtfs_feed_datasets with a download_at filter by the date before after all downloads
    Expected result: the full list of datasets
    """
    datasets = get_all_datasets(client)
    date = datasets_download_first_date + timedelta(days=10)
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets?downloaded_before={date}".format(id=TEST_GTFS_FEED_STABLE_IDS[0], date=date),
        headers=authHeaders,
    )

    assert response.status_code == 200
    assert response.json() == datasets


def get_all_datasets(client):
    unfiltered_response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets".format(id=TEST_GTFS_FEED_STABLE_IDS[0]),
        headers=authHeaders,
    )
    datasets = []
    for dataset in unfiltered_response.json():
        if dataset["feed_id"] == TEST_GTFS_FEED_STABLE_IDS[0]:
            datasets.append(dataset)
    return datasets


def test_get_gtfs_feed_datasets_with_download_at_before_the_first_dataset(client: TestClient):
    """Test case for get_gtfs_feed_datasets with a download_at filter by the date before of the first dataset
    Expected result: the first dataset
    """
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets?downloaded_before={date}".format(
            id=TEST_GTFS_FEED_STABLE_IDS[0], date=datasets_download_first_date
        ),
        headers=authHeaders,
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["feed_id"] == TEST_GTFS_FEED_STABLE_IDS[0]
    assert response.json()[0]["id"] == TEST_DATASET_STABLE_IDS[0]


def test_get_gtfs_feed_datasets_with_download_at_after_after(client: TestClient):
    """Test case for get_gtfs_feed_datasets with a download_at filter that is after all downloads
    Expected result: empty list
    """
    date = datasets_download_first_date + timedelta(days=10)
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets?downloaded_after={date}".format(id=TEST_GTFS_FEED_STABLE_IDS[0], date=date),
        headers=authHeaders,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_get_gtfs_feed_datasets_with_download_at_after_before(client: TestClient):
    """Test case for get_gtfs_feed_datasets with a download_at filter by the after operation with date before
     all downloads
    Expected result: the full list of datasets
    """
    datasets = get_all_datasets(client)
    date = datasets_download_first_date - timedelta(days=1)
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets?downloaded_after={date}".format(id=TEST_GTFS_FEED_STABLE_IDS[0], date=date),
        headers=authHeaders,
    )

    assert response.status_code == 200
    assert response.json() == datasets


def test_get_gtfs_feed_datasets_with_download_at_after_first(client: TestClient):
    """Test case for get_gtfs_feed_datasets with a download_at
    filter by the after operation with date after the first dataset
    Expected result: the full list of datasets
    """
    datasets = get_all_datasets(client)
    datasets.pop(0)
    date = datasets_download_first_date + timedelta(days=1)
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets?downloaded_after={date}".format(id=TEST_GTFS_FEED_STABLE_IDS[0], date=date),
        headers=authHeaders,
    )

    assert response.status_code == 200
    assert len(response.json()) == len(datasets)
    assert response.json() == datasets
