# coding: utf-8
import contextlib
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from feeds_gen.models.search_feeds200_response import SearchFeeds200Response  # noqa: F401
from shared.database.database import Database
from shared.database_gen.sqlacodegen_models import (
    FeedReliabilitySeal,
    Gtfsfeed,
    SealCriterion,
    t_feedsearch,
)
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
    [("gtfs", 10), ("not_valid_gtfs", 0), ("gtfs_rt", 3), ("gtfs,gtfs_rt", 13)],
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
            assert result.data_type in data_type.split(",")


@pytest.mark.parametrize(
    "status, expected_results_total",
    [
        ("active", 12),
        ("not_valid_status", 0),
        ("inactive", 2),
        ("active,inactive", 14),
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
    if expected_results_total > 0:
        for result in response_body.results:
            assert result.status in status


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


@pytest.mark.parametrize(
    "values",
    [
        {"search_query": "éèàçíóúč", "expected_ids": ["mdb-1562"]},
        {"search_query": "eeaciouc", "expected_ids": ["mdb-1562"]},
        {"search_query": "ŘŤÜî", "expected_ids": ["mdb-1562"]},
        {"search_query": "rtui", "expected_ids": ["mdb-1562"]},
    ],
    ids=[
        "Search query with accents and special characters against a provider",
        "Search query with the normalized version of the accents against a provider",
        "Search query with accents and special characters against the feed name",
        "Search query with the normalized version of the accents against the feed name",
    ],
)
def test_search_feeds_filter_accents(client: TestClient, values: dict):
    """
    Retrieve feeds with accents in the provider name and/or feed name.
    """
    params = [
        ("limit", 100),
        ("offset", 0),
        ("search_query", values["search_query"]),
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

    assert len(response_body.results) == len(values["expected_ids"])
    assert response_body.total == len(values["expected_ids"])
    assert all(result.id in values["expected_ids"] for result in response_body.results)


@pytest.mark.parametrize(
    "values",
    [
        {"official": True, "expected_count": 2},
        {"official": False, "expected_count": 14},
        {"official": None, "expected_count": 16},
    ],
    ids=[
        "Official",
        "Not official",
        "Not specified",
    ],
)
def test_search_filter_by_official_status(client: TestClient, values: dict):
    """
    Retrieve feeds with the official status.
    """
    params = None
    if values["official"] is not None:
        params = [
            ("is_official", str(values["official"]).lower()),
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
    # Parse the response body into a Python object
    response_body = SearchFeeds200Response.parse_obj(response.json())
    expected_count = values["expected_count"]
    assert (
        response_body.total == expected_count
    ), f"There should be {expected_count} feeds for official={values['official']}"


@pytest.mark.parametrize(
    "values",
    [
        {"versions": "1.0", "expected_count": 0},
        {"versions": "2.3,3.0", "expected_count": 2},
        {"versions": "3.0", "expected_count": 1},
        {"versions": "2.3", "expected_count": 2},
        {"versions": None, "expected_count": 16},
    ],
    ids=[
        "Version 1.0",
        "Versions 2.3 and 3.0",
        "Version 3.0",
        "Version 2.3",
        "No version specified",
    ],
)
def test_search_filter_by_versions(client: TestClient, values: dict):
    """
    Retrieve feeds with the version.
    """
    params = None
    if values["versions"] is not None:
        params = [
            ("version", values["versions"]),
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
    # Parse the response body into a Python object
    response_body = SearchFeeds200Response.parse_obj(response.json())
    expected_count = values["expected_count"]
    assert (
        response_body.total == expected_count
    ), f"There should be {expected_count} feeds for versions={values['versions']}"


@pytest.mark.parametrize(
    "values",
    [
        {"license_ids": "CC BY 4.0", "expected_count": 1},
        {"license_ids": "ODbL-1.0", "expected_count": 1},
        {"license_ids": "ODbL-1.0,CC BY 4.0", "expected_count": 2},
        {"license_ids": "", "expected_count": 16},
    ],
    ids=[
        "License ID CC BY 4.0",
        "License ID ODbL-1.0",
        "License IDs ODbL-1.0 and CC BY 4.0",
        "No license IDs specified",
    ],
)
def test_search_filter_by_license_ids(client: TestClient, values: dict):
    """
    Retrieve feeds that contain specific license IDs.
    """
    params = None
    if values["license_ids"] is not None:
        params = [
            ("license_ids", values["license_ids"]),
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
    expected_count = values["expected_count"]
    assert (
        response_body.total == expected_count
    ), f"There should be {expected_count} feeds for license_ids={values['license_ids']}"


@pytest.mark.parametrize(
    "values",
    [
        {"feature": "", "expected_count": 16},
        {"feature": "Bike Allowed", "expected_count": 2},
        {"feature": "Stops Wheelchair Accessibility", "expected_count": 0},
    ],
    ids=[
        "All",
        "Bike Allowed",
        "Stops Wheelchair Accessibility",
    ],
)
def test_search_filter_by_feature(client: TestClient, values: dict):
    """
    Retrieve feeds that contain specific features.
    """
    params = None
    if values["feature"] is not None:
        params = [
            ("feature", values["feature"]),
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
    response_body = SearchFeeds200Response.model_validate(response.json())
    expected_count = values["expected_count"]
    assert (
        response_body.total == expected_count
    ), f"There should be {expected_count} feeds with feature={values['feature']}"

    # Verify all returned feeds have at least one of the requested features
    if values["feature"] and expected_count > 0:
        requested_features = set(values["feature"].split(","))
        for result in response_body.results:
            features = result.latest_dataset.validation_report.features
            # Check that at least one of the feed's features is in the requested features
            assert requested_features.intersection(features), (
                f"Feed {result.id} with features {features} does not match " f"requested features {requested_features}"
            )


@pytest.mark.parametrize(
    "values",
    [
        {"license_tags": "family:ODC", "expected_count": 1},
        {"license_tags": "license:open-data-commons", "expected_count": 1},
        # AND semantics: feed must contain ALL requested tags
        {"license_tags": "family:ODC,license:open-data-commons", "expected_count": 1},
        {"license_tags": "nonexistent:tag", "expected_count": 0},
        {"license_tags": "license:open-data-commons,nonexistent:tag", "expected_count": 0},
        {"license_tags": "", "expected_count": 16},
    ],
    ids=[
        "Filter by single tag family:ODC",
        "Filter by single tag license:open-data-commons",
        "Filter by multiple tags (AND semantics)",
        "No feed matches nonexistent tag",
        "Mixed existing and nonexistent tag (AND semantics)",
        "No filter returns all feeds",
    ],
)
def test_search_filter_by_license_tags(client: TestClient, values: dict):
    """Retrieve feeds that have licenses associated with specific license tag IDs.

    The ``license_tags`` parameter accepts a comma-separated list of tag IDs.
    The filter uses AND semantics: the feed's ``license_tags`` array must
    contain **all** of the requested tags for the feed to be returned.
    """

    params = None
    if values["license_tags"]:
        params = [("license_tags", values["license_tags"])]

    headers = {"Authentication": "special-key"}
    response = client.request("GET", "/v1/search", headers=headers, params=params)

    assert response.status_code == 200

    response_body = SearchFeeds200Response.model_validate(response.json())
    expected_count = values["expected_count"]
    assert (
        response_body.total == expected_count
    ), f"There should be {expected_count} feeds for license_tags={values['license_tags']}"


def test_search_result_contains_license_tags(client: TestClient):
    """
    Verify that the search results include license_tags for feeds with license tags.
    """
    params = [
        ("feed_id", "mdb-70"),
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
    assert response.status_code == 200
    response_body = SearchFeeds200Response.parse_obj(response.json())
    assert response_body.total == 1
    result = response_body.results[0]
    assert result.source_info.license_tags is not None
    assert "family:ODC" in result.source_info.license_tags[0]
    assert "license:open-data-commons" in result.source_info.license_tags[1]


# ---- Seal of Reliability filter ----

SEARCH_HEADERS = {"Authentication": "special-key"}


@contextlib.contextmanager
def _feed_with_seal(feed_stable_id: str):
    """Give one feed the seal for the duration of a test, refreshing the search view either way.

    Search reads the `feedsearch` materialized view, so the view has to be rebuilt for the seal to
    be visible - and rebuilt again on the way out so the rest of the package sees the original data.
    Writes go through `__table__` (a Core insert) so the seal row's surrogate `id` falls back to its
    `gen_random_uuid()` default.
    """
    db = Database()
    with db.start_db_session() as session:
        feed_id = session.query(Gtfsfeed).filter(Gtfsfeed.stable_id == feed_stable_id).first().id
        session.execute(
            FeedReliabilitySeal.__table__.insert().values(
                feed_id=feed_id, has_seal=True, seal_earned_at=datetime.now(timezone.utc)
            )
        )
        session.execute(
            SealCriterion.__table__.insert().values(
                feed_id=feed_id,
                criterion="official",
                observed_status="pass",
                confirmed_status="pass",
                evaluated_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
        session.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {t_feedsearch.name}"))
        session.commit()
    try:
        yield
    finally:
        with db.start_db_session() as session:
            session.execute(SealCriterion.__table__.delete().where(SealCriterion.__table__.c.feed_id == feed_id))
            session.execute(
                FeedReliabilitySeal.__table__.delete().where(FeedReliabilitySeal.__table__.c.feed_id == feed_id)
            )
            session.commit()
            session.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {t_feedsearch.name}"))
            session.commit()


def _search(client: TestClient, params):
    return client.request("GET", "/v1/search", headers=SEARCH_HEADERS, params=params)


def _grant_seal_filter(mocker):
    """Give the caller the `isSealFilterEnabled` flag, without seeding the users DB."""
    mocker.patch("feeds.impl.search_api_impl.get_request_context", return_value={"user_id": "some-user-uuid"})
    mocker.patch("feeds.impl.search_api_impl.feature_flag_enabled", return_value=True)


def test_search_has_seal_requires_permission(client: TestClient):
    """Filtering by seal status is gated, and refused rather than silently ignored.

    Silently dropping the filter would answer "feeds with the seal" with feeds that lack it. The
    caller here has no user id, so there is nobody to hold the flag.
    """
    response = _search(client, [("has_seal", "true")])

    assert response.status_code == 403
    assert "selected users" in response.json()["detail"]


def test_search_has_seal_denied_without_the_feature_flag(client: TestClient, mocker):
    """An identified user without `isSealFilterEnabled` is still refused."""
    mocker.patch("feeds.impl.search_api_impl.get_request_context", return_value={"user_id": "some-user-uuid"})
    mocker.patch("feeds.impl.search_api_impl.feature_flag_enabled", return_value=False)

    response = _search(client, [("has_seal", "true")])

    assert response.status_code == 403


def test_search_without_has_seal_needs_no_permission(client: TestClient):
    """The gate only applies when the parameter is supplied - ordinary search is unaffected."""
    response = _search(client, [("limit", 1)])

    assert response.status_code == 200


def test_search_has_seal_true(client: TestClient, mocker):
    """`has_seal=true` returns only the feed holding the seal."""
    _grant_seal_filter(mocker)
    feed_stable_id = TEST_GTFS_FEED_STABLE_IDS[0]

    with _feed_with_seal(feed_stable_id):
        response = _search(client, [("limit", 100), ("has_seal", "true")])

        assert response.status_code == 200
        response_body = SearchFeeds200Response.parse_obj(response.json())
        assert [result.id for result in response_body.results] == [feed_stable_id]
        assert response_body.results[0].reliability_seal.has_seal is True
        assert response_body.results[0].reliability_seal.on_probation is False


def test_search_has_seal_false_excludes_sealed_feed(client: TestClient, mocker):
    """`has_seal=false` covers feeds without a seal row as well as those explicitly without it."""
    _grant_seal_filter(mocker)
    feed_stable_id = TEST_GTFS_FEED_STABLE_IDS[0]

    with _feed_with_seal(feed_stable_id):
        unfiltered = SearchFeeds200Response.parse_obj(_search(client, [("limit", 100)]).json())
        response = _search(client, [("limit", 100), ("has_seal", "false")])

        assert response.status_code == 200
        response_body = SearchFeeds200Response.parse_obj(response.json())
        assert response_body.total == unfiltered.total - 1
        assert feed_stable_id not in [result.id for result in response_body.results]
