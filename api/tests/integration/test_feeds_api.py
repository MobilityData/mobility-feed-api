# coding: utf-8
import pytest
from fastapi.testclient import TestClient
from datetime import timedelta

from tests.test_utils.database import TEST_GTFS_FEED_STABLE_IDS, TEST_GTFS_RT_FEED_STABLE_ID, TEST_DATASET_STABLE_IDS
from tests.test_utils.token import authHeaders
from tests.test_utils.database import datasets_download_first_date


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


def test_feeds_get(client: TestClient):
    """Test case for feeds_get"""
    params = [
        ("limit", 10),
        ("offset", 0),
        ("status", "active"),
        ("sort", "+provider"),
    ]
    response = client.request(
        "GET",
        "/v1/feeds",
        headers=authHeaders,
        params=params,
    )

    assert response.status_code == 200
    assert len(response.json()) >= 1, "At least one feed should be returned"
    assert len(response.json()) <= 10, "At most 10 feeds should be returned"
    assert all(feed["status"] == "active" for feed in response.json()), "All feeds should be active"


def test_feeds_get_with_limit_and_offset(client: TestClient):
    params = [
        ("limit", 5),
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
    assert len(response.json()) == 5


def test_feeds_get_with_limit_and_offset_multiple_locations(client: TestClient):
    # Testing fix for bug #707
    params = [
        ("limit", 2),
        ("offset", 1),
        ("provider", "BlaBlaCar"),
    ]
    response = client.request(
        "GET",
        "/v1/feeds",
        headers=authHeaders,
        params=params,
    )

    assert response.status_code == 200
    assert len(response.json()) == 2


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


def test_non_existent_gtfs_feed_get(client: TestClient):
    """Test case for feeds_gtfs_id_get with a non-existent feed"""
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}".format(id="mdb-4000"),
        headers=authHeaders,
    )

    assert response.status_code == 404


def test_non_existent_dataset_get(client: TestClient):
    """Test case for datasets/gtfs with a non-existent dataset"""
    response = client.request(
        "GET",
        "/v1/datasets/gtfs/{id}".format(id="mdb-1210-202402121801"),
        headers=authHeaders,
    )

    assert response.status_code == 404


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
    assert response.status_code == 422


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


@pytest.mark.parametrize(
    "values",
    [
        {
            "endpoint": "/v1/gtfs_feeds",
            "all_feeds_count": 10,
            "false_feeds_count": 9,
            "true_feeds_count": 1,
            "official_feeds": ["mdb-40"],
        },
        {
            "endpoint": "/v1/gtfs_rt_feeds",
            "all_feeds_count": 3,
            "false_feeds_count": 2,
            "true_feeds_count": 1,
            "official_feeds": ["mdb-1562"],
        },
        {
            "endpoint": "/v1/feeds",
            "all_feeds_count": 16,
            "false_feeds_count": 14,
            "true_feeds_count": 2,
            "official_feeds": ["mdb-1562", "mdb-40"],
        },
        {
            "endpoint": "/v1/gbfs_feeds",
            "all_feeds_count": 3,
            "false_feeds_count": None,
            "true_feeds_count": None,
            "official_feeds": [],
        },
    ],
    ids=["gtfs_feeds", "gtfs_rt_feeds", "feeds", "gbfs_feeds"],
)
def test_feeds_filter_by_official(client: TestClient, values):
    endpoint = values["endpoint"]
    official_feeds = values["official_feeds"]
    all_feeds_count = values["all_feeds_count"]
    false_feeds_count = values["false_feeds_count"]
    true_feeds_count = values["true_feeds_count"]

    # 1 - Test with official not specified should return all feeds
    response_no_filter = client.request(
        "GET",
        endpoint,
        headers=authHeaders,
    )
    assert response_no_filter.status_code == 200
    response_no_filter_json = response_no_filter.json()
    assert (
        len(response_no_filter_json) == all_feeds_count
    ), f"official not specified should return {all_feeds_count} feeds but got {len(response_no_filter_json)}"

    # 2 - Test with official=false
    if false_feeds_count is not None:
        response_official_false = client.request(
            "GET",
            endpoint,
            headers=authHeaders,
            params=[("is_official", "false")],
        )
        assert response_official_false.status_code == 200
        response_official_false_json = response_official_false.json()
        assert (
            len(response_official_false_json) == false_feeds_count
        ), f"official=false should return {false_feeds_count} feeds but got {len(response_official_false_json)}"
        assert not any(
            response["id"] in official_feeds for response in response_official_false_json
        ), f"official=false expected no feed with stable_id {official_feeds} since it is official"

    # 3 - Test with official=true
    if true_feeds_count is not None:
        response = client.request(
            "GET",
            endpoint,
            headers=authHeaders,
            params=[("is_official", "true")],
        )
        assert response.status_code == 200
        json_response = response.json()
        assert len(json_response) == true_feeds_count, f"official=true should return {true_feeds_count} feeds"
        assert json_response[0]["id"] in official_feeds, f"official=true should return {official_feeds}"


