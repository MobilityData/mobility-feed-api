import pytest
from fastapi.testclient import TestClient

from feeds.impl.error_handling import (
    location_directory_country_not_in_continent,
    location_directory_not_found,
    location_directory_parent_required,
    search_location_sort_requires_location,
    search_sort_unsupported,
)
from feeds_gen.models.location_directory_response import LocationDirectoryResponse
from feeds_gen.models.search_feeds200_response import SearchFeeds200Response

HEADERS = {"Authentication": "special-key"}
# The statuses counted by the directory, passed to /v1/search to list the same feeds.
DIRECTORY_STATUSES = "active,inactive,development,future"


def _directory(client: TestClient, **params):
    return client.get("/v1/locations/directory", headers=HEADERS, params=params)


def _search(client: TestClient, **params):
    return client.get("/v1/search", headers=HEADERS, params=params)


def _directory_feeds(client: TestClient, **params):
    """The feeds of a directory node, as listed by the web app: /v1/search with the directory statuses."""
    return _search(client, status=DIRECTORY_STATUSES, sort="location", **params)


def _feed_ids(response) -> list:
    return [feed.id for feed in SearchFeeds200Response.model_validate(response.json()).results]


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
        ("france", "France", (1, 0, 0, 1)),
        ("kosovo", "Kosovo", (1, 0, 0, 1)),
    ]
    assert [child.code for child in body.children] == ["FR", "XK"]


def test_country_rolls_up_and_collapses_subdivision_spellings(client: TestClient):
    # The country slug is case-insensitive.
    response = _directory(client, continent="north-america", country="Canada")
    assert response.status_code == 200
    body = LocationDirectoryResponse.model_validate(response.json())

    assert body.level == "country"
    assert [(node.level, node.slug, node.name, _counts(node)) for node in body.breadcrumb] == [
        ("continent", "north-america", "North America", (6, 1, 1, 8)),
        ("country", "canada", "Canada", (6, 1, 1, 8)),
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
        _directory(client, continent="north-america", country="canada", subdivision="quebec").json()
    )

    assert body.level == "subdivision"
    assert [node.slug for node in body.breadcrumb] == ["north-america", "canada", "quebec"]
    assert _counts(body) == (2, 1, 1, 4)
    # ld-3 is located in both Montréal and Laval: it counts once toward Québec and once in each municipality.
    assert _children(body) == [
        ("laval", "Laval", (0, 1, 0, 1)),
        ("montreal", "Montréal", (1, 1, 0, 2)),
    ]


def test_municipality_has_no_children(client: TestClient):
    body = LocationDirectoryResponse.model_validate(
        _directory(
            client, continent="north-america", country="canada", subdivision="quebec", municipality="montreal"
        ).json()
    )

    assert body.level == "municipality"
    assert [(node.level, node.slug, node.name) for node in body.breadcrumb] == [
        ("continent", "north-america", "North America"),
        ("country", "canada", "Canada"),
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
            client, continent="north-america", country="canada", subdivision="quebec", municipality="montreal"
        ).json()
    )
    # ld-7 (wip) is now counted; ld-6 (deprecated) still is not.
    assert _counts(body) == (2, 1, 0, 3)


