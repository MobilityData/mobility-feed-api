# coding: utf-8
import pytest
from fastapi.testclient import TestClient

from feeds_gen.models.search_feeds200_response import SearchFeeds200Response  # noqa: F401
from tests.test_utils.database import TEST_GTFS_FEED_STABLE_IDS, TEST_GTFS_RT_FEED_STABLE_ID


@pytest.mark.parametrize(
    "search_query",
    [
        # Provider
        "MobilityDataTest provider",
        # Provider using a lexically similar word
        "MobilityDataTest PROVIDE",
        # Feed name
        "MobilityDataTest Feed name",
        # Feed name using a lexically similar word
        "MobilityDataTest feedING",
    ],
)
def test_search_feeds_all_feeds(client: TestClient, search_query: str):
    """
    Retrieve all feeds with a search query using provider or feed name.
    """
    params = [("limit", 100), ("offset", 0), ("feed_id", ""), ("data_type", ""), ("search_query", search_query)]
    headers = {
        "Authentication": "special-key",
    }
    response = client.request(
        "GET",
        "/v1/search",
        headers=headers,
        params=params,
    )

    # Assert the status code of the HTTP response
    assert response.status_code == 200

    # Parse the response body into a Python object
    response_body = SearchFeeds200Response.parse_obj(response.json())

    assert response_body.total == len(TEST_GTFS_FEED_STABLE_IDS)
    assert len(response_body.results) == len(TEST_GTFS_FEED_STABLE_IDS)


@pytest.mark.parametrize(
    "search_query",
    [
        # Provider
        "MobilityDataTest provider",
        # Provider using a lexically similar word
        "MobilityDataTest PROVIDE",
        # Feed name
        "MobilityDataTest Feed name",
        # Feed name using a lexically similar word
        "MobilityDataTest feedING",
    ],
)
def test_search_feeds_all_feeds_with_limit(client: TestClient, search_query: str):
    """
    Retrieve 2 feeds using limit with a search query using provider or feed name.
    """
    params = [("limit", 2), ("offset", 0), ("feed_id", ""), ("data_type", ""), ("search_query", search_query)]
    headers = {
        "Authentication": "special-key",
    }
    response = client.request(
        "GET",
        "/v1/search",
        headers=headers,
        params=params,
    )

    # Assert the status code of the HTTP response
    assert response.status_code == 200

    # Parse the response body into a Python object
    response_body = SearchFeeds200Response.parse_obj(response.json())

    assert response_body.total == len(TEST_GTFS_FEED_STABLE_IDS)
    assert len(response_body.results) == 2


@pytest.mark.parametrize(
    "search_query",
    [
        # Provider
        f"{TEST_GTFS_FEED_STABLE_IDS[0]}-MobilityDataTest provider",
        # Provider using a lexically similar word
        f"{TEST_GTFS_FEED_STABLE_IDS[0]}-MobilityDataTest provide",
        # Feed name
        f"{TEST_GTFS_FEED_STABLE_IDS[0]}-MobilityDataTest Feed name",
        # Feed name using a lexically similar word
        f"{TEST_GTFS_FEED_STABLE_IDS[0]}-MobilityDataTest Feeding name",
    ],
)
def test_search_feeds_provider_one_feed(client: TestClient, search_query: str):
    """
    Retrieve a single feed with a search query using provider or feed name.
    """
    params = [
        ("limit", 10),
        ("offset", 0),
        ("status", ""),
        ("feed_id", ""),
        ("data_type", ""),
        ("search_query", search_query),
    ]
    headers = {
        "Authentication": "special-key",
    }
    response = client.request(
        "GET",
        "/v1/search",
        headers=headers,
        params=params,
    )

    # Assert the status code of the HTTP response
    assert response.status_code == 200

    # Parse the response body into a Python object
    response_body = SearchFeeds200Response.parse_obj(response.json())

    assert response_body.total == 1
    assert response_body.results[0].id == TEST_GTFS_FEED_STABLE_IDS[0]
    assert response_body.results[0].provider == f"{TEST_GTFS_FEED_STABLE_IDS[0]}-MobilityDataTest provider"


@pytest.mark.parametrize(
    "data_type, expected_results_total",
    [
        ("gtfs", 7),
        ("not_valid_gtfs", 0),
        ("gtfs_rt", 2),
    ],
)
def test_search_feeds_filter_data_type(client: TestClient, data_type: str, expected_results_total: int):
    """
    Retrieve feeds with a specific data type.
    """
    params = [
        ("limit", 100),
        ("offset", 0),
        ("status", ""),
        ("feed_id", ""),
        ("data_type", data_type),
        ("search_query", ""),
    ]
    headers = {
        "Authentication": "special-key",
    }
    response = client.request(
        "GET",
        "/v1/search",
        headers=headers,
        params=params,
    )

    # Assert the status code of the HTTP response
    assert response.status_code == 200

    # Parse the response body into a Python object
    response_body = SearchFeeds200Response.parse_obj(response.json())

    assert response_body.total == expected_results_total
    assert len(response_body.results) == expected_results_total
    if expected_results_total > 1:
        for result in response_body.results:
            assert result.data_type == data_type


