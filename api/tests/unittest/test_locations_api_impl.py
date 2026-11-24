from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from feeds.impl.error_handling import locations_include_unsupported, locations_sort_unsupported
from feeds.impl.location_feeds import continent_groups, location_groups
from feeds.impl.locations_api_impl import (
    LocationsApiImpl,
    _normalize_location_code,
    _normalize_search_query,
    _parse_include,
    _parse_sort,
    _to_prefix_tsquery,
)
from feeds_gen.models.location_feed_counts import LocationFeedCounts
from feeds_gen.models.location_search_response import LocationSearchResponse
from feeds_gen.models.location_search_result import LocationSearchResult
from shared.db_models.location_search_result_impl import LocationSearchResultImpl


def test_to_prefix_tsquery_single_word():
    assert _to_prefix_tsquery("mon") == "mon:*"


def test_to_prefix_tsquery_multiple_words_are_anded():
    assert _to_prefix_tsquery("los angeles") == "los:* & angeles:*"


def test_to_prefix_tsquery_strips_operator_characters():
    # tsquery operators embedded in user input must not leak into the query.
    assert _to_prefix_tsquery("a & b | c") == "a:* & b:* & c:*"


def test_to_prefix_tsquery_returns_none_without_word_characters():
    assert _to_prefix_tsquery("!!!") is None
    assert _to_prefix_tsquery("") is None


def test_normalize_search_query():
    assert _normalize_search_query(None) is None
    assert _normalize_search_query("   ") is None
    assert _normalize_search_query("!!!") is None
    assert _normalize_search_query("  montreal ") == "montreal"


def test_normalize_location_code_trims_and_uppercases():
    assert _normalize_location_code(None) is None
    assert _normalize_location_code("  ") is None
    assert _normalize_location_code(" ca ") == "CA"
    assert _normalize_location_code("ca-qc") == "CA-QC"


def test_parse_sort():
    assert _parse_sort(None) == "admin_level"
    assert _parse_sort(" feed_count ") == "feed_count"
    with pytest.raises(HTTPException) as error:
        _parse_sort("name")
    assert error.value.status_code == 400
    assert error.value.detail == locations_sort_unsupported.format("name")


def test_parse_include_accepts_comma_separated_and_repeated_values():
    assert _parse_include(None) == set()
    assert _parse_include(["feed_counts"]) == {"feed_counts"}
    assert _parse_include(["feed_counts, feed_counts", "feed_counts"]) == {"feed_counts"}
    assert _parse_include([" , "]) == set()


def test_parse_include_rejects_unsupported_values():
    with pytest.raises(HTTPException) as error:
        _parse_include(["feed_counts,children"])
    assert error.value.status_code == 400
    assert error.value.detail == locations_include_unsupported.format("children", "'feed_counts'")


def test_location_groups_include_the_other_boundaries_of_a_country():
    # The groups of the location, and of the geopolygons sharing its ISO 3166-1 code, if any.
    sql = str(location_groups(30))
    assert "osmlocationgroupgeopolygon.osm_id = " in sql
    assert "geopolygon.iso_3166_1_code" in sql


def test_continent_groups_are_the_groups_of_its_countries():
    sql = str(continent_groups("NA"))
    assert "country_continent.continent_code" in sql
    assert "geopolygon.iso_3166_1_code" in sql


def _row(**fields):
    """A locations row: Montréal unless overridden."""
    values = dict(
        osm_id=1634158,
        parent_osm_id=8508277,
        name="Montreal",
        alt_name=None,
        location_type="municipality",
        country_name="Canada",
        country_code="CA",
        subdivision_name="Quebec",
        subdivision_code="CA-QC",
        path_names=["Canada", "Quebec", "Montreal"],
        display_name="Canada, Quebec, Montreal",
        continent_code="NA",
        slug="1634158-montreal",
        path_slugs=["ca", "61549-quebec", "1634158-montreal"],
        gtfs=None,
        gtfs_rt=None,
        gbfs=None,
        total=None,
        matching_locations=1,
    )
    values.update(fields)
    return SimpleNamespace(**values)


def _continent_row(**fields):
    return _row(
        osm_id=None,
        parent_osm_id=None,
        name="North America",
        location_type="continent",
        country_name=None,
        country_code=None,
        subdivision_name=None,
        subdivision_code=None,
        path_names=["North America"],
        display_name="North America",
        slug="north-america",
        path_slugs=["north-america"],
        **fields,
    )


def test_location_from_row_maps_fields():
    result = LocationSearchResultImpl.from_orm(_row())
    assert isinstance(result, LocationSearchResult)
    assert result.location_id == 1634158
    assert result.parent_location_id == 8508277
    assert result.country_code == "CA"
    assert result.subdivision_code == "CA-QC"
    assert result.continent_code == "NA"
    assert result.path_names == ["Canada", "Quebec", "Montreal"]
    assert result.slug == "1634158-montreal"
    assert result.path_slugs == ["ca", "61549-quebec", "1634158-montreal"]
    assert result.feed_counts is None


