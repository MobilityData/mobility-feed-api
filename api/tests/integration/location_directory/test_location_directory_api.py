import pytest
from fastapi.testclient import TestClient

from feeds.impl.error_handling import (
    location_not_found,
    location_path_not_found,
    location_path_required,
    locations_include_unsupported,
    locations_sort_unsupported,
    search_location_id_and_path,
    search_location_sort_requires_location,
    search_sort_unsupported,
)
from feeds_gen.models.location_detail import LocationDetail
from feeds_gen.models.location_search_response import LocationSearchResponse
from feeds_gen.models.search_feeds200_response import SearchFeeds200Response

HEADERS = {"Authentication": "special-key"}
# The statuses counted in feed_counts, passed to /v1/search to list the same feeds.
DIRECTORY_STATUSES = "active,inactive,development,future"
CONTINENT_SLUGS = ["africa", "antarctica", "asia", "europe", "north-america", "oceania", "south-america"]
NORTH_AMERICA = -5
EUROPE = -4


def _locations(client: TestClient, **params) -> LocationSearchResponse:
    response = client.get("/v1/locations", headers=HEADERS, params=params)
    assert response.status_code == 200, response.text
    return LocationSearchResponse.model_validate(response.json())


def _lookup(client: TestClient, path: str, **params) -> LocationDetail:
    response = client.get("/v1/locations/lookup", headers=HEADERS, params={"path": path, **params})
    assert response.status_code == 200, response.text
    return LocationDetail.model_validate(response.json())


def _location(client: TestClient, location_id: int, **params) -> LocationDetail:
    response = client.get(f"/v1/locations/{location_id}", headers=HEADERS, params=params)
    assert response.status_code == 200, response.text
    return LocationDetail.model_validate(response.json())


def _children(client: TestClient, location_id: int, **params) -> LocationSearchResponse:
    response = client.get(f"/v1/locations/{location_id}/children", headers=HEADERS, params=params)
    assert response.status_code == 200, response.text
    return LocationSearchResponse.model_validate(response.json())


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


# /v1/locations


def test_continents_come_first(client: TestClient):
    body = _locations(client, limit=8)
    assert [location.slug for location in body.results[:7]] == CONTINENT_SLUGS
    assert [location.location_id for location in body.results[:7]] == [-1, -2, -3, -4, -5, -6, -7]
    # Then the countries, at admin level 2.
    assert body.results[7].name == "Canada"
    assert body.results[7].location_type == "country"


def test_continents_with_counts(client: TestClient):
    body = _locations(client, location_type="continent", include="feed_counts")

    assert body.total == 7
    assert [location.slug for location in body.results] == CONTINENT_SLUGS
    north_america = body.results[4]
    assert north_america.location_type == "continent"
    assert north_america.location_id == NORTH_AMERICA
    assert north_america.parent_location_id is None
    assert north_america.country_code is None
    assert north_america.continent_code == "NA"
    assert (north_america.name, north_america.display_name) == ("North America", "North America")
    assert (north_america.slug, north_america.path) == ("north-america", "north-america")
    assert north_america.path_slugs == ["north-america"]
    assert north_america.path_names == ["North America"]
    # Distinct feeds of the countries of the continent: the cross-border feed ld-4, in Canada and the United States,
    # counts once. The deprecated (ld-5) and wip (ld-6) feeds are not counted, nor is the feed of Clipperton (ld-9),
    # a country without continent. ld-13 references ld-1 (Montréal) but has its own location, Paris.
    assert _counts(north_america) == (4, 1, 1, 6)
    # ld-7 and the two realtime feeds of Paris: ld-12 through its schedule feed ld-7, ld-13 through its own location.
    assert _counts(body.results[3]) == (1, 2, 0, 3)
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
        # Continents are not contained in any country.
        ({"country_code": "CA"}, []),
    ],
)
def test_continents_filters(client: TestClient, params, expected_slugs):
    body = _locations(client, location_type="continent", **params)
    assert [location.slug for location in body.results] == expected_slugs
    assert body.total == len(expected_slugs)