@pytest.mark.parametrize(
    "status, expected_results_total",
    [
        ("active", 9),  # 7 GTFS feeds and 2 GTFS-rt feeds
        ("not_valid_status", 0),
        ("inactive", 0),
    ],
)
def test_search_feeds_filter_status(client: TestClient, status: str, expected_results_total: int):
    """
    Retrieve feeds with a specific status.
    """
    params = [
        ("limit", 100),
        ("offset", 0),
        ("status", status),
        ("feed_id", ""),
        ("data_type", ""),
        ("search_query", ""),
    ]
    headers = {
        "Authentication": "special-key",
    }
    response = client.request(
        "GET",
        "/v1/search",
        headers=headers,
        params=params,
    )

    # Assert the status code of the HTTP response
    assert response.status_code == 200

    # Parse the response body into a Python object
    response_body = SearchFeeds200Response.parse_obj(response.json())

    assert response_body.total == expected_results_total
    assert len(response_body.results) == expected_results_total
    if expected_results_total > 1:
        for result in response_body.results:
            assert result.status == status


@pytest.mark.parametrize(
    "feed_id, expected_results_total",
    [
        (TEST_GTFS_FEED_STABLE_IDS[0], 1),
        (TEST_GTFS_FEED_STABLE_IDS[1], 1),
        ("this_is_not_valid", 0),
    ],
)
def test_search_feeds_filter_feed_id(client: TestClient, feed_id: str, expected_results_total: int):
    """
    Retrieve feeds with a specific feed ID.
    """
    params = [
        ("limit", 100),
        ("offset", 0),
        ("status", ""),
        ("feed_id", feed_id),
        ("data_type", ""),
        ("search_query", ""),
    ]
    headers = {
        "Authentication": "special-key",
    }
    response = client.request(
        "GET",
        "/v1/search",
        headers=headers,
        params=params,
    )

    # Assert the status code of the HTTP response
    assert response.status_code == 200

    # Parse the response body into a Python object
    response_body = SearchFeeds200Response.parse_obj(response.json())

    assert response_body.total == expected_results_total
    assert len(response_body.results) == expected_results_total
    if expected_results_total > 1:
        for result in response_body.results:
            assert result.id == feed_id


@pytest.mark.parametrize(
    "feed_id, status, data_type, search_query, expected_results_total",
    [
        (TEST_GTFS_FEED_STABLE_IDS[0], "active", "gtfs", "MobilityDataTest", 1),
        (TEST_GTFS_FEED_STABLE_IDS[0], "deprecated", "gtfs", "MobilityDataTest", 0),
        (TEST_GTFS_FEED_STABLE_IDS[0], "active", "gtfs_rt", "MobilityDataTest", 0),  # GTFS-rt is not the right type
        ("", "active", "gtfs", "MobilityDataTest", len(TEST_GTFS_FEED_STABLE_IDS)),
        (TEST_GTFS_FEED_STABLE_IDS[0], "", "gtfs", "MobilityDataTest", 1),
        (TEST_GTFS_RT_FEED_STABLE_ID, "active", "gtfs_rt", "", 1),
    ],
)
def test_search_feeds_filter_combine_filters_and_query(
    client: TestClient, feed_id: str, status: str, data_type: str, search_query: str, expected_results_total: int
):
    """
    Retrieve feeds combining feed ID, status, data type, and search query.
    """
    params = [
        ("limit", 100),
        ("offset", 0),
        ("status", status),
        ("feed_id", feed_id),
        ("data_type", data_type),
        ("search_query", search_query),
    ]
    headers = {
        "Authentication": "special-key",
    }
    response = client.request(
        "GET",
        "/v1/search",
        headers=headers,
        params=params,
    )

    # Assert the status code of the HTTP response
    assert response.status_code == 200

    # Parse the response body into a Python object
    response_body = SearchFeeds200Response.parse_obj(response.json())

    assert response_body.total == expected_results_total
    assert len(response_body.results) == expected_results_total
    if expected_results_total > 1:
        for result in response_body.results:
            if feed_id:
                assert result.id == feed_id
            if status:
                assert result.status == status
            if data_type:
                assert result.data_type == data_type


def test_search_feeds_filter_reference_id(client: TestClient):
    """
    Retrieve feeds combining feed ID, status, data type, and search query.
    """
    params = [
        ("limit", 100),
        ("offset", 0),
        ("feed_id", TEST_GTFS_RT_FEED_STABLE_ID),
    ]
    headers = {
        "Authentication": "special-key",
    }
    response = client.request(
        "GET",
        "/v1/search",
        headers=headers,
        params=params,
    )

    # Assert the status code of the HTTP response
    assert response.status_code == 200

    # Parse the response body into a Python object
    response_body = SearchFeeds200Response.parse_obj(response.json())

    assert response_body.total == 1
    assert len(response_body.results) == 1
    assert response_body.results[0].id == TEST_GTFS_RT_FEED_STABLE_ID
    assert response_body.results[0].data_type == "gtfs_rt"
    assert response_body.results[0].status == "active"
    assert len(response_body.results[0].feed_references) == 1
    assert response_body.results[0].feed_references[0] == TEST_GTFS_FEED_STABLE_IDS[0]
