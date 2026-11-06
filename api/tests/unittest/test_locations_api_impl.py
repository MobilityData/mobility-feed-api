from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from feeds.impl.error_handling import (
    location_not_found,
    location_path_not_found,
    location_path_required,
    locations_include_unsupported,
    locations_sort_unsupported,
)
from feeds.impl.location_feeds import location_groups, normalize_path
from feeds.impl.locations_api_impl import (
    LocationsApiImpl,
    _build_locations_conditions,
    _normalize_location_code,
    _normalize_search_query,
    _parse_include,
    _parse_sort,
    _to_prefix_tsquery,
)
from feeds_gen.models.location_detail import LocationDetail
from feeds_gen.models.location_feed_counts import LocationFeedCounts
from feeds_gen.models.location_search_response import LocationSearchResponse
from feeds_gen.models.location_search_result import LocationSearchResult
from shared.db_models.location_detail_impl import LocationDetailImpl
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
    assert normalize_path(None) is None
    assert normalize_path("  ") is None
    assert normalize_path(" North-America/Canada/Quebec ") == "north-america/canada/quebec"


def test_normalize_path_ignores_leading_and_trailing_slashes():
    assert normalize_path("canada/quebec/") == "canada/quebec"
    assert normalize_path("/canada/quebec") == "canada/quebec"
    assert normalize_path(" /Canada/Quebec// ") == "canada/quebec"
    assert normalize_path("/") is None


def test_build_conditions_no_filters():
    conditions, normalized_query = _build_locations_conditions(None, None, None, None)
    assert conditions == []
    assert normalized_query is None


def test_build_conditions_all_filters():
    conditions, normalized_query = _build_locations_conditions("montreal", "ca", "ca-qc", "municipality")
    # search_query + country_code + subdivision_code + location_type
    assert len(conditions) == 4
    assert normalized_query == "montreal"


def test_build_conditions_continent_filter():
    conditions, _ = _build_locations_conditions(None, None, None, None, "NA")
    assert len(conditions) == 1


def test_parse_sort():
    assert _parse_sort(None) == "admin_level"
    assert _parse_sort(" feed_count ") == "feed_count"
    with pytest.raises(HTTPException) as error:
        _parse_sort("name")
    assert error.value.status_code == 400
    assert error.value.detail == locations_sort_unsupported.format("name")


def test_parse_include_accepts_comma_separated_and_repeated_values():
    assert _parse_include(None, ("feed_counts",)) == set()
    assert _parse_include(["feed_counts"], ("feed_counts",)) == {"feed_counts"}
    assert _parse_include(["feed_counts, children", "children"], ("feed_counts", "children")) == {
        "feed_counts",
        "children",
    }
    assert _parse_include([" , "], ("feed_counts",)) == set()


def test_parse_include_rejects_unsupported_values():
    with pytest.raises(HTTPException) as error:
        _parse_include(["feed_counts,children"], ("feed_counts",))
    assert error.value.status_code == 400
    assert error.value.detail == locations_include_unsupported.format("children", "'feed_counts'")


def test_location_groups_of_a_continent_are_the_groups_of_its_countries():
    place = str(location_groups(4))
    continent = str(location_groups(-5))
    assert "continent_country" not in place
    assert "continent_country" in continent


def test_build_conditions_ignores_blank_search_query():
    conditions, normalized_query = _build_locations_conditions("   ", "CA", None, None)
    # Only the country filter remains; blank search query is dropped.
    assert len(conditions) == 1
    assert normalized_query is None


def _row(**fields):
    """A row of the geopolygon location search read model: Montréal unless overridden."""
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
        path_names=["North America", "Canada", "Quebec", "Montreal"],
        display_name="Canada, Quebec, Montreal",
        continent_code="NA",
        slug="montreal",
        path="north-america/canada/quebec/montreal",
        path_slugs=["north-america", "canada", "quebec", "montreal"],
    )
    values.update(fields)
    return SimpleNamespace(**values)


def _continent_row():
    return _row(
        osm_id=-5,
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
        path="north-america",
        path_slugs=["north-america"],
    )


