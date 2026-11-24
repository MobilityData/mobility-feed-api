import pytest
from fastapi.testclient import TestClient

from feeds.impl.error_handling import (
    locations_include_unsupported,
    locations_sort_unsupported,
    search_location_id_and_continent,
    search_location_sort_requires_location,
    search_sort_unsupported,
)
from feeds_gen.models.location_search_response import LocationSearchResponse
from feeds_gen.models.search_feeds200_response import SearchFeeds200Response

HEADERS = {"Authentication": "special-key"}
# The statuses counted in feed_counts, passed to /v1/search to list the same feeds.
DIRECTORY_STATUSES = "active,inactive,development,future"
CONTINENT_SLUGS = ["africa", "antarctica", "asia", "europe", "north-america", "oceania", "south-america"]


def _locations(client: TestClient, **params) -> LocationSearchResponse:
    response = client.get("/v1/locations", headers=HEADERS, params=params)
    assert response.status_code == 200, response.text
    return LocationSearchResponse.model_validate(response.json())


def _location(client: TestClient, location_id: int, **params):
    """One location, from the `location_id` filter."""
    body = _locations(client, location_id=location_id, **params)
    assert body.total == 1
    return body.results[0]


def _continent(client: TestClient, continent: str, **params):
    body = _locations(client, location_type="continent", continent=continent, **params)
    assert body.total == 1
    return body.results[0]


def _children(client: TestClient, location_id: int, **params) -> LocationSearchResponse:
    return _locations(client, parent_location_id=location_id, **params)


def _search(client: TestClient, **params):
    return client.get("/v1/search", headers=HEADERS, params=params)


def _location_feeds(client: TestClient, **params) -> SearchFeeds200Response:
    """The feeds of a location, as listed by the web app: /v1/search with the counted statuses."""
    response = _search(client, status=DIRECTORY_STATUSES, sort="location", **params)
    assert response.status_code == 200, response.text
    return SearchFeeds200Response.model_validate(response.json())


def _feed_ids(body: SearchFeeds200Response) -> list:
    return [feed.id for feed in body.results]


def _counts(location) -> tuple:
    counts = location.feed_counts
    return counts.gtfs, counts.gtfs_rt, counts.gbfs, counts.total


def _names_and_counts(body: LocationSearchResponse) -> list:
    return [(location.name, _counts(location)) for location in body.results]


# /v1/locations: continents


def test_continents_come_first(client: TestClient):
    body = _locations(client, limit=8)
    assert [location.slug for location in body.results[:7]] == CONTINENT_SLUGS
    # Continents have no location id: their continent code identifies them.
    assert [location.location_id for location in body.results[:7]] == [None] * 7
    # Then the countries, at admin level 2.
    assert body.results[7].name == "Canada"
    assert body.results[7].location_type == "country"


def test_continents_with_counts(client: TestClient):
    body = _locations(client, location_type="continent", include="feed_counts")

    assert body.total == 7
    assert [location.slug for location in body.results] == CONTINENT_SLUGS
    north_america = body.results[4]
    assert north_america.location_type == "continent"
    assert (north_america.location_id, north_america.parent_location_id) == (None, None)
    assert north_america.country_code is None
    assert north_america.continent_code == "NA"
    assert (north_america.name, north_america.display_name) == ("North America", "North America")
    assert north_america.path_slugs == ["north-america"]
    assert north_america.path_names == ["North America"]
    # Distinct feeds of the countries of the continent: the cross-border feed ld-4, in Canada and the United States,
    # counts once, and ld-14, located under a discarded boundary of Martinique, counts in Martinique. The deprecated
    # (ld-5) and wip (ld-6) feeds are not counted, nor is the feed of Clipperton (ld-9), a country without continent.
    assert _counts(north_america) == (5, 1, 1, 7)
    # ld-7 and ld-13, located in Paris. ld-12 is never geolocated: it is counted nowhere.
    assert _counts(body.results[3]) == (1, 1, 0, 2)
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
        # Continents have no id, parent, country or subdivision.
        ({"country_code": "CA"}, []),
        ({"subdivision_code": "CA-QC"}, []),
        ({"location_id": 1}, []),
        ({"parent_location_id": 1}, []),
    ],
)
def test_continents_filters(client: TestClient, params, expected_slugs):
    body = _locations(client, location_type="continent", **params)
    assert [location.slug for location in body.results] == expected_slugs
    assert body.total == len(expected_slugs)