def test_non_existent_gtfs_rt_feed_get(client: TestClient):
    """Test case for feeds_gtfs_rt_id_get with a non-existent feed"""
    response = client.request(
        "GET",
        "/v1/gtfs_rt_feeds/{id}".format(id="mdb-3000"),
        headers=authHeaders,
    )

    assert response.status_code == 404


def test_feeds_id_get(client: TestClient):
    """Test case for feeds_id_get"""
    response = client.request(
        "GET",
        "/v1/feeds/{id}".format(id=TEST_GTFS_FEED_STABLE_IDS[0]),
        headers=authHeaders,
    )

    assert response.status_code == 200


def test_non_existent_feed_get(client: TestClient):
    """Test case for feeds_id_get with a non-existent feed"""
    response = client.request(
        "GET",
        "/v1/feeds/{id}".format(id="mdb-2090"),
        headers=authHeaders,
    )

    assert response.status_code == 404


def test_get_gtfs_feed_datasets_with_downloaded_before_before(client: TestClient):
    """Test case for get_gtfs_feed_datasets filter by downloaded_before with date before all downloads
    Expected result: empty list
    """
    date = datasets_download_first_date - timedelta(days=10)
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets?downloaded_before={date}".format(
            id=TEST_GTFS_FEED_STABLE_IDS[0], date=date.isoformat()
        ),
        headers=authHeaders,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_get_gtfs_feed_datasets_with_downloaded_before_after(client: TestClient):
    """Test case for get_gtfs_feed_datasets filter by downloaded_before with date after all downloads
    Expected result: the full list of datasets
    """
    datasets = get_all_datasets(client)
    date = datasets_download_first_date + timedelta(days=10)
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets?downloaded_before={date}".format(
            id=TEST_GTFS_FEED_STABLE_IDS[0], date=date.isoformat()
        ),
        headers=authHeaders,
    )

    assert response.status_code == 200
    assert response.json() == datasets


def test_get_gtfs_feed_datasets_with_downloaded_before_the_first_dataset(client: TestClient):
    """Test case for get_gtfs_feed_datasets filter by downloaded_before with date before of the first dataset
    Expected result: the first dataset
    """
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets?downloaded_before={date}".format(
            id=TEST_GTFS_FEED_STABLE_IDS[0], date=datasets_download_first_date.isoformat()
        ),
        headers=authHeaders,
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["feed_id"] == TEST_GTFS_FEED_STABLE_IDS[0]
    assert response.json()[0]["id"] == TEST_DATASET_STABLE_IDS[0]


def test_get_gtfs_feed_datasets_with_limit(client: TestClient):
    """Test case for get_gtfs_feed_datasets limit of returning 1
    Expected result: only one dataset out of two
    """
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets?limit={limit}".format(id=TEST_GTFS_FEED_STABLE_IDS[0], limit=1),
        headers=authHeaders,
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    # the second dataset should be returned as it is the most recent
    assert response.json()[0]["id"] == TEST_DATASET_STABLE_IDS[1]


def test_get_gtfs_feed_datasets_with_offset(client: TestClient):
    """Test case for get_gtfs_feed_datasets offset of returning the second element out of 2
    Expected result: the second dataset
    """
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets?offset={offset}".format(id=TEST_GTFS_FEED_STABLE_IDS[0], offset=1),
        headers=authHeaders,
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    # The first dataset should be returned as it is the oldest
    assert response.json()[0]["id"] == TEST_DATASET_STABLE_IDS[0]


