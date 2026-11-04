import pytest
from fastapi.testclient import TestClient

from feeds.impl.error_handling import (
    locations_sort_unsupported,
    search_location_sort_requires_location,
    search_sort_unsupported,
)
from feeds_gen.models.location_search_response import LocationSearchResponse
from feeds_gen.models.search_feeds200_response import SearchFeeds200Response

HEADERS = {"Authentication": "special-key"}
# The statuses counted in feed_counts, passed to /v1/search to list the same feeds.
DIRECTORY_STATUSES = "active,inactive,development,future"


def _locations(client: TestClient, **params) -> LocationSearchResponse:
    response = client.get("/v1/locations", headers=HEADERS, params=params)
    assert response.status_code == 200
    return LocationSearchResponse.model_validate(response.json())


def _search(client: TestClient, **params):
    return client.get("/v1/search", headers=HEADERS, params=params)


def _location_feeds(client: TestClient, **params) -> SearchFeeds200Response:
    """The feeds of a location, as listed by the web app: /v1/search with the counted statuses."""
    response = _search(client, status=DIRECTORY_STATUSES, sort="location", **params)
    assert response.status_code == 200
    return SearchFeeds200Response.model_validate(response.json())


def _feed_ids(body: SearchFeeds200Response) -> list:
    return [feed.id for feed in body.results]


def _counts(location) -> tuple:
    counts = location.feed_counts
    return counts.gtfs, counts.gtfs_rt, counts.gbfs, counts.total


def _names_and_counts(body: LocationSearchResponse) -> list:
    return [(location.name, _counts(location)) for location in body.results]


def test_continents_with_counts(client: TestClient):
    body = _locations(client, location_type="continent", include_feed_counts=True)

    assert body.total == 7
    assert [location.slug for location in body.results] == [
        "africa",
        "antarctica",
        "asia",
        "europe",
        "north-america",
        "oceania",
        "south-america",
    ]
    north_america = body.results[4]
    assert north_america.location_type == "continent"
    assert north_america.location_id is None
    assert north_america.parent_location_id is None
    assert north_america.country_code is None
    assert (north_america.continent_code, north_america.continent_slug, north_america.continent_name) == (
        "NA",
        "north-america",
        "North America",
    )
    assert north_america.path_slugs == []
    assert north_america.path_names == []
    # Distinct feeds of the countries of the continent: the cross-border feed ld-4, in Canada and the United States,
    # counts once. The deprecated (ld-5) and wip (ld-6) feeds are not counted, nor is the feed of Clipperton (ld-9),
    # a country without continent.
    assert _counts(north_america) == (4, 1, 1, 6)
    assert _counts(body.results[3]) == (1, 0, 0, 1)
    assert _counts(body.results[0]) == (0, 0, 0, 0)


def test_continents_with_feeds_sorted_by_feed_count(client: TestClient):
    body = _locations(client, location_type="continent", has_feeds=True, sort="feed_count")
    assert body.total == 2
    assert [location.slug for location in body.results] == ["north-america", "europe"]
    # Counts are only returned when requested.
    assert all(location.feed_counts is None for location in body.results)


@pytest.mark.parametrize(
    "params, expected_slugs",
    [
        ({"continent": "EU"}, ["europe"]),
        ({"continent": "North-America"}, ["north-america"]),
        ({"search_query": "north"}, ["north-america"]),
        ({"search_query": "amer"}, ["north-america", "south-america"]),
        # Continents are not contained in any location.
        ({"parent_location_id": 1}, []),
        ({"country_code": "CA"}, []),
        ({"path": "north-america"}, []),
    ],
)
def test_continents_filters(client: TestClient, params, expected_slugs):
    body = _locations(client, location_type="continent", **params)
    assert [location.slug for location in body.results] == expected_slugs
    assert body.total == len(expected_slugs)


def test_countries_of_a_continent(client: TestClient):
    body = _locations(client, location_type="country", continent="north-america")
    # By admin level: the Martinique boundary at admin level 3 comes after the countries at level 2.
    assert [location.name for location in body.results] == ["Canada", "United States", "Martinique"]
    canada = body.results[0]
    assert (canada.continent_code, canada.continent_slug, canada.continent_name) == (
        "NA",
        "north-america",
        "North America",
    )
    assert (canada.slug, canada.path_slugs) == ("canada", ["canada"])