def test_search_query_matches_continents_and_places(client: TestClient):
    assert [location.name for location in _locations(client, search_query="europe").results] == ["Europe"]
    assert [location.name for location in _locations(client, search_query="france").results] == [
        "France",
        "Île-de-France",
        "Fort-de-France",
        "Paris",
    ]


def test_continent_filter_includes_the_continent(client: TestClient):
    body = _locations(client, continent="eu")
    assert [location.name for location in body.results] == ["Europe", "France", "Île-de-France", "Paris"]
    assert body.total == 4


def test_wip_feeds_are_counted_for_unrestricted_users(client: TestClient, monkeypatch):
    monkeypatch.setattr("feeds.impl.locations_api_impl.is_user_email_restricted", lambda: False)
    # ld-6 (wip) is now counted; ld-5 (deprecated) still is not.
    assert _counts(_location(client, 4, include="feed_counts")) == (3, 1, 1, 5)
    assert _counts(_continent(client, "NA", include="feed_counts")) == (6, 1, 1, 8)


# /v1/locations: places


def test_location_by_id(client: TestClient):
    quebec = _location(client, 2, include="feed_counts")
    assert (quebec.name, quebec.location_type, quebec.parent_location_id) == ("Québec", "subdivision", 1)
    assert (quebec.slug, quebec.path_slugs) == ("2-quebec", ["ca", "2-quebec"])
    assert _counts(quebec) == (2, 1, 1, 4)


def test_unknown_location_id(client: TestClient):
    body = _locations(client, location_id=999999)
    assert (body.total, body.results) == (0, [])


def test_country_code_filter_includes_the_country(client: TestClient):
    body = _locations(client, country_code="fr")
    assert [location.name for location in body.results] == ["France", "Île-de-France", "Paris"]
    body = _locations(client, subdivision_code="CA-ON")
    assert [location.name for location in body.results] == ["Ontario", "Springfield", "Springfield", "Toronto"]


def test_countries_of_a_continent(client: TestClient):
    body = _locations(client, location_type="country", continent="north-america")
    # By admin level: the Martinique boundary at admin level 3 comes after the countries at level 2.
    assert [location.name for location in body.results] == ["Canada", "United States", "Martinique"]
    canada = body.results[0]
    # A country has no parent: its continent is its continent_code.
    assert (canada.location_id, canada.parent_location_id, canada.continent_code) == (1, None, "NA")
    assert (canada.slug, canada.path_slugs) == ("ca", ["ca"])
    assert (canada.path_names, canada.display_name) == (["Canada"], "Canada")


def test_countries_of_a_continent_with_feeds_sorted_by_feed_count(client: TestClient):
    body = _locations(
        client,
        location_type="country",
        continent="NA",
        has_feeds=True,
        sort="feed_count",
        include="feed_counts",
    )
    assert body.total == 3
    assert _names_and_counts(body) == [
        ("Canada", (3, 1, 1, 5)),
        ("Martinique", (2, 0, 0, 2)),
        ("United States", (1, 0, 0, 1)),
    ]


def test_locations_has_feeds(client: TestClient):
    body = _locations(client, country_code="CA", location_type="municipality")
    assert body.total == 6
    with_feeds = _locations(client, country_code="CA", location_type="municipality", has_feeds=True)
    # The Springfields have no feed. By admin level, then display name ("Canada, Ontario, Toronto" first).
    assert [location.name for location in with_feeds.results] == ["Montréal (région)", "Toronto", "Laval", "Montréal"]