def test_continent_filter_includes_the_continent(client: TestClient):
    body = _locations(client, continent="eu")
    assert [location.name for location in body.results] == ["Europe", "France", "Île-de-France", "Paris"]
    assert body.total == 4


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
    assert (canada.location_id, canada.parent_location_id, canada.continent_code) == (1, NORTH_AMERICA, "NA")
    assert (canada.slug, canada.path, canada.path_slugs) == (
        "canada",
        "north-america/canada",
        ["north-america", "canada"],
    )
    assert (canada.path_names, canada.display_name) == (["North America", "Canada"], "Canada")


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
    # Canada has five feeds; Martinique and the United States have one each, ordered by name.
    assert _names_and_counts(body) == [
        ("Canada", (3, 1, 1, 5)),
        ("Martinique", (1, 0, 0, 1)),
        ("United States", (1, 0, 0, 1)),
    ]


def test_locations_has_feeds(client: TestClient):
    body = _locations(client, country_code="CA", location_type="municipality")
    assert body.total == 6
    with_feeds = _locations(client, country_code="CA", location_type="municipality", has_feeds=True)
    # The Springfields have no feed. By admin level, then display name ("Canada, Ontario, Toronto" first).
    assert [location.name for location in with_feeds.results] == ["Montréal (région)", "Toronto", "Laval", "Montréal"]


def test_place_paths_start_with_the_continent(client: TestClient):
    montreal = _locations(client, search_query="montreal", location_type="municipality", sort="admin_level")
    assert [location.location_id for location in montreal.results] == [3, 4]
    montreal = montreal.results[1]
    assert montreal.path == "north-america/canada/quebec/montreal-region/montreal"
    assert montreal.path_slugs == ["north-america", "canada", "quebec", "montreal-region", "montreal"]
    assert montreal.path_names == ["North America", "Canada", "Québec", "Montréal (région)", "Montréal"]
    # The display name starts at the country.
    assert montreal.display_name == "Canada, Québec, Montréal (région), Montréal"
    assert montreal.parent_location_id == 3


@pytest.mark.parametrize("include", ["children", "feed_counts,children", "unknown"])
def test_locations_rejects_unsupported_include(client: TestClient, include):
    response = client.get("/v1/locations", headers=HEADERS, params={"include": include})
    assert response.status_code == 400
    unsupported = "unknown" if include == "unknown" else "children"
    assert response.json()["detail"] == locations_include_unsupported.format(unsupported, "'feed_counts'")


def test_locations_rejects_unknown_sort(client: TestClient):
    response = client.get("/v1/locations", headers=HEADERS, params={"sort": "name"})
    assert response.status_code == 400
    assert response.json()["detail"] == locations_sort_unsupported.format("name")


def test_locations_unknown_continent_returns_no_result(client: TestClient):
    body = _locations(client, continent="atlantis")
    assert body.total == 0
    assert body.results == []


def test_wip_feeds_are_counted_for_unrestricted_users(client: TestClient, monkeypatch):
    monkeypatch.setattr("feeds.impl.location_feeds.is_user_email_restricted", lambda: False)
    montreal = _location(client, 4, include="feed_counts")
    # ld-6 (wip) is now counted; ld-5 (deprecated) still is not.
    assert _counts(montreal) == (3, 1, 1, 5)
    assert _counts(_location(client, NORTH_AMERICA, include="feed_counts")) == (5, 1, 1, 7)


# /v1/locations/lookup


def test_lookup_place(client: TestClient):
    montreal = _lookup(client, "North-America/Canada/Quebec/Montreal-Region/Montreal")
    assert montreal.location_id == 4
    assert montreal.location_type == "municipality"
    assert montreal.slug == "montreal"
    assert montreal.path == "north-america/canada/quebec/montreal-region/montreal"
    assert montreal.path_names == ["North America", "Canada", "Québec", "Montréal (région)", "Montréal"]
    assert (montreal.country_code, montreal.subdivision_code, montreal.continent_code) == ("CA", "CA-QC", "NA")
    # Neither counts nor children unless requested.
    assert montreal.feed_counts is None
    assert montreal.children is None

    paris = _lookup(client, "europe/france/ile-de-france/paris")
    assert (paris.location_id, paris.continent_code) == (22, "EU")