def test_get_gtfs_feed_datasets_with_downloaded_after_after(client: TestClient):
    """Test case for get_gtfs_feed_datasets filter downloaded_after with date after all downloads
    Expected result: empty list
    """
    date = datasets_download_first_date + timedelta(days=10)
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets?downloaded_after={date}".format(
            id=TEST_GTFS_FEED_STABLE_IDS[0], date=date.isoformat()
        ),
        headers=authHeaders,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_get_gtfs_feed_datasets_with_downloaded_after_before(client: TestClient):
    """Test case for get_gtfs_feed_datasets filter by downloaded_after with date before
     all downloads
    Expected result: the full list of datasets
    """
    datasets = get_all_datasets(client)
    date = datasets_download_first_date - timedelta(days=1)
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets?downloaded_after={date}".format(
            id=TEST_GTFS_FEED_STABLE_IDS[0], date=date.isoformat()
        ),
        headers=authHeaders,
    )

    assert response.status_code == 200
    assert response.json() == datasets


def test_get_gtfs_feed_datasets_with_downloaded_after_first(client: TestClient):
    """Test case for get_gtfs_feed_datasets filter by downloaded_after date after the first dataset
    Expected result: the full list of datasets
    """
    datasets = get_all_datasets(client)
    datasets.pop(len(datasets) - 1)
    date = datasets_download_first_date + timedelta(days=1)
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets?downloaded_after={date}".format(
            id=TEST_GTFS_FEED_STABLE_IDS[0], date=date.isoformat()
        ),
        headers=authHeaders,
    )

    assert response.status_code == 200
    assert len(response.json()) == len(datasets)
    assert response.json() == datasets


def test_get_gtfs_feed_datasets_with_downloaded_before_invalid_date(client: TestClient):
    """Test case for get_gtfs_feed_datasets with an invalid date in download_before
    Expected result: the full list of datasets
    """
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets?downloaded_before={date}".format(
            id=TEST_GTFS_FEED_STABLE_IDS[0], date="invalid_date"
        ),
        headers=authHeaders,
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Invalid date format for 'downloaded_before'. Expected ISO 8601 format, example: "
        "'2021-01-01T00:00:00Z'"
    }


def test_get_gtfs_feed_datasets_with_downloaded_after_invalid_date(client: TestClient):
    """Test case for get_gtfs_feed_datasets with an invalid date in download_after
    filter by the after operation with date after the first dataset
    Expected result: the full list of datasets
    """
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets?downloaded_after={date}".format(
            id=TEST_GTFS_FEED_STABLE_IDS[0], date="invalid_date"
        ),
        headers=authHeaders,
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Invalid date format for 'downloaded_after'. Expected ISO 8601 format, example: "
        "'2021-01-01T00:00:00Z'"
    }


def test_get_gtfs_feed_datasets_with_downloaded_date_between(client: TestClient):
    """Test case for get_gtfs_feed_datasets filter by downloaded_before and downloaded_after containing
     all downloads
    Expected result: the full list of datasets
    """
    datasets = get_all_datasets(client)
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/datasets?downloaded_after={first}&downloaded_before={last}".format(
            id=TEST_GTFS_FEED_STABLE_IDS[0],
            first=datasets_download_first_date.isoformat(),
            last=(datasets_download_first_date + timedelta(days=len(datasets) - 1)).isoformat(),
        ),
        headers=authHeaders,
    )

    assert response.status_code == 200
    assert response.json() == datasets


def test_get_gtfs_feed_gtfs_rt_feeds_valid_id(client: TestClient):
    """Test case for get_gtfs_feed_gtfs_rt_feeds with a valid GTFS feed ID
    Expected result: a list of GTFS RT feeds related to the GTFS feed
    """
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/{id}/gtfs_rt_feeds".format(id=TEST_GTFS_FEED_STABLE_IDS[0]),
        headers=authHeaders,
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == TEST_GTFS_RT_FEED_STABLE_ID
    assert response.json()[0]["feed_references"][0] == TEST_GTFS_FEED_STABLE_IDS[0]