def test_place_slugs_and_paths_start_at_the_country(client: TestClient):
    montreal = _location(client, 4)
    assert montreal.slug == "4-montreal"
    assert montreal.path_slugs == ["ca", "2-quebec", "3-montreal-region", "4-montreal"]
    assert montreal.path_names == ["Canada", "Québec", "Montréal (région)", "Montréal"]
    assert montreal.display_name == "Canada, Québec, Montréal (région), Montréal"
    assert (montreal.parent_location_id, montreal.continent_code) == (3, "NA")


def test_slugs_start_with_the_osm_id(client: TestClient):
    slugs = {location.location_id: location.slug for location in _children(client, 40).results}
    assert slugs == {
        # Same name, different ids.
        41: "41-springfield",
        42: "42-springfield",
        43: "43-springfield-41",
        # No ASCII letter or digit in the name: the id alone.
        44: "44",
        45: "45-44",
    }


def test_country_boundaries_are_deduplicated(client: TestClient):
    body = _locations(client, location_type="country", country_code="MQ", include="feed_counts")
    assert [(location.location_id, location.slug) for location in body.results] == [(30, "mq")]
    # ld-8, in the kept boundary, and ld-14, in a group of the discarded one.
    assert _counts(body.results[0]) == (2, 0, 0, 2)


def test_children_of_a_discarded_country_boundary_belong_to_the_kept_one(client: TestClient):
    # Fort-de-France's parent in the hierarchy is the discarded Martinique boundary (31).
    assert [location.location_id for location in _children(client, 30).results] == [32]
    fort_de_france = _location(client, 32, include="feed_counts")
    assert fort_de_france.parent_location_id == 30
    assert fort_de_france.path_names == ["Martinique", "Fort-de-France"]
    assert fort_de_france.path_slugs == ["mq", "32-fort-de-france"]
    assert fort_de_france.country_name == "Martinique"
    assert _counts(fort_de_france) == (1, 0, 0, 1)


def test_country_without_continent(client: TestClient):
    clipperton = _location(client, 50, include="feed_counts")
    assert (clipperton.parent_location_id, clipperton.continent_code) == (None, None)
    assert (clipperton.slug, clipperton.path_slugs, clipperton.path_names) == ("cp", ["cp"], ["Clipperton"])
    assert _counts(clipperton) == (1, 0, 0, 1)


# /v1/locations: children (parent_location_id)


def test_children_of_a_country(client: TestClient):
    body = _children(client, 1, include="feed_counts")
    assert [(location.location_id, location.parent_location_id) for location in body.results] == [(6, 1), (2, 1)]
    assert _names_and_counts(body) == [("Ontario", (1, 0, 0, 1)), ("Québec", (2, 1, 1, 4))]


def test_children_of_a_subdivision(client: TestClient):
    body = _children(client, 2)
    # Depth varies: the children of Québec are a region and a municipality.
    assert [(location.location_id, location.name) for location in body.results] == [
        (3, "Montréal (région)"),
        (5, "Laval"),
    ]
    assert all(location.feed_counts is None for location in body.results)


def test_children_with_feeds_and_pagination(client: TestClient):
    assert [location.location_id for location in _children(client, 6).results] == [8, 9, 7]
    with_feeds = _children(client, 6, has_feeds=True)
    assert with_feeds.total == 1
    assert [location.name for location in with_feeds.results] == ["Toronto"]
    page = _children(client, 6, limit=1, offset=1)
    assert (page.total, [location.location_id for location in page.results]) == (3, [9])
    by_feed_count = _children(client, 1, sort="feed_count")
    assert [location.name for location in by_feed_count.results] == ["Québec", "Ontario"]


def test_children_with_feeds_total_on_every_page(client: TestClient):
    # Canada's children with feeds (Québec, Ontario): the total comes with each page, and a page past the last one
    # still reports it.
    first = _children(client, 1, has_feeds=True, sort="feed_count", limit=1)
    assert (first.total, [location.location_id for location in first.results]) == (2, [2])
    second = _children(client, 1, has_feeds=True, sort="feed_count", limit=1, offset=1)
    assert (second.total, [location.location_id for location in second.results]) == (2, [6])
    past_the_end = _children(client, 1, has_feeds=True, sort="feed_count", limit=1, offset=5)
    assert (past_the_end.total, past_the_end.results) == (2, [])
    empty_page = _children(client, 1, has_feeds=True, sort="feed_count", limit=0)
    assert (empty_page.total, empty_page.results) == (2, [])