def test_location_from_continent_row():
    counts = LocationFeedCounts(gtfs=1, gtfs_rt=0, gbfs=0, total=1)
    result = LocationSearchResultImpl.from_orm(_continent_row(), feed_counts=counts)
    assert (result.location_id, result.parent_location_id, result.location_type) == (None, None, "continent")
    assert (result.name, result.slug, result.display_name, result.continent_code) == (
        "North America",
        "north-america",
        "North America",
        "NA",
    )
    assert result.path_slugs == ["north-america"]
    assert result.path_names == ["North America"]
    assert result.country_code is None
    assert result.feed_counts == counts


def test_location_from_row_defaults_missing_paths_to_empty_lists():
    result = LocationSearchResultImpl.from_orm(_row(path_names=None, path_slugs=None))
    assert result.path_names == []
    assert result.path_slugs == []


def test_location_from_row_returns_none_for_none_row():
    assert LocationSearchResultImpl.from_orm(None) is None


def _result(value=None, rows=None):
    """A mocked result of session.execute()."""
    result = MagicMock()
    result.scalar_one.return_value = value
    result.scalar_one_or_none.return_value = value
    result.all.return_value = rows or []
    return result


def _mock_session(*results):
    session = MagicMock()
    session.execute.side_effect = list(results)
    return session


@pytest.fixture(autouse=True)
def restricted_user(monkeypatch):
    # No request context here: the feed visibility rule is evaluated outside of a request.
    monkeypatch.setattr("feeds.impl.locations_api_impl.is_user_email_restricted", lambda: True)


def _get_locations(session, **params):
    values = dict(
        limit=10,
        offset=0,
        search_query=None,
        location_id=None,
        parent_location_id=None,
        continent=None,
        country_code=None,
        subdivision_code=None,
        location_type=None,
        has_feeds=False,
        include=None,
        sort=None,
    )
    values.update(params)
    return LocationsApiImpl().get_locations(**values, db_session=session)


def test_get_locations_returns_total_and_results_in_one_query():
    session = _mock_session(_result(rows=[_row(matching_locations=17)]))

    response = _get_locations(session, search_query="montreal", subdivision_code="CA-QC")

    assert isinstance(response, LocationSearchResponse)
    assert response.total == 17
    assert len(response.results) == 1
    assert response.results[0].location_id == 1634158
    assert response.results[0].feed_counts is None
    # total is serialized before results.
    assert list(response.model_dump().keys())[0] == "total"
    assert session.execute.call_count == 1


def test_get_locations_empty_first_page():
    session = _mock_session(_result(rows=[]))
    response = _get_locations(session)
    assert (response.total, response.results) == (0, [])
    assert session.execute.call_count == 1


def test_get_locations_counts_the_total_of_a_page_past_the_last_one():
    session = _mock_session(_result(rows=[]), _result(5))
    response = _get_locations(session, offset=20)
    assert (response.total, response.results) == (5, [])
    assert session.execute.call_count == 2


@pytest.mark.parametrize(
    "include, sort, detail",
    [
        (None, "name", locations_sort_unsupported.format("name")),
        (["children"], None, locations_include_unsupported.format("children", "'feed_counts'")),
    ],
)
def test_get_locations_rejects_unsupported_values(include, sort, detail):
    session = MagicMock()
    with pytest.raises(HTTPException) as error:
        _get_locations(session, include=include, sort=sort)
    assert error.value.status_code == 400
    assert error.value.detail == detail
    session.execute.assert_not_called()


def test_get_locations_unknown_continent_returns_no_result():
    session = _mock_session(_result(None))
    response = _get_locations(session, continent="atlantis")
    assert (response.total, response.results) == (0, [])
    # Only the continent lookup ran.
    assert session.execute.call_count == 1


def test_get_locations_continents_with_a_place_only_filter_returns_no_result():
    session = MagicMock()
    response = _get_locations(session, location_type="continent", parent_location_id=1)
    assert (response.total, response.results) == (0, [])
    session.execute.assert_not_called()


def test_get_locations_includes_the_precomputed_feed_counts():
    rows = [
        _continent_row(gtfs=2, gtfs_rt=1, gbfs=1, total=4, matching_locations=2),
        # A location without any counted feed has no counts row.
        _row(osm_id=2, name="Quebec", matching_locations=2),
    ]
    session = _mock_session(_result(rows=rows))

    response = _get_locations(session, include=["feed_counts"])

    assert [result.feed_counts for result in response.results] == [
        LocationFeedCounts(gtfs=2, gtfs_rt=1, gbfs=1, total=4),
        LocationFeedCounts(gtfs=0, gtfs_rt=0, gbfs=0, total=0),
    ]
    assert session.execute.call_count == 1