def test_get_gtfs_feed_gtfs_rt_feeds_invalid_id(client: TestClient):
    """Test case for get_gtfs_feed_gtfs_rt_feeds with an invalid GTFS feed ID
    Expected result: 404 HTTP error
    """
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/THIS_IS_NOT_VALID/gtfs_rt_feeds",
        headers=authHeaders,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "GTFS feed 'THIS_IS_NOT_VALID' not found"}


def test_filter_by_country(client):
    """Test filter by country"""

    params = [
        ("country_code", "CA"),
    ]
    response = client.request(
        "GET",
        "/v1/gtfs_feeds",
        headers=authHeaders,
        params=params,
    )
    assert response.status_code == 200

    # Response should be a list of 3 feeds (according to the test data)
    feeds = response.json()
    assert isinstance(feeds, list), "Response should be a list."
    assert len(feeds) == 3, f"Expected 3 feeds for country_code CA, got {len(feeds)}."
    assert any(feed["id"] == "mdb-50" for feed in feeds)
    assert any(feed["id"] == "mdb-40" for feed in feeds)
    assert any(feed["id"] == "mdb-702" for feed in feeds)


def test_filter_by_subdivision(client):
    """Test filter by subdivision"""

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
    assert any(feed["id"] == "mdb-50" for feed in feeds)
    assert any(feed["id"] == "mdb-40" for feed in feeds)


def test_filter_by_municipality(client):
    """Test filter by municipality"""
    params = {"municipality": "Barrie"}
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
    assert len(feeds) == 1, f"Expected 1 feeds for municipality Barrie, got {len(feeds)}."
    assert any(feed["id"] == "mdb-50" for feed in feeds)


def test_filter_by_wrong_location(client):
    """Test filter by wrong location"""

    params = {"country_code": "US", "municipality": "Barrie"}

    response = client.request(
        "GET",
        "/v1/gtfs_feeds",
        headers=authHeaders,
        params=params,
    )
    assert response.status_code == 200

    # Response should be an empty list (according to the test data)
    feeds = response.json()
    assert isinstance(feeds, list), "Response should be a list."
    assert len(feeds) == 0, f"Expected no feed for country US and municipality Barrie, got {len(feeds)}."


def test_filter_by_subdivision_and_municipality(client):
    """Test filter by location"""

    params = {"subdivision_name": "British Columbia", "municipality": "Whistler"}

    response = client.request(
        "GET",
        "/v1/gtfs_feeds",
        headers=authHeaders,
        params=params,
    )
    assert response.status_code == 200

    # Response should be a list of 1 feed (according to the test data)
    feeds = response.json()
    assert isinstance(feeds, list), "Response should be a list."
    assert (
        len(feeds) == 1
    ), f"Expected 1 feed for subdivision_name British Columbia and municipality Whistler, got {len(feeds)}."
    assert any(feed["id"] == "mdb-702" for feed in feeds)