def test_children_of_a_location_without_children(client: TestClient):
    body = _children(client, 4)
    assert (body.total, body.results) == (0, [])


# /v1/locations: parameters


@pytest.mark.parametrize("include", ["children", "unknown"])
def test_locations_rejects_unsupported_include(client: TestClient, include):
    response = client.get("/v1/locations", headers=HEADERS, params={"include": include})
    assert response.status_code == 400
    assert response.json()["detail"] == locations_include_unsupported.format(include, "'feed_counts'")


def test_locations_rejects_unknown_sort(client: TestClient):
    response = client.get("/v1/locations", headers=HEADERS, params={"sort": "name"})
    assert response.status_code == 400
    assert response.json()["detail"] == locations_sort_unsupported.format("name")


def test_locations_unknown_continent_returns_no_result(client: TestClient):
    body = _locations(client, continent="atlantis")
    assert (body.total, body.results) == (0, [])


@pytest.mark.parametrize("path", ["/v1/locations/lookup", "/v1/locations/1", "/v1/locations/1/children"])
def test_location_endpoints_are_removed(client: TestClient, path):
    assert client.get(path, headers=HEADERS).status_code == 404


# /v1/search


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
    # The same feeds as the continent's count.
    assert body.total == 7
    assert _feed_ids(body) == ["ld-1", "ld-2", "ld-3", "ld-4", "ld-8", "ld-14", "ld-11"]
    assert _feed_ids(_location_feeds(client, continent="EU")) == ["ld-7", "ld-13"]


def test_search_by_country_includes_its_discarded_boundaries(client: TestClient):
    # The same feeds as Martinique's count: ld-14 is located under the discarded boundary.
    assert _feed_ids(_location_feeds(client, location_id=30)) == ["ld-8", "ld-14"]


def test_search_with_location_id_and_continent(client: TestClient):
    response = _search(client, location_id=4, continent="north-america")
    assert response.status_code == 400
    assert response.json()["detail"] == search_location_id_and_continent


def test_realtime_feed_without_location_is_in_no_location(client: TestClient):
    # ld-12 references ld-7 (Paris) but has no location group of its own.
    assert _counts(_location(client, 22, include="feed_counts")) == (1, 1, 0, 2)
    response = _search(client, location_id=22, status=DIRECTORY_STATUSES, data_type="gtfs_rt", sort="location")
    assert _feed_ids(SearchFeeds200Response.model_validate(response.json())) == ["ld-13"]
    assert "ld-12" not in _feed_ids(_location_feeds(client, continent="europe"))
    # ld-13 references ld-1 (Montréal) but is located in Paris only.
    assert "ld-13" not in _feed_ids(_location_feeds(client, location_id=4))


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


@pytest.mark.parametrize("params", [{"location_id": 999999}, {"continent": "atlantis"}])
def test_search_unknown_location_returns_no_feed(client: TestClient, params):
    response = _search(client, sort="location", **params)
    assert response.status_code == 200
    assert response.json() == {"total": 0, "results": []}


def test_search_without_location_is_unchanged(client: TestClient):
    # No location filter: every published feed, including those that were never geolocated (ld-10, ld-12).
    body = SearchFeeds200Response.model_validate(_search(client).json())
    assert body.total == 13
    assert {"ld-10", "ld-12"} <= set(_feed_ids(body))


@pytest.mark.parametrize("params", [{}, {"continent": " "}])
def test_search_location_sort_requires_location(client: TestClient, params):
    response = _search(client, sort="location", **params)
    assert response.status_code == 400
    assert response.json()["detail"] == search_location_sort_requires_location


def test_search_rejects_unknown_sort(client: TestClient):
    response = _search(client, sort="provider")
    assert response.status_code == 400
    assert response.json()["detail"] == search_sort_unsupported.format("provider")