def test_location_from_row_maps_fields():
    result = LocationSearchResultImpl.from_orm(_row())
    assert isinstance(result, LocationSearchResult)
    assert result.location_id == 1634158
    assert result.parent_location_id == 8508277
    assert result.country_code == "CA"
    assert result.subdivision_code == "CA-QC"
    assert result.continent_code == "NA"
    assert result.path_names == ["North America", "Canada", "Quebec", "Montreal"]
    assert result.slug == "montreal"
    assert result.path == "north-america/canada/quebec/montreal"
    assert result.path_slugs == ["north-america", "canada", "quebec", "montreal"]
    assert result.feed_counts is None


def test_location_from_continent_row():
    counts = LocationFeedCounts(gtfs=1, gtfs_rt=0, gbfs=0, total=1)
    result = LocationSearchResultImpl.from_orm(_continent_row(), feed_counts=counts)
    assert (result.location_id, result.parent_location_id, result.location_type) == (-5, None, "continent")
    assert (result.name, result.slug, result.path, result.display_name) == (
        "North America",
        "north-america",
        "north-america",
        "North America",
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
    assert LocationDetailImpl.from_orm(None) is None


def test_location_detail_from_row():
    children = LocationSearchResponse(total=1, results=[LocationSearchResultImpl.from_orm(_row())])
    result = LocationDetailImpl.from_orm(_continent_row(), children=children)
    assert isinstance(result, LocationDetail)
    assert result.location_id == -5
    assert result.children.total == 1
    assert result.children.results[0].location_id == 1634158
    assert LocationDetailImpl.from_orm(_continent_row()).children is None


def _result(value=None, rows=None):
    """A mocked result of session.execute()."""
    result = MagicMock()
    result.scalar_one.return_value = value
    result.scalar_one_or_none.return_value = value
    result.one_or_none.return_value = value
    result.all.return_value = rows or []
    return result


def _mock_session(*results):
    session = MagicMock()
    session.execute.side_effect = list(results)
    return session


@pytest.fixture
def restricted_user(monkeypatch):
    # No request context here: the feed visibility rule is evaluated outside of a request.
    monkeypatch.setattr("feeds.impl.location_feeds.is_user_email_restricted", lambda: True)


def test_get_locations_returns_total_and_results():
    session = _mock_session(_result(17), _result(rows=[_row()]))

    response = LocationsApiImpl().get_locations(
        5, 0, "montreal", None, None, "CA-QC", None, False, None, None, db_session=session
    )

    assert isinstance(response, LocationSearchResponse)
    assert response.total == 17
    assert len(response.results) == 1
    assert response.results[0].location_id == 1634158
    assert response.results[0].feed_counts is None
    # total is serialized before results.
    assert list(response.model_dump().keys())[0] == "total"
    assert session.execute.call_count == 2


def test_get_locations_empty_result():
    session = _mock_session(_result(0), _result(rows=[]))
    response = LocationsApiImpl().get_locations(
        10, 0, None, None, None, None, None, False, None, None, db_session=session
    )
    assert response.total == 0
    assert response.results == []


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
        LocationsApiImpl().get_locations(10, 0, None, None, None, None, None, False, include, sort, db_session=session)
    assert error.value.status_code == 400
    assert error.value.detail == detail
    session.execute.assert_not_called()


def test_get_locations_unknown_continent_returns_no_result():
    session = _mock_session(_result(None))
    response = LocationsApiImpl().get_locations(
        10, 0, None, "atlantis", None, None, None, False, None, None, db_session=session
    )
    assert response.total == 0
    assert response.results == []
    # Only the continent lookup ran.
    assert session.execute.call_count == 1


def test_get_locations_includes_feed_counts_of_the_page(restricted_user):
    rows = [_continent_row(), _row(osm_id=2, name="Quebec")]
    counts = _result(rows=[SimpleNamespace(osm_id=-5, gtfs=2, gtfs_rt=1, gbfs=1, total=4)])
    session = _mock_session(_result(2), _result(rows=rows), counts)

    response = LocationsApiImpl().get_locations(
        10, 0, None, None, None, None, None, False, ["feed_counts"], None, db_session=session
    )
    assert [result.feed_counts for result in response.results] == [
        LocationFeedCounts(gtfs=2, gtfs_rt=1, gbfs=1, total=4),
        # A location without any counted feed.
        LocationFeedCounts(gtfs=0, gtfs_rt=0, gbfs=0, total=0),
    ]
    assert session.execute.call_count == 3


def test_get_locations_sorted_by_feed_count_counts_in_the_same_query(restricted_user):
    rows = [SimpleNamespace(**vars(_row()), gtfs=1, gtfs_rt=0, gbfs=0, total=1)]
    session = _mock_session(_result(1), _result(rows=rows))
    response = LocationsApiImpl().get_locations(
        10, 0, None, None, None, None, None, True, ["feed_counts"], "feed_count", db_session=session
    )
    assert response.results[0].feed_counts == LocationFeedCounts(gtfs=1, gtfs_rt=0, gbfs=0, total=1)
    assert session.execute.call_count == 2


def test_get_location_without_children():
    session = _mock_session(_result(_continent_row()))
    response = LocationsApiImpl().get_location(-5, None, False, None, 100, 0, db_session=session)
    assert isinstance(response, LocationDetail)
    assert response.location_id == -5
    assert response.feed_counts is None
    assert response.children is None
    assert session.execute.call_count == 1


def test_get_location_with_children_and_feed_counts(restricted_user):
    session = _mock_session(
        _result(_continent_row()),
        _result(rows=[SimpleNamespace(osm_id=-5, gtfs=1, gtfs_rt=0, gbfs=0, total=1)]),
        _result(1),
        _result(rows=[_row(osm_id=1, parent_osm_id=-5, name="Canada", location_type="country")]),
        _result(rows=[]),
    )
    response = LocationsApiImpl().get_location(-5, ["feed_counts,children"], True, None, 10, 0, db_session=session)
    assert response.feed_counts == LocationFeedCounts(gtfs=1, gtfs_rt=0, gbfs=0, total=1)
    assert response.children.total == 1
    assert response.children.results[0].location_id == 1
    assert response.children.results[0].feed_counts == LocationFeedCounts(gtfs=0, gtfs_rt=0, gbfs=0, total=0)


def test_get_location_unknown_id():
    session = _mock_session(_result(None))
    with pytest.raises(HTTPException) as error:
        LocationsApiImpl().get_location(999, None, False, None, 100, 0, db_session=session)
    assert error.value.status_code == 404
    assert error.value.detail == location_not_found.format(999)


@pytest.mark.parametrize("include", [["parents"], ["children,parents"]])
def test_get_location_rejects_unsupported_include(include):
    session = MagicMock()
    with pytest.raises(HTTPException) as error:
        LocationsApiImpl().get_location(1, include, False, None, 100, 0, db_session=session)
    assert error.value.status_code == 400
    assert error.value.detail == locations_include_unsupported.format("parents", "'feed_counts', 'children'")
    session.execute.assert_not_called()


def test_get_location_by_path():
    session = _mock_session(_result(_row()))
    response = LocationsApiImpl().get_location_by_path(
        "/North-America/Canada/Quebec/Montreal/", None, False, None, 100, 0, db_session=session
    )
    assert response.location_id == 1634158


@pytest.mark.parametrize("path", [None, "", " / "])
def test_get_location_by_path_requires_a_path(path):
    session = MagicMock()
    with pytest.raises(HTTPException) as error:
        LocationsApiImpl().get_location_by_path(path, None, False, None, 100, 0, db_session=session)
    assert error.value.status_code == 400
    assert error.value.detail == location_path_required
    session.execute.assert_not_called()


def test_get_location_by_unknown_path():
    session = _mock_session(_result(None))
    with pytest.raises(HTTPException) as error:
        LocationsApiImpl().get_location_by_path("Atlantis/", None, False, None, 100, 0, db_session=session)
    assert error.value.status_code == 404
    assert error.value.detail == location_path_not_found.format("atlantis")


def test_get_location_children():
    session = _mock_session(_result(-5), _result(1), _result(rows=[_row(osm_id=1, parent_osm_id=-5)]))
    response = LocationsApiImpl().get_location_children(-5, 10, 0, False, None, None, db_session=session)
    assert response.total == 1
    assert response.results[0].parent_location_id == -5
    assert response.results[0].feed_counts is None


def test_get_location_children_of_unknown_location():
    session = _mock_session(_result(None))
    with pytest.raises(HTTPException) as error:
        LocationsApiImpl().get_location_children(999, 10, 0, False, None, None, db_session=session)
    assert error.value.status_code == 404
    assert error.value.detail == location_not_found.format(999)


def test_get_location_children_rejects_children_include():
    session = MagicMock()
    with pytest.raises(HTTPException) as error:
        LocationsApiImpl().get_location_children(1, 10, 0, False, ["children"], None, db_session=session)
    assert error.value.status_code == 400
    session.execute.assert_not_called()