def test_countries_of_a_continent_with_feeds_sorted_by_feed_count(client: TestClient):
    body = _locations(
        client,
        location_type="country",
        continent="NA",
        has_feeds=True,
        sort="feed_count",
        include_feed_counts=True,
    )
    assert body.total == 3
    # Canada has five feeds; Martinique and the United States have one each, ordered by name.
    assert _names_and_counts(body) == [
        ("Canada", (3, 1, 1, 5)),
        ("Martinique", (1, 0, 0, 1)),
        ("United States", (1, 0, 0, 1)),
    ]


def test_children_by_parent_location_id(client: TestClient):
    body = _locations(client, parent_location_id=1, include_feed_counts=True)
    assert [(location.location_id, location.parent_location_id) for location in body.results] == [(6, 1), (2, 1)]
    assert _names_and_counts(body) == [("Ontario", (1, 0, 0, 1)), ("Québec", (2, 1, 1, 4))]
    quebec = body.results[1]
    assert quebec.location_type == "subdivision"
    assert (quebec.slug, quebec.path_slugs, quebec.path_names) == ("quebec", ["canada", "quebec"], ["Canada", "Québec"])


def test_children_with_feeds(client: TestClient):
    body = _locations(client, parent_location_id=6)
    assert [location.location_id for location in body.results] == [8, 9, 7]

    with_feeds = _locations(client, parent_location_id=6, has_feeds=True)
    assert with_feeds.total == 1
    assert [location.name for location in with_feeds.results] == ["Toronto"]


def test_feed_counts_include_sub_areas(client: TestClient):
    body = _locations(client, path="canada/quebec/montreal-region/montreal", include_feed_counts=True)
    # Deprecated (ld-5) and wip (ld-6) feeds are not counted; the feed without stop count (ld-11) is.
    assert _names_and_counts(body) == [("Montréal", (2, 1, 1, 4))]


def test_wip_feeds_are_counted_for_unrestricted_users(client: TestClient, monkeypatch):
    monkeypatch.setattr("feeds.impl.location_feeds.is_user_email_restricted", lambda: False)
    montreal = _locations(client, path="canada/quebec/montreal-region/montreal", include_feed_counts=True)
    # ld-6 (wip) is now counted; ld-5 (deprecated) still is not.
    assert _names_and_counts(montreal) == [("Montréal", (3, 1, 1, 5))]
    continents = _locations(client, location_type="continent", continent="north-america", include_feed_counts=True)
    assert _counts(continents.results[0]) == (5, 1, 1, 7)


def test_path_lookup(client: TestClient):
    body = _locations(client, path="Canada/Quebec/Montreal-Region/Montreal")
    assert body.total == 1
    montreal = body.results[0]
    assert montreal.location_id == 4
    assert montreal.slug == "montreal"
    assert montreal.path_slugs == ["canada", "quebec", "montreal-region", "montreal"]
    assert montreal.path_names == ["Canada", "Québec", "Montréal (région)", "Montréal"]
    assert montreal.continent_code == "NA"

    paris = _locations(client, path="france/ile-de-france/paris").results
    assert [(location.location_id, location.continent_slug) for location in paris] == [(22, "europe")]


def test_path_lookup_with_slug_collision(client: TestClient):
    # Two Springfields under Ontario: each gets its id appended, and the bare slug matches neither.
    springfields = _locations(client, parent_location_id=6, search_query="springfield").results
    assert [(location.slug, location.path_slugs) for location in springfields] == [
        ("springfield-8", ["canada", "ontario", "springfield-8"]),
        ("springfield-9", ["canada", "ontario", "springfield-9"]),
    ]
    assert [location.location_id for location in _locations(client, path="canada/ontario/springfield-9").results] == [9]
    assert _locations(client, path="canada/ontario/springfield").total == 0


def test_country_boundaries_are_deduplicated(client: TestClient):
    body = _locations(client, location_type="country", country_code="MQ")
    assert [(location.location_id, location.slug) for location in body.results] == [(30, "martinique")]
    assert [location.location_id for location in _locations(client, path="martinique").results] == [30]


def test_country_without_continent(client: TestClient):
    clipperton = _locations(client, path="clipperton", include_feed_counts=True).results[0]
    assert (clipperton.continent_code, clipperton.continent_slug, clipperton.continent_name) == (None, None, None)
    assert _counts(clipperton) == (1, 0, 0, 1)


@pytest.mark.parametrize("params", [{"continent": "atlantis"}, {"path": "atlantis"}, {"parent_location_id": 999999}])
def test_unknown_locations_return_no_result(client: TestClient, params):
    body = _locations(client, **params)
    assert body.total == 0
    assert body.results == []