@pytest.mark.parametrize(
    "values",
    [
        {"response_code": 200, "expected_feed_ids": ["mdb-1561", "mdb-1562", "mdb-1563"]},
        {"entity_types": "vp", "response_code": 200, "expected_feed_ids": ["mdb-1561"]},
        {"entity_types": "sa,vp", "response_code": 200, "expected_feed_ids": ["mdb-1561", "mdb-1562"]},
        {"entity_types": "", "response_code": 200, "expected_feed_ids": ["mdb-1561", "mdb-1562", "mdb-1563"]},
        {"entity_types": "not_valid", "response_code": 422},
        {"country_code": "CA", "response_code": 200, "expected_feed_ids": ["mdb-1562"]},
        {"country_code": "CA", "entity_types": "sa,vp", "response_code": 200, "expected_feed_ids": ["mdb-1562"]},
        {"country_code": "", "response_code": 200, "expected_feed_ids": ["mdb-1561", "mdb-1562", "mdb-1563"]},
        {"provider": "no-found-provider", "response_code": 200, "expected_feed_ids": []},
        {"provider": "transit", "response_code": 200, "expected_feed_ids": ["mdb-1562"]},
        {"provider": "", "response_code": 200, "expected_feed_ids": ["mdb-1561", "mdb-1562", "mdb-1563"]},
        {"producer_url": "foo.org", "response_code": 200, "expected_feed_ids": ["mdb-1562"]},
        {"producer_url": "", "response_code": 200, "expected_feed_ids": ["mdb-1561", "mdb-1562", "mdb-1563"]},
        {"subdivision_name": "bc", "response_code": 200, "expected_feed_ids": ["mdb-1562"]},
        {"subdivision_name": "", "response_code": 200, "expected_feed_ids": ["mdb-1561", "mdb-1562", "mdb-1563"]},
        {"municipality": "vanco", "response_code": 200, "expected_feed_ids": ["mdb-1562"]},
        {"municipality": "", "response_code": 200, "expected_feed_ids": ["mdb-1561", "mdb-1562", "mdb-1563"]},
    ],
    ids=[
        "all_none",
        "single_entity_type_vp",
        "multiple_entity_types_sa_vp",
        "empty_entity_types",
        "invalid_entity_type",
        "country_code_ca",
        "country_code_ca_entity_types_sa_vp",
        "empty_country_code",
        "provider_no_found_provider",
        "provider_transit",
        "empty_provider",
        "producer_url_foo_org",
        "empty_producer_url",
        "subdivision_name_bc",
        "empty_subdivision_name",
        "municipality_vanco",
        "empty_municipality",
    ],
)
def test_gtfs_rt_filters(client, values):
    """Test /v1/gtfs_rt_feeds filters by entity types, country code, provider, producer URL, subdivision name, and
    municipality."""

    params = {
        "entity_types": values["entity_types"] if "entity_types" in values else None,
        "country_code": values["country_code"] if "country_code" in values else None,
        "provider": values["provider"] if "provider" in values else None,
        "producer_url": values["producer_url"] if "producer_url" in values else None,
        "subdivision_name": values["subdivision_name"] if "subdivision_name" in values else None,
        "municipality": values["municipality"] if "municipality" in values else None,
    }

    response = client.request(
        "GET",
        "/v1/gtfs_rt_feeds",
        headers=authHeaders,
        params=params,
    )
    if int(values["response_code"]) != 200:
        assert response.status_code == values["response_code"]
        return

    feeds = response.json()
    assert isinstance(feeds, list), "Response should be a list."
    assert len(feeds) == len(values["expected_feed_ids"])
    if len(values["expected_feed_ids"]) != 0:
        assert any(feed["id"] in values["expected_feed_ids"] for feed in feeds)


@pytest.mark.parametrize(
    "values",
    [
        {"stable_id": "mdb-1562", "target_id": "mdb-40"},
        {"stable_id": "mdb-1563", "target_id": "mdb-50"},
    ],
    ids=[
        "integer_static_reference",
        "string_static_reference",
    ],
)
def test_gtfs_rt_reference(client, values):
    """Test /v1/gtfs_rt_feeds to make sure it returns the proper feed_reference for integer and string references."""

    stable_id = values["stable_id"] if "stable_id" in values else None
    response = client.request(
        "GET",
        f"/v1/gtfs_rt_feeds/{stable_id}",
        headers=authHeaders,
    )
    assert response.status_code == 200
    feed = response.json()
    assert feed["feed_references"][0] == values["target_id"]


def test_gtfs_redirect(client):
    """Test that a returned feed contains the proper redirects for integer or string redirects."""

    response = client.request(
        "GET",
        "/v1/feeds/mdb-50",
        headers=authHeaders,
    )
    assert response.status_code == 200
    feed = response.json()
    assert feed["redirects"][0]["comment"] == "Some"
    assert feed["redirects"][1]["comment"] == "Comment"
    # spreadsheet contains '40|mdb-702'
    assert feed["redirects"][0]["target_id"] == "mdb-40"
    assert feed["redirects"][1]["target_id"] == "mdb-702"

    response = client.request(
        "GET",
        "/v1/feeds/mdb-1562",
        headers=authHeaders,
    )
    assert response.status_code == 200
    feed = response.json()
    assert feed["redirects"][0]["comment"] == ""
    # spreadsheet contains '10'
    assert feed["redirects"][0]["target_id"] == "mdb-10"


