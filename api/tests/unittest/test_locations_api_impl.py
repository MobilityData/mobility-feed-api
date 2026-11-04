from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from feeds.impl.error_handling import locations_sort_unsupported
from feeds.impl.locations_api_impl import (
    LocationsApiImpl,
    _build_locations_conditions,
    _normalize_location_code,
    _normalize_path,
    _normalize_search_query,
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


def test_normalize_path_trims_and_lowercases():
    assert _normalize_path(None) is None
    assert _normalize_path("  ") is None
    assert _normalize_path(" Canada/Quebec/Montreal ") == "canada/quebec/montreal"


def test_build_conditions_no_filters():
    conditions, normalized_query = _build_locations_conditions(None, None, None, None)
    assert conditions == []
    assert normalized_query is None


def test_build_conditions_all_filters():
    conditions, normalized_query = _build_locations_conditions("montreal", "ca", "ca-qc", "municipality")
    # search_query + country_code + subdivision_code + location_type
    assert len(conditions) == 4
    assert normalized_query == "montreal"


def test_build_conditions_location_filters():
    conditions, _ = _build_locations_conditions(None, None, None, None, "NA", 61549, "canada/quebec")
    # continent_code + parent_location_id + path
    assert len(conditions) == 3


def test_build_conditions_ignores_blank_search_query():
    conditions, normalized_query = _build_locations_conditions("   ", "CA", None, None)
    # Only the country filter remains; blank search query is dropped.
    assert len(conditions) == 1
    assert normalized_query is None


def test_location_from_row_maps_fields():
    row = SimpleNamespace(
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
        continent_slug="north-america",
        continent_name="North America",
        slug="montreal",
        path_slugs=["canada", "quebec", "montreal"],
    )
    result = LocationSearchResultImpl.from_orm(row)
    assert isinstance(result, LocationSearchResult)
    assert result.location_id == 1634158
    assert result.parent_location_id == 8508277
    assert result.country_code == "CA"
    assert result.subdivision_code == "CA-QC"
    assert result.path_names == ["Canada", "Quebec", "Montreal"]
    assert (result.continent_code, result.continent_slug, result.continent_name) == (
        "NA",
        "north-america",
        "North America",
    )
    assert result.slug == "montreal"
    assert result.path_slugs == ["canada", "quebec", "montreal"]
    assert result.feed_counts is None


def test_location_from_row_defaults_missing_path_names_to_empty_list():
    row = SimpleNamespace(
        osm_id=1,
        parent_osm_id=None,
        name="Canada",
        alt_name=None,
        location_type="country",
        country_name="Canada",
        country_code="CA",
        subdivision_name=None,
        subdivision_code=None,
        path_names=None,
        display_name="Canada",
        continent_code="NA",
        slug="canada",
        path_slugs=None,
    )
    result = LocationSearchResultImpl.from_orm(row)
    assert result.path_names == []
    assert result.path_slugs == []
    # Rows without the continent table columns.
    assert result.continent_slug is None


def test_location_from_row_returns_none_for_none_row():
    assert LocationSearchResultImpl.from_orm(None) is None


def _mock_session(total, rows):
    """Build a session whose two execute() calls return the count then the rows."""
    count_result = MagicMock()
    count_result.scalar_one.return_value = total

    rows_result = MagicMock()
    rows_result.all.return_value = rows

    session = MagicMock()
    session.execute.side_effect = [count_result, rows_result]
    return session


def test_get_locations_returns_total_and_results():
    rows = [
        SimpleNamespace(
            osm_id=8508277,
            parent_osm_id=61549,
            name="Urban agglomeration of Montreal",
            alt_name=None,
            location_type="municipality",
            country_name="Canada",
            country_code="CA",
            subdivision_name="Quebec",
            subdivision_code="CA-QC",
            path_names=["Canada", "Quebec", "Urban agglomeration of Montreal"],
            display_name="Canada, Quebec, Urban agglomeration of Montreal",
            continent_code="NA",
            continent_slug="north-america",
            continent_name="North America",
            slug="urban-agglomeration-of-montreal",
            path_slugs=["canada", "quebec", "urban-agglomeration-of-montreal"],
        )
    ]
    session = _mock_session(total=17, rows=rows)

    response = LocationsApiImpl().get_locations(
        5, 0, "montreal", None, "CA-QC", None, None, None, None, False, False, None, db_session=session
    )

    assert isinstance(response, LocationSearchResponse)
    assert response.total == 17
    assert len(response.results) == 1
    assert response.results[0].location_id == 8508277
    assert response.results[0].feed_counts is None
    # total is serialized before results.
    assert list(response.model_dump().keys())[0] == "total"
    assert session.execute.call_count == 2


def test_get_locations_empty_result():
    session = _mock_session(total=0, rows=[])
    response = LocationsApiImpl().get_locations(
        10, 0, None, None, None, None, None, None, None, False, False, None, db_session=session
    )
    assert response.total == 0
    assert response.results == []


def test_get_locations_rejects_unknown_sort():
    session = MagicMock()
    with pytest.raises(HTTPException) as error:
        LocationsApiImpl().get_locations(
            10, 0, None, None, None, None, None, None, None, False, False, "name", db_session=session
        )
    assert error.value.status_code == 400
    assert error.value.detail == locations_sort_unsupported.format("name")
    session.execute.assert_not_called()


def test_get_locations_unknown_continent_returns_no_result():
    continent_result = MagicMock()
    continent_result.scalar_one_or_none.return_value = None
    session = MagicMock()
    session.execute.return_value = continent_result

    response = LocationsApiImpl().get_locations(
        10, 0, None, None, None, None, "atlantis", None, None, False, False, None, db_session=session
    )
    assert response.total == 0
    assert response.results == []
    # Only the continent lookup ran.
    assert session.execute.call_count == 1


def test_get_continents_inside_a_location_returns_no_result():
    session = MagicMock()
    response = LocationsApiImpl().get_locations(
        10, 0, None, None, None, "continent", None, 61549, None, False, False, None, db_session=session
    )
    assert response.total == 0
    assert response.results == []
    session.execute.assert_not_called()


def test_get_locations_includes_feed_counts_of_the_page(monkeypatch):
    # No request context here: the feed visibility rule is evaluated outside of a request.
    monkeypatch.setattr("feeds.impl.location_feeds.is_user_email_restricted", lambda: True)
    rows = [
        SimpleNamespace(
            osm_id=osm_id,
            parent_osm_id=1,
            name=name,
            alt_name=None,
            location_type="subdivision",
            country_name="Canada",
            country_code="CA",
            subdivision_name=name,
            subdivision_code=None,
            path_names=["Canada", name],
            display_name=f"Canada, {name}",
            continent_code="NA",
            continent_slug="north-america",
            continent_name="North America",
            slug=name.lower(),
            path_slugs=["canada", name.lower()],
        )
        for osm_id, name in [(2, "Quebec"), (6, "Ontario")]
    ]
    session = _mock_session(total=2, rows=rows)
    counts_result = MagicMock()
    counts_result.all.return_value = [SimpleNamespace(osm_id=2, gtfs=2, gtfs_rt=1, gbfs=1, total=4)]
    session.execute.side_effect = [*session.execute.side_effect, counts_result]

    response = LocationsApiImpl().get_locations(
        10, 0, None, None, None, None, None, 1, None, False, True, None, db_session=session
    )
    assert [result.feed_counts for result in response.results] == [
        LocationFeedCounts(gtfs=2, gtfs_rt=1, gbfs=1, total=4),
        # A location without any counted feed.
        LocationFeedCounts(gtfs=0, gtfs_rt=0, gbfs=0, total=0),
    ]
    assert session.execute.call_count == 3


def test_location_from_continent_row():
    row = SimpleNamespace(code="EU", slug="europe", name="Europe")
    counts = LocationFeedCounts(gtfs=1, gtfs_rt=0, gbfs=0, total=1)
    result = LocationSearchResultImpl.from_continent(row, feed_counts=counts)
    assert result.location_id is None
    assert result.parent_location_id is None
    assert result.location_type == "continent"
    assert (result.continent_code, result.continent_slug, result.continent_name) == ("EU", "europe", "Europe")
    assert (result.name, result.slug, result.display_name) == ("Europe", "europe", "Europe")
    assert result.path_slugs == []
    assert result.path_names == []
    assert result.country_code is None
    assert result.feed_counts == counts
    assert LocationSearchResultImpl.from_continent(None) is None