def test_locations_rejects_unknown_sort(client: TestClient):
    response = client.get("/v1/locations", headers=HEADERS, params={"sort": "name"})
    assert response.status_code == 400
    assert response.json()["detail"] == locations_sort_unsupported.format("name")


def test_search_by_location_sorted_by_stop_share(client: TestClient):
    body = _location_feeds(client, location_id=4)
    # ld-1 has all its stops in Montréal, ld-3 half of them and ld-2 a fifth; ld-11 has no stop count.
    assert body.total == 4
    assert _feed_ids(body) == ["ld-1", "ld-3", "ld-2", "ld-11"]


def test_search_by_location_includes_sub_areas(client: TestClient):
    # Every feed of Québec has all its stops there: ties are broken by provider, then feed name.
    assert _feed_ids(_location_feeds(client, location_id=2)) == ["ld-1", "ld-2", "ld-3", "ld-11"]
    # Three quarters of the stops of ld-4 are in Canada.
    assert _feed_ids(_location_feeds(client, location_id=1)) == ["ld-1", "ld-2", "ld-3", "ld-4", "ld-11"]


def test_search_by_continent(client: TestClient):
    body = _location_feeds(client, continent="north-america")
    assert body.total == 6
    assert _feed_ids(body) == ["ld-1", "ld-2", "ld-3", "ld-4", "ld-8", "ld-11"]
    assert _feed_ids(_location_feeds(client, continent="eu")) == ["ld-7"]


def test_search_by_continent_and_location(client: TestClient):
    assert _feed_ids(_location_feeds(client, continent="north-america", location_id=4)) == [
        "ld-1",
        "ld-3",
        "ld-2",
        "ld-11",
    ]
    assert _location_feeds(client, continent="europe", location_id=4).total == 0


def test_search_location_pagination(client: TestClient):
    body = _location_feeds(client, location_id=1, limit=2, offset=2)
    assert body.total == 5
    assert _feed_ids(body) == ["ld-3", "ld-4"]


def test_search_location_filter_applies_search_statuses(client: TestClient):
    # Without a status filter, search returns every published feed located there, the deprecated one included.
    response = _search(client, location_id=4, sort="location")
    assert _feed_ids(SearchFeeds200Response.model_validate(response.json())) == [
        "ld-1",
        "ld-5",
        "ld-3",
        "ld-2",
        "ld-11",
    ]


def test_search_location_filter_hides_wip_feeds_like_search(client: TestClient, monkeypatch):
    assert "ld-6" not in _feed_ids(_location_feeds(client, location_id=4))
    monkeypatch.setattr("feeds.impl.search_api_impl.is_user_email_restricted", lambda: False)
    assert "ld-6" in _feed_ids(_location_feeds(client, location_id=4))


def test_search_location_filter_combines_with_other_filters(client: TestClient):
    response = _search(client, location_id=1, status=DIRECTORY_STATUSES, data_type="gtfs_rt")
    assert _feed_ids(SearchFeeds200Response.model_validate(response.json())) == ["ld-2"]
    # Feeds matching the text (here through the names of their OSM locations) within the continent.
    response = _search(client, continent="north-america", status=DIRECTORY_STATUSES, search_query="Laval")
    assert sorted(_feed_ids(SearchFeeds200Response.model_validate(response.json()))) == ["ld-2", "ld-3"]
    response = _search(client, continent="europe", status=DIRECTORY_STATUSES, search_query="Laval")
    assert _feed_ids(SearchFeeds200Response.model_validate(response.json())) == []


@pytest.mark.parametrize("params", [{"continent": "atlantis"}, {"location_id": 999999}])
def test_search_unknown_location_returns_no_feed(client: TestClient, params):
    response = _search(client, sort="location", **params)
    assert response.status_code == 200
    assert response.json() == {"total": 0, "results": []}


def test_search_without_location_is_unchanged(client: TestClient):
    # No location filter: every published feed, including the one that was never geolocated (ld-10).
    body = SearchFeeds200Response.model_validate(_search(client).json())
    assert body.total == 10
    assert "ld-10" in _feed_ids(body)


def test_search_location_sort_requires_location(client: TestClient):
    response = _search(client, sort="location")
    assert response.status_code == 400
    assert response.json()["detail"] == search_location_sort_requires_location


def test_search_rejects_unknown_sort(client: TestClient):
    response = _search(client, sort="provider")
    assert response.status_code == 400
    assert response.json()["detail"] == search_sort_unsupported.format("provider")