def test_lookup_continent(client: TestClient):
    north_america = _lookup(client, "north-america")
    assert (north_america.location_id, north_america.location_type) == (NORTH_AMERICA, "continent")
    assert north_america.parent_location_id is None
    assert north_america.path_slugs == ["north-america"]
    assert north_america.path_names == ["North America"]


def test_lookup_ignores_slashes_and_case(client: TestClient):
    canada = _lookup(client, "/North-America/Canada/")
    assert (canada.location_id, canada.parent_location_id) == (1, NORTH_AMERICA)


def test_lookup_country_without_continent(client: TestClient):
    clipperton = _lookup(client, "clipperton", include="feed_counts")
    assert clipperton.location_id == 50
    assert clipperton.parent_location_id is None
    assert clipperton.continent_code is None
    assert (clipperton.path, clipperton.path_slugs, clipperton.path_names) == (
        "clipperton",
        ["clipperton"],
        ["Clipperton"],
    )
    assert _counts(clipperton) == (1, 0, 0, 1)


def test_lookup_with_slug_collision(client: TestClient):
    # Two Springfields under Ontario: each gets its id appended, and the bare slug matches neither.
    springfields = _children(client, 6).results[:2]
    assert [(location.slug, location.path) for location in springfields] == [
        ("springfield-8", "north-america/canada/ontario/springfield-8"),
        ("springfield-9", "north-america/canada/ontario/springfield-9"),
    ]
    assert _lookup(client, "north-america/canada/ontario/springfield-9").location_id == 9
    response = client.get(
        "/v1/locations/lookup", headers=HEADERS, params={"path": "north-america/canada/ontario/springfield"}
    )
    assert response.status_code == 404


def test_country_boundaries_are_deduplicated(client: TestClient):
    body = _locations(client, location_type="country", country_code="MQ")
    assert [(location.location_id, location.slug) for location in body.results] == [(30, "martinique")]
    assert _lookup(client, "north-america/martinique").location_id == 30


@pytest.mark.parametrize(
    "path",
    [
        "atlantis",
        # Paths start with the continent.
        "canada/quebec",
    ],
)
def test_lookup_unknown_path(client: TestClient, path):
    response = client.get("/v1/locations/lookup", headers=HEADERS, params={"path": path})
    assert response.status_code == 404
    assert response.json()["detail"] == location_path_not_found.format(path)


@pytest.mark.parametrize("params", [{}, {"path": " / "}])
def test_lookup_requires_a_path(client: TestClient, params):
    response = client.get("/v1/locations/lookup", headers=HEADERS, params=params)
    assert response.status_code == 400
    assert response.json()["detail"] == location_path_required


def test_lookup_with_children(client: TestClient):
    north_america = _lookup(client, "north-america", include="children")
    assert north_america.feed_counts is None
    assert north_america.children.total == 3
    assert [(location.name, location.parent_location_id) for location in north_america.children.results] == [
        ("Canada", NORTH_AMERICA),
        ("United States", NORTH_AMERICA),
        ("Martinique", NORTH_AMERICA),
    ]
    assert all(location.feed_counts is None for location in north_america.children.results)


def test_lookup_with_children_and_feed_counts(client: TestClient):
    north_america = _lookup(client, "north-america", include="feed_counts,children", sort="feed_count")
    assert _counts(north_america) == (4, 1, 1, 6)
    assert _names_and_counts(north_america.children) == [
        ("Canada", (3, 1, 1, 5)),
        ("Martinique", (1, 0, 0, 1)),
        ("United States", (1, 0, 0, 1)),
    ]

    # limit and offset page the children.
    page = _lookup(client, "north-america", include="children", sort="feed_count", limit=1, offset=1)
    assert page.children.total == 3
    assert [location.name for location in page.children.results] == ["Martinique"]