@pytest.mark.parametrize(
    "values",
    [
        {"endpoint": "/v1/feeds", "hard_limit": 3500},
        {"endpoint": "/v1/gtfs_feeds", "hard_limit": 2500},
        {"endpoint": "/v1/gtfs_rt_feeds", "hard_limit": 1000},
        {"endpoint": "/v1/gtfs_feeds/mdb-1/datasets", "hard_limit": 500},
        {"endpoint": "/v1/search", "hard_limit": 3500},
        {"endpoint": "/v1/gbfs_feeds", "hard_limit": 500},
    ],
)
def test_hard_limits(client, monkeypatch, values):
    """Test that an error is returned if we request more than the hard limit for each endpoint"""
    hard_limit = values["hard_limit"]

    response = client.request(
        "GET",
        values["endpoint"],
        headers=authHeaders,
        params={"limit": hard_limit + 1},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "values",
    [
        {"response_code": 200, "expected_feed_ids": ["gbfs-system_id_1", "gbfs-system_id_2", "gbfs-system_id_3"]},
        {
            "provider": "Provider Name 1",
            "response_code": 200,
            "expected_feed_ids": ["gbfs-system_id_1", "gbfs-system_id_2"],
        },
        {"provider": "Provider Name 2", "response_code": 200, "expected_feed_ids": ["gbfs-system_id_3"]},
        {
            "country_code": "CA",
            "response_code": 200,
            "expected_feed_ids": ["gbfs-system_id_1", "gbfs-system_id_2", "gbfs-system_id_3"],
        },
        {"country_code": "US", "response_code": 200, "expected_feed_ids": []},
        {"municipality": "Laval", "response_code": 200, "expected_feed_ids": ["gbfs-system_id_2"]},
        {
            "producer_url": "https://www.example.com/gbfs_feed_3/",
            "response_code": 200,
            "expected_feed_ids": ["gbfs-system_id_3"],
        },
        {"system_id": "system_id_1", "response_code": 200, "expected_feed_ids": ["gbfs-system_id_1"]},
        {"version": "3.0", "response_code": 200, "expected_feed_ids": ["gbfs-system_id_1"]},
        {"version": "2.3", "response_code": 200, "expected_feed_ids": ["gbfs-system_id_1", "gbfs-system_id_2"]},
        {"version": "1.0", "response_code": 200, "expected_feed_ids": []},
        {"system_id": "system_id_1", "response_code": 200, "expected_feed_ids": ["gbfs-system_id_1"]},
        {"system_id": "doesnt_exist", "response_code": 200, "expected_feed_ids": []},
    ],
    ids=[
        "all_none",
        "provider_name_1",
        "provider_name_2",
        "country_code_ca",
        "country_code_us",
        "municipality_laval",
        "producer_url",
        "system_id",
        "version_3.0",
        "version_2.3",
        "version_1.0",
        "system_id_1",
        "system_id_doesnt_exist",
    ],
)
def test_gbfs_filters(client, values):
    """Test /v1/gbfs_feeds filters by system_id"""
    params = {
        "provider": values["provider"] if "provider" in values else None,
        "country_code": values["country_code"] if "country_code" in values else None,
        "municipality": values["municipality"] if "municipality" in values else None,
        "producer_url": values["producer_url"] if "producer_url" in values else None,
        "system_id": values["system_id"] if "system_id" in values else None,
        "version": values["version"] if "version" in values else None,
    }
    params = {k: v for k, v in params.items() if v is not None}

    response = client.request(
        "GET",
        "/v1/gbfs_feeds",
        headers=authHeaders,
        params=params,
    )
    assert response.status_code == values["response_code"]
    if values["response_code"] != 200:
        return

    feeds = response.json()
    assert isinstance(feeds, list), "Response should be a list."
    assert len(feeds) == len(values["expected_feed_ids"]), (
        f"Expected {len(values['expected_feed_ids'])} feeds, " f"got {len(feeds)}."
    )
    if len(values["expected_feed_ids"]) != 0:
        assert any(feed["id"] in values["expected_feed_ids"] for feed in feeds)


