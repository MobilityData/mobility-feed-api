import pytest
from fastapi.testclient import TestClient

from feeds.impl.error_handling import (
    location_directory_country_not_in_continent,
    location_directory_not_found,
    location_directory_parent_required,
)
from feeds_gen.models.location_directory_feeds_response import LocationDirectoryFeedsResponse
from feeds_gen.models.location_directory_response import LocationDirectoryResponse

HEADERS = {"Authentication": "special-key"}


def _directory(client: TestClient, **params):
    return client.get("/v1/locations/directory", headers=HEADERS, params=params)


def _directory_feeds(client: TestClient, **params):
    return client.get("/v1/locations/directory/feeds", headers=HEADERS, params=params)


def _counts(node) -> tuple:
    counts = node.feed_counts
    return counts.gtfs, counts.gtfs_rt, counts.gbfs, counts.total


def _children(response: LocationDirectoryResponse) -> list:
    return [(child.slug, child.name, _counts(child)) for child in response.children]


def test_root_lists_continents_with_counts(client: TestClient):
    response = _directory(client)
    assert response.status_code == 200
    body = LocationDirectoryResponse.model_validate(response.json())

    assert body.level == "root"
    assert body.breadcrumb == []
    # Ten feeds in scope: deprecated (ld-6), wip (ld-7) and unmapped country (ld-12) feeds are left out.
    assert _counts(body) == (8, 1, 1, 10)
    assert _children(body) == [
        ("europe", "Europe", (2, 0, 0, 2)),
        ("north-america", "North America", (6, 1, 1, 8)),
    ]
    assert [child.code for child in body.children] == ["EU", "NA"]
    assert all(child.level == "continent" for child in body.children)


def test_continent_lists_countries_sorted_by_name(client: TestClient):
    body = LocationDirectoryResponse.model_validate(_directory(client, continent="europe").json())

    assert body.level == "continent"
    assert [(node.slug, node.code, node.name) for node in body.breadcrumb] == [("europe", "EU", "Europe")]
    # XK is a user-assigned code, mapped to Europe.
    assert _children(body) == [
        ("fr", "France", (1, 0, 0, 1)),
        ("xk", "Kosovo", (1, 0, 0, 1)),
    ]
    assert [child.code for child in body.children] == ["FR", "XK"]


def test_country_rolls_up_and_collapses_subdivision_spellings(client: TestClient):
    # The country code is case-insensitive.
    response = _directory(client, continent="north-america", country_code="Ca")
    assert response.status_code == 200
    body = LocationDirectoryResponse.model_validate(response.json())

    assert body.level == "country"
    assert [(node.level, node.slug, node.name, _counts(node)) for node in body.breadcrumb] == [
        ("continent", "north-america", "North America", (6, 1, 1, 8)),
        ("country", "ca", "Canada", (6, 1, 1, 8)),
    ]
    # The cross-border feed ld-9 counts toward both Canada and the United States, but once toward North America.
    assert _counts(body) == (6, 1, 1, 8)
    # "Québec" and "Quebec" are a single node, displayed with the most frequent spelling. The municipality
    # declared without a subdivision (Whistler) counts toward Canada but produces no subdivision.
    assert _children(body) == [
        ("ontario", "Ontario", (1, 0, 0, 1)),
        ("quebec", "Québec", (2, 1, 1, 4)),
    ]
    assert all(child.code is None for child in body.children)


def test_subdivision_counts_feed_once_with_several_locations(client: TestClient):
    body = LocationDirectoryResponse.model_validate(
        _directory(client, continent="north-america", country_code="ca", subdivision="quebec").json()
    )

    assert body.level == "subdivision"
    assert [node.slug for node in body.breadcrumb] == ["north-america", "ca", "quebec"]
    assert _counts(body) == (2, 1, 1, 4)
    # ld-3 is located in both Montréal and Laval: it counts once toward Québec and once in each municipality.
    assert _children(body) == [
        ("laval", "Laval", (0, 1, 0, 1)),
        ("montreal", "Montréal", (1, 1, 0, 2)),
    ]


def test_municipality_has_no_children(client: TestClient):
    body = LocationDirectoryResponse.model_validate(
        _directory(
            client, continent="north-america", country_code="ca", subdivision="quebec", municipality="montreal"
        ).json()
    )

    assert body.level == "municipality"
    assert [(node.level, node.slug, node.name) for node in body.breadcrumb] == [
        ("continent", "north-america", "North America"),
        ("country", "ca", "Canada"),
        ("subdivision", "quebec", "Québec"),
        ("municipality", "montreal", "Montréal"),
    ]
    # The deprecated (ld-6) and wip (ld-7) feeds located in Montréal are not counted.
    assert _counts(body) == (1, 1, 0, 2)
    assert body.children == []


def test_wip_feeds_are_visible_to_unrestricted_users(client: TestClient, monkeypatch):
    monkeypatch.setattr("feeds.impl.location_directory.is_user_email_restricted", lambda: False)
    body = LocationDirectoryResponse.model_validate(
        _directory(
            client, continent="north-america", country_code="ca", subdivision="quebec", municipality="montreal"
        ).json()
    )
    # ld-7 (wip) is now counted; ld-6 (deprecated) still is not.
    assert _counts(body) == (2, 1, 0, 3)