def test_lookup_with_children_with_feeds(client: TestClient):
    ontario = _lookup(client, "north-america/canada/ontario", include=["children", "feed_counts"], has_feeds=True)
    assert ontario.children.total == 1
    assert _names_and_counts(ontario.children) == [("Toronto", (1, 0, 0, 1))]
    # Without children, has_feeds does not apply to the location itself.
    quebec = _lookup(client, "north-america/canada/quebec", has_feeds=True)
    assert (quebec.location_id, quebec.children) == (2, None)


@pytest.mark.parametrize(
    "params, detail",
    [
        ({"sort": "name"}, locations_sort_unsupported.format("name")),
        ({"include": "parents"}, locations_include_unsupported.format("parents", "'feed_counts', 'children'")),
    ],
)
def test_lookup_rejects_unsupported_values(client: TestClient, params, detail):
    response = client.get("/v1/locations/lookup", headers=HEADERS, params={"path": "north-america", **params})
    assert response.status_code == 400
    assert response.json()["detail"] == detail


# /v1/locations/{location_id}


def test_location_by_id(client: TestClient):
    quebec = _location(client, 2, include="feed_counts")
    assert (quebec.name, quebec.location_type, quebec.parent_location_id) == ("Québec", "subdivision", 1)
    assert quebec.path == "north-america/canada/quebec"
    assert _counts(quebec) == (2, 1, 1, 4)
    assert quebec.children is None


def test_continent_by_id(client: TestClient):
    north_america = _location(client, NORTH_AMERICA, include="children")
    assert (north_america.slug, north_america.location_type) == ("north-america", "continent")
    assert [location.location_id for location in north_america.children.results] == [1, 10, 30]


def test_location_by_id_matches_lookup(client: TestClient):
    assert _location(client, 22) == _lookup(client, "europe/france/ile-de-france/paris")


@pytest.mark.parametrize("location_id", [999999, -99])
def test_unknown_location_id(client: TestClient, location_id):
    response = client.get(f"/v1/locations/{location_id}", headers=HEADERS)
    assert response.status_code == 404
    assert response.json()["detail"] == location_not_found.format(location_id)


def test_location_by_id_rejects_unsupported_include(client: TestClient):
    response = client.get("/v1/locations/1", headers=HEADERS, params={"include": "children,parents"})
    assert response.status_code == 400


# /v1/locations/{location_id}/children


def test_children_with_feeds_total_on_every_page(client: TestClient):
    # Canada's children with feeds (Ontario, Quebec): the total comes with each page, and a page past the last one
    # still reports it.
    first = _children(client, 1, has_feeds=True, sort="feed_count", limit=1)
    assert (first.total, [location.location_id for location in first.results]) == (2, [2])
    second = _children(client, 1, has_feeds=True, sort="feed_count", limit=1, offset=1)
    assert (second.total, [location.location_id for location in second.results]) == (2, [6])
    past_the_end = _children(client, 1, has_feeds=True, sort="feed_count", limit=1, offset=5)
    assert (past_the_end.total, past_the_end.results) == (2, [])


def test_children_of_a_continent(client: TestClient):
    body = _children(client, NORTH_AMERICA, include="feed_counts")
    assert body.total == 3
    assert [(location.location_id, location.parent_location_id) for location in body.results] == [
        (1, NORTH_AMERICA),
        (10, NORTH_AMERICA),
        (30, NORTH_AMERICA),
    ]
    assert _names_and_counts(body) == [
        ("Canada", (3, 1, 1, 5)),
        ("United States", (1, 0, 0, 1)),
        ("Martinique", (1, 0, 0, 1)),
    ]
    assert [location.name for location in _children(client, EUROPE).results] == ["France"]


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


def test_children_of_a_location_without_children(client: TestClient):
    body = _children(client, 4)
    assert body.total == 0
    assert body.results == []


def test_children_of_an_unknown_location(client: TestClient):
    response = client.get("/v1/locations/999999/children", headers=HEADERS)
    assert response.status_code == 404
    assert response.json()["detail"] == location_not_found.format(999999)