@pytest.mark.parametrize(
    "params, child, parent",
    [
        ({"country": "canada"}, "country", "continent"),
        ({"continent": "north-america", "subdivision": "quebec"}, "subdivision", "country"),
        (
            {"continent": "north-america", "country": "canada", "municipality": "montreal"},
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


@pytest.mark.parametrize("endpoint", [_directory, _directory_feeds])
def test_country_not_in_continent_is_rejected(client: TestClient, endpoint):
    response = endpoint(client, continent="europe", country="Canada")
    assert response.status_code == 400
    assert response.json()["detail"] == location_directory_country_not_in_continent.format("Canada", "europe")


@pytest.mark.parametrize(
    "params",
    [
        {"continent": "atlantis"},
        # A known continent without any feed.
        {"continent": "antarctica"},
        # A valid country of the continent without any feed.
        {"continent": "north-america", "country": "mexico"},
        # Unknown country slugs, ISO codes included: countries are identified by their name only.
        {"continent": "north-america", "country": "atlantis"},
        {"continent": "north-america", "country": "ca"},
        {"continent": "north-america", "country": "canada", "subdivision": "atlantis"},
        {"continent": "north-america", "country": "canada", "subdivision": "quebec", "municipality": "toronto"},
    ],
)
def test_unknown_node_is_not_found(client: TestClient, params):
    response = _directory(client, **params)
    assert response.status_code == 404
    assert response.json()["detail"] == location_directory_not_found

    feeds_response = _directory_feeds(client, **params)
    assert feeds_response.status_code == 200
    assert feeds_response.json() == {"total": 0, "results": []}


def test_search_feeds_sorted_by_location_relevance(client: TestClient):
    response = _directory_feeds(client, continent="north-america", country="canada", subdivision="quebec")
    assert response.status_code == 200
    body = SearchFeeds200Response.model_validate(response.json())

    # The total matches the directory counts of the node.
    assert body.total == 4
    # Located in Québec (depth 2) first, then in a municipality of Québec (depth 3); provider breaks the ties.
    assert [feed.id for feed in body.results] == ["ld-1", "ld-4", "ld-3", "ld-2"]
    assert [feed.data_type for feed in body.results] == ["gtfs", "gbfs", "gtfs_rt", "gtfs"]


def test_search_feeds_country_level_ordering(client: TestClient):
    body = SearchFeeds200Response.model_validate(
        _directory_feeds(client, continent="north-america", country="canada").json()
    )

    assert body.total == 8
    # Country-only locations first (ld-5, ld-13), then subdivisions (ld-1, ld-4), then municipalities, including
    # the municipality declared without a subdivision (ld-8).
    assert [feed.id for feed in body.results] == ["ld-5", "ld-13", "ld-1", "ld-4", "ld-3", "ld-2", "ld-8", "ld-9"]


def test_search_feeds_continent_level_ranks_by_most_relevant_location(client: TestClient):
    body = SearchFeeds200Response.model_validate(_directory_feeds(client, continent="north-america", limit=3).json())
    assert body.total == 8
    assert [feed.id for feed in body.results] == ["ld-5", "ld-13", "ld-1"]


def test_search_feeds_location_pagination(client: TestClient):
    response = _directory_feeds(client, continent="north-america", country="canada", limit=3, offset=2)
    assert SearchFeeds200Response.model_validate(response.json()).total == 8
    assert _feed_ids(response) == ["ld-1", "ld-4", "ld-3"]

    last_page = _directory_feeds(client, continent="north-america", country="canada", limit=3, offset=6)
    assert _feed_ids(last_page) == ["ld-8", "ld-9"]


def test_search_location_filter_applies_search_statuses(client: TestClient):
    params = {"continent": "north-america", "country": "canada", "subdivision": "quebec", "municipality": "montreal"}
    # With the directory statuses, the deprecated feed (ld-6) is left out, as in the directory counts.
    assert sorted(_feed_ids(_directory_feeds(client, **params))) == ["ld-2", "ld-3"]
    # Without a status filter, search returns every published feed located there, the deprecated one included.
    assert sorted(_feed_ids(_search(client, **params))) == ["ld-2", "ld-3", "ld-6"]


def test_search_location_filter_hides_wip_feeds_like_search(client: TestClient, monkeypatch):
    params = {"continent": "north-america", "country": "canada", "subdivision": "quebec", "municipality": "montreal"}
    assert "ld-7" not in _feed_ids(_search(client, **params))
    monkeypatch.setattr("feeds.impl.search_api_impl.is_user_email_restricted", lambda: False)
    assert "ld-7" in _feed_ids(_search(client, **params))


def test_search_location_filter_combines_with_other_filters(client: TestClient):
    params = {"continent": "north-america", "country": "canada", "status": DIRECTORY_STATUSES}
    assert sorted(_feed_ids(_search(client, data_type="gtfs_rt", **params))) == ["ld-3"]
    assert sorted(_feed_ids(_search(client, search_query="Montreal", **params))) == ["ld-2", "ld-3"]


def test_search_without_location_is_unchanged(client: TestClient):
    # No location filter: every published feed, including those without a mapped location (ld-12).
    body = SearchFeeds200Response.model_validate(_search(client).json())
    assert body.total == 12
    assert "ld-12" in {feed.id for feed in body.results}


def test_search_location_sort_requires_location(client: TestClient):
    response = _search(client, sort="location")
    assert response.status_code == 400
    assert response.json()["detail"] == search_location_sort_requires_location


def test_search_rejects_unknown_sort(client: TestClient):
    response = _search(client, sort="provider")
    assert response.status_code == 400
    assert response.json()["detail"] == search_sort_unsupported.format("provider")


def test_search_location_results_use_search_result_shape(client: TestClient):
    body = _directory_feeds(
        client, continent="north-america", country="canada", subdivision="quebec", municipality="montreal"
    ).json()

    assert [feed["id"] for feed in body["results"]] == ["ld-3", "ld-2"]
    feed = body["results"][1]
    assert feed["provider"] == "B Provider"
    assert feed["feed_name"] == "Montreal metro"
    assert feed["status"] == "active"
    assert {"country_code": "CA", "subdivision_name": "Québec", "municipality": "Montréal"}.items() <= feed[
        "locations"
    ][0].items()