@pytest.mark.parametrize(
    "params, child, parent",
    [
        ({"country_code": "ca"}, "country_code", "continent"),
        ({"continent": "north-america", "subdivision": "quebec"}, "subdivision", "country_code"),
        (
            {"continent": "north-america", "country_code": "ca", "municipality": "montreal"},
            "municipality",
            "subdivision",
        ),
    ],
)
@pytest.mark.parametrize("endpoint", [_directory, _directory_feeds])
def test_parameter_without_parent_is_rejected(client: TestClient, endpoint, params, child, parent):
    response = endpoint(client, **params)
    assert response.status_code == 400
    assert response.json()["detail"] == location_directory_parent_required.format(child, parent)


@pytest.mark.parametrize("country_code", ["ca", "zz"])
@pytest.mark.parametrize("endpoint", [_directory, _directory_feeds])
def test_country_not_in_continent_is_rejected(client: TestClient, endpoint, country_code):
    response = endpoint(client, continent="europe", country_code=country_code)
    assert response.status_code == 400
    assert response.json()["detail"] == location_directory_country_not_in_continent.format(
        country_code.upper(), "europe"
    )


@pytest.mark.parametrize(
    "params",
    [
        {"continent": "atlantis"},
        # A known continent without any feed.
        {"continent": "antarctica"},
        # A valid country of the continent without any feed.
        {"continent": "north-america", "country_code": "mx"},
        {"continent": "north-america", "country_code": "ca", "subdivision": "atlantis"},
        {"continent": "north-america", "country_code": "ca", "subdivision": "quebec", "municipality": "toronto"},
    ],
)
def test_unknown_node_is_not_found(client: TestClient, params):
    response = _directory(client, **params)
    assert response.status_code == 404
    assert response.json()["detail"] == location_directory_not_found

    feeds_response = _directory_feeds(client, **params)
    assert feeds_response.status_code == 200
    assert feeds_response.json() == {"total": 0, "results": []}


def test_feeds_sorted_by_relevance(client: TestClient):
    response = _directory_feeds(client, continent="north-america", country_code="ca", subdivision="quebec")
    assert response.status_code == 200
    body = LocationDirectoryFeedsResponse.model_validate(response.json())

    assert body.total == 4
    # Located in Québec (depth 2) first, then in a municipality of Québec (depth 3); provider breaks the ties.
    assert [feed.id for feed in body.results] == ["ld-1", "ld-4", "ld-3", "ld-2"]
    assert [feed.data_type for feed in body.results] == ["gtfs", "gbfs", "gtfs_rt", "gtfs"]


def test_feeds_country_level_ordering(client: TestClient):
    body = LocationDirectoryFeedsResponse.model_validate(
        _directory_feeds(client, continent="north-america", country_code="ca").json()
    )

    assert body.total == 8
    # Country-only locations first (ld-5, ld-13), then subdivisions (ld-1, ld-4), then municipalities, including
    # the municipality declared without a subdivision (ld-8).
    assert [feed.id for feed in body.results] == ["ld-5", "ld-13", "ld-1", "ld-4", "ld-3", "ld-2", "ld-8", "ld-9"]


def test_feeds_continent_level_ranks_by_most_relevant_location(client: TestClient):
    body = LocationDirectoryFeedsResponse.model_validate(
        _directory_feeds(client, continent="north-america", limit=3).json()
    )
    assert body.total == 8
    assert [feed.id for feed in body.results] == ["ld-5", "ld-13", "ld-1"]


def test_feeds_pagination(client: TestClient):
    body = LocationDirectoryFeedsResponse.model_validate(
        _directory_feeds(client, continent="north-america", country_code="ca", limit=3, offset=2).json()
    )
    assert body.total == 8
    assert [feed.id for feed in body.results] == ["ld-1", "ld-4", "ld-3"]

    last_page = LocationDirectoryFeedsResponse.model_validate(
        _directory_feeds(client, continent="north-america", country_code="ca", limit=3, offset=6).json()
    )
    assert last_page.total == 8
    assert [feed.id for feed in last_page.results] == ["ld-8", "ld-9"]


def test_feeds_default_and_maximum_limit(client: TestClient):
    body = LocationDirectoryFeedsResponse.model_validate(_directory_feeds(client).json())
    # No parameter: every feed in the directory.
    assert body.total == 10
    assert len(body.results) == 10

    assert _directory_feeds(client, limit=101).status_code == 422


def test_feeds_use_search_result_shape(client: TestClient):
    body = _directory_feeds(
        client, continent="north-america", country_code="ca", subdivision="quebec", municipality="montreal"
    ).json()

    assert [feed["id"] for feed in body["results"]] == ["ld-3", "ld-2"]
    feed = body["results"][1]
    assert feed["provider"] == "B Provider"
    assert feed["feed_name"] == "Montreal metro"
    assert feed["status"] == "active"
    assert {"country_code": "CA", "subdivision_name": "Québec", "municipality": "Montréal"}.items() <= feed[
        "locations"
    ][0].items()


def test_feeds_exclude_deprecated_feeds(client: TestClient):
    body = LocationDirectoryFeedsResponse.model_validate(_directory_feeds(client, limit=100).json())
    feed_ids = {feed.id for feed in body.results}
    assert "ld-6" not in feed_ids  # deprecated
    assert "ld-7" not in feed_ids  # wip
    assert "ld-12" not in feed_ids  # unmapped country code