@pytest.mark.parametrize(
    "params, detail",
    [
        ({"sort": "name"}, locations_sort_unsupported.format("name")),
        ({"include": "children"}, locations_include_unsupported.format("children", "'feed_counts'")),
    ],
)
def test_children_rejects_unsupported_values(client: TestClient, params, detail):
    response = client.get("/v1/locations/1/children", headers=HEADERS, params=params)
    assert response.status_code == 400
    assert response.json()["detail"] == detail


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


def test_search_by_continent_id(client: TestClient):
    body = _location_feeds(client, location_id=NORTH_AMERICA)
    assert body.total == 6
    assert _feed_ids(body) == ["ld-1", "ld-2", "ld-3", "ld-4", "ld-8", "ld-11"]
    # Paris feeds all have their stops in Europe: ties are broken by provider, then feed name.
    assert _feed_ids(_location_feeds(client, location_id=EUROPE)) == ["ld-7", "ld-12", "ld-13"]


def test_search_by_location_path(client: TestClient):
    assert _feed_ids(
        _location_feeds(client, location_path="North-America/Canada/Quebec/Montreal-Region/Montreal/")
    ) == [
        "ld-1",
        "ld-3",
        "ld-2",
        "ld-11",
    ]
    assert _feed_ids(_location_feeds(client, location_path="europe")) == ["ld-7", "ld-12", "ld-13"]
    assert _feed_ids(_location_feeds(client, location_path="clipperton")) == ["ld-9"]


def test_search_with_location_id_and_path(client: TestClient):
    response = _search(client, location_id=4, location_path="north-america/canada")
    assert response.status_code == 400
    assert response.json()["detail"] == search_location_id_and_path


def test_realtime_feed_takes_the_location_of_its_schedule_feed(client: TestClient):
    paris = _location(client, 22, include="feed_counts")
    assert _counts(paris) == (1, 2, 0, 3)
    response = _search(client, location_id=22, status=DIRECTORY_STATUSES, data_type="gtfs_rt", sort="location")
    assert _feed_ids(SearchFeeds200Response.model_validate(response.json())) == ["ld-12", "ld-13"]
    # A realtime feed with its own location is only there: ld-13 is not in Montréal, where its schedule feed is.
    assert "ld-13" not in _feed_ids(_location_feeds(client, location_id=4))
    # The continent counts and lists it too.
    assert "ld-12" in _feed_ids(_location_feeds(client, location_id=EUROPE))


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
    response = _search(client, location_id=NORTH_AMERICA, status=DIRECTORY_STATUSES, search_query="Laval")
    assert sorted(_feed_ids(SearchFeeds200Response.model_validate(response.json()))) == ["ld-2", "ld-3"]
    response = _search(client, location_path="europe", status=DIRECTORY_STATUSES, search_query="Laval")
    assert _feed_ids(SearchFeeds200Response.model_validate(response.json())) == []


@pytest.mark.parametrize(
    "params",
    [{"location_id": 999999}, {"location_id": -99}, {"location_path": "atlantis"}, {"location_path": "canada"}],
)
def test_search_unknown_location_returns_no_feed(client: TestClient, params):
    response = _search(client, sort="location", **params)
    assert response.status_code == 200
    assert response.json() == {"total": 0, "results": []}


def test_search_without_location_is_unchanged(client: TestClient):
    # No location filter: every published feed, including the one that was never geolocated (ld-10).
    body = SearchFeeds200Response.model_validate(_search(client).json())
    assert body.total == 12
    assert "ld-10" in _feed_ids(body)


@pytest.mark.parametrize("params", [{}, {"location_path": " "}])
def test_search_location_sort_requires_location(client: TestClient, params):
    response = _search(client, sort="location", **params)
    assert response.status_code == 400
    assert response.json()["detail"] == search_location_sort_requires_location


def test_search_rejects_unknown_sort(client: TestClient):
    response = _search(client, sort="provider")
    assert response.status_code == 400
    assert response.json()["detail"] == search_sort_unsupported.format("provider")


def test_search_continent_parameter_is_removed(client: TestClient):
    # The continent parameter is ignored: continents are filtered by their location id.
    body = SearchFeeds200Response.model_validate(_search(client, continent="europe").json())
    assert body.total == 12