@pytest.mark.parametrize(
    "values",
    [
        {"response_code": 200, "expected_feed_ids": ["gbfs-system_id_1"]},
        {"response_code": 200, "expected_feed_ids": ["gbfs-system_id_2"]},
        {"response_code": 200, "expected_feed_ids": ["gbfs-system_id_3"]},
        {"response_code": 404},
    ],
    ids=["valid_id", "valid_id_2", "valid_id_3", "invalid_id"],
)
def test_gbfs_feed_id_get(client: TestClient, values):
    """Test case for gbfs_feed_id_get"""
    test_id = values.get("expected_feed_ids", ["dummy_id"])[0]
    response = client.request(
        "GET",
        "/v1/gbfs_feeds/{id}".format(id=test_id),
        headers=authHeaders,
    )

    assert response.status_code == values["response_code"]
    if values["response_code"] != 200:
        return
    assert response.json()["id"] == test_id


@pytest.mark.parametrize(
    "feed_id, expected_license_id, expected_is_spdx, expected_license_notes, expected_license_tags",
    [
        ("mdb-70", "license-1", True, "Notes for license-1", ["family:ODC", "license:open-data-commons"]),
        ("mdb-80", "license-2", False, None, None),
    ],
)
def test_feeds_have_expected_license_info(
    client: TestClient,
    feed_id: str,
    expected_license_id: str,
    expected_is_spdx: bool,
    expected_license_notes: str,
    expected_license_tags: list,
):
    """
    Verify that specified feeds have the expected license id,
    license_is_spdx, license_notes, and license_tags from the test fixture.
    """
    response = client.request(
        "GET",
        "/v1/feeds/{id}".format(id=feed_id),
        headers=authHeaders,
    )

    assert response.status_code == 200
    body = response.json()
    # Ensure the license_id matches the expected license
    assert body["source_info"]["license_id"] == expected_license_id
    # Ensure the license_is_spdx flag matches expectation
    assert body["source_info"]["license_is_spdx"] is expected_is_spdx
    # Check license_notes (may be None)
    assert body["source_info"].get("license_notes") == expected_license_notes
    # Check license_tags (may be None if no tags)
    if expected_license_tags is None:
        assert body["source_info"].get("license_tags") is None
    else:
        assert sorted(body["source_info"].get("license_tags", [])) == sorted(expected_license_tags)


# ---- GTFS Feed Availability endpoint tests ----

AVAILABILITY_FEED_ID = TEST_GTFS_FEED_STABLE_IDS[0]  # mdb-1 — has availability_checks fixture data
AVAILABILITY_CHECKS_COUNT = 5  # number of checks added in extra_test_data.json for mdb-1


def test_gtfs_feed_availability_basic(client: TestClient):
    """GET /v1/gtfs_feeds/{id}/availability returns 200 with expected fields."""
    response = client.request(
        "GET",
        f"/v1/gtfs_feeds/{AVAILABILITY_FEED_ID}/availability",
        headers=authHeaders,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["feed_id"] == AVAILABILITY_FEED_ID
    assert body["total"] == AVAILABILITY_CHECKS_COUNT
    assert body["offset"] == 0
    assert body["limit"] == 100
    assert len(body["checks"]) == AVAILABILITY_CHECKS_COUNT

    # Verify one check has expected fields
    check = body["checks"][0]
    assert "checked_at" in check
    assert "success" in check
    assert check["request_method"] in ("HEAD", "GET")


def test_gtfs_feed_availability_ordered_desc_by_default(client: TestClient):
    """Checks are returned newest → oldest by default."""
    response = client.request(
        "GET",
        f"/v1/gtfs_feeds/{AVAILABILITY_FEED_ID}/availability",
        headers=authHeaders,
    )
    assert response.status_code == 200
    checks = response.json()["checks"]
    timestamps = [c["checked_at"] for c in checks]
    assert timestamps == sorted(timestamps, reverse=True)


def test_gtfs_feed_availability_ordered_asc(client: TestClient):
    """sort=asc returns checks oldest → newest."""
    response = client.request(
        "GET",
        f"/v1/gtfs_feeds/{AVAILABILITY_FEED_ID}/availability",
        headers=authHeaders,
        params={"sort": "asc"},
    )
    assert response.status_code == 200
    checks = response.json()["checks"]
    timestamps = [c["checked_at"] for c in checks]
    assert timestamps == sorted(timestamps)


def test_gtfs_feed_availability_request_method_mapping(client: TestClient):
    """request_type http_head/http_get maps to HEAD/GET in the response."""
    response = client.request(
        "GET",
        f"/v1/gtfs_feeds/{AVAILABILITY_FEED_ID}/availability",
        headers=authHeaders,
    )
    assert response.status_code == 200
    methods = {c["request_method"] for c in response.json()["checks"]}
    # Test data has both HEAD and GET checks
    assert "HEAD" in methods
    assert "GET" in methods


def test_gtfs_feed_availability_filter_from(client: TestClient):
    """from filter excludes checks before the cutoff."""
    response = client.request(
        "GET",
        f"/v1/gtfs_feeds/{AVAILABILITY_FEED_ID}/availability",
        headers=authHeaders,
        params={"from": "2025-03-01T00:00:00Z"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3  # March, April, May checks
    for check in body["checks"]:
        assert check["checked_at"] >= "2025-03-01T00:00:00"


def test_gtfs_feed_availability_filter_to(client: TestClient):
    """to filter excludes checks after the cutoff."""
    response = client.request(
        "GET",
        f"/v1/gtfs_feeds/{AVAILABILITY_FEED_ID}/availability",
        headers=authHeaders,
        params={"to": "2025-02-28T23:59:59Z"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2  # Jan, Feb checks
    for check in body["checks"]:
        assert check["checked_at"] <= "2025-02-28T23:59:59"


def test_gtfs_feed_availability_filter_from_to(client: TestClient):
    """from+to together filters to the intersection."""
    response = client.request(
        "GET",
        f"/v1/gtfs_feeds/{AVAILABILITY_FEED_ID}/availability",
        headers=authHeaders,
        params={"from": "2025-02-01T00:00:00Z", "to": "2025-03-31T23:59:59Z"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2  # Feb, March checks


def test_gtfs_feed_availability_pagination_limit(client: TestClient):
    """limit param returns the correct number of items."""
    response = client.request(
        "GET",
        f"/v1/gtfs_feeds/{AVAILABILITY_FEED_ID}/availability",
        headers=authHeaders,
        params={"limit": 2},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["checks"]) == 2
    assert body["total"] == AVAILABILITY_CHECKS_COUNT
    assert body["limit"] == 2
    assert body["offset"] == 0


def test_gtfs_feed_availability_pagination_offset(client: TestClient):
    """offset param skips items correctly; total remains consistent."""
    first_page = client.request(
        "GET",
        f"/v1/gtfs_feeds/{AVAILABILITY_FEED_ID}/availability",
        headers=authHeaders,
        params={"limit": 2, "offset": 0},
    )
    second_page = client.request(
        "GET",
        f"/v1/gtfs_feeds/{AVAILABILITY_FEED_ID}/availability",
        headers=authHeaders,
        params={"limit": 2, "offset": 2},
    )
    assert first_page.status_code == 200
    assert second_page.status_code == 200
    first = first_page.json()
    second = second_page.json()

    assert first["total"] == second["total"] == AVAILABILITY_CHECKS_COUNT
    assert len(first["checks"]) == 2
    assert len(second["checks"]) == 2
    # No overlap between pages
    first_timestamps = {c["checked_at"] for c in first["checks"]}
    second_timestamps = {c["checked_at"] for c in second["checks"]}
    assert first_timestamps.isdisjoint(second_timestamps)


def test_gtfs_feed_availability_not_found(client: TestClient):
    """Unknown feed ID returns 404."""
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/mdb-99999/availability",
        headers=authHeaders,
    )
    assert response.status_code == 404


def test_gtfs_feed_availability_from_after_to_returns_422(client: TestClient):
    """from > to returns 422."""
    response = client.request(
        "GET",
        f"/v1/gtfs_feeds/{AVAILABILITY_FEED_ID}/availability",
        headers=authHeaders,
        params={"from": "2025-06-01T00:00:00Z", "to": "2025-01-01T00:00:00Z"},
    )
    assert response.status_code == 422


def test_gtfs_feed_availability_invalid_date_returns_422(client: TestClient):
    """Invalid ISO date returns 422."""
    response = client.request(
        "GET",
        f"/v1/gtfs_feeds/{AVAILABILITY_FEED_ID}/availability",
        headers=authHeaders,
        params={"from": "not-a-date"},
    )
    assert response.status_code == 422
