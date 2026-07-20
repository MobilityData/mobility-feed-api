from unittest.mock import MagicMock

from feeds.impl.locations_api_impl import (
    LocationsApiImpl,
    _build_locations_conditions,
    _location_from_row,
    _normalize_location_code,
    _normalize_search_query,
    _to_prefix_tsquery,
)
from feeds_gen.models.location_search_response import LocationSearchResponse
from feeds_gen.models.location_search_result import LocationSearchResult


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


def test_build_conditions_no_filters():
    conditions, normalized_query = _build_locations_conditions(None, None, None, None)
    assert conditions == []
    assert normalized_query is None


def test_build_conditions_all_filters():
    conditions, normalized_query = _build_locations_conditions("montreal", "ca", "ca-qc", "municipality")
    # search_query + country_code + subdivision_code + location_type
    assert len(conditions) == 4
    assert normalized_query == "montreal"


def test_build_conditions_ignores_blank_search_query():
    conditions, normalized_query = _build_locations_conditions("   ", "CA", None, None)
    # Only the country filter remains; blank search query is dropped.
    assert len(conditions) == 1
    assert normalized_query is None


def test_location_from_row_maps_fields():
    row = {
        "osm_id": 1634158,
        "parent_osm_id": 8508277,
        "name": "Montreal",
        "alt_name": None,
        "location_type": "municipality",
        "country_name": "Canada",
        "country_code": "CA",
        "subdivision_name": "Quebec",
        "subdivision_code": "CA-QC",
        "path_names": ["Canada", "Quebec", "Montreal"],
        "display_name": "Canada, Quebec, Montreal",
    }
    result = _location_from_row(row)
    assert isinstance(result, LocationSearchResult)
    assert result.location_id == 1634158
    assert result.parent_location_id == 8508277
    assert result.country_code == "CA"
    assert result.subdivision_code == "CA-QC"
    assert result.path_names == ["Canada", "Quebec", "Montreal"]


def test_location_from_row_defaults_missing_path_names_to_empty_list():
    row = {
        "osm_id": 1,
        "parent_osm_id": None,
        "name": "Canada",
        "alt_name": None,
        "location_type": "country",
        "country_name": "Canada",
        "country_code": "CA",
        "subdivision_name": None,
        "subdivision_code": None,
        "path_names": None,
        "display_name": "Canada",
    }
    result = _location_from_row(row)
    assert result.path_names == []


def _mock_session(total, rows):
    """Build a session whose two execute() calls return the count then the rows."""
    count_result = MagicMock()
    count_result.scalar_one.return_value = total

    rows_result = MagicMock()
    rows_result.mappings.return_value.all.return_value = rows

    session = MagicMock()
    session.execute.side_effect = [count_result, rows_result]
    return session


def test_get_locations_returns_total_and_results():
    rows = [
        {
            "osm_id": 8508277,
            "parent_osm_id": 61549,
            "name": "Urban agglomeration of Montreal",
            "alt_name": None,
            "location_type": "municipality",
            "country_name": "Canada",
            "country_code": "CA",
            "subdivision_name": "Quebec",
            "subdivision_code": "CA-QC",
            "path_names": ["Canada", "Quebec", "Urban agglomeration of Montreal"],
            "display_name": "Canada, Quebec, Urban agglomeration of Montreal",
        }
    ]
    session = _mock_session(total=17, rows=rows)

    response = LocationsApiImpl().get_locations(5, 0, "montreal", None, "CA-QC", None, db_session=session)

    assert isinstance(response, LocationSearchResponse)
    assert response.total == 17
    assert len(response.results) == 1
    assert response.results[0].location_id == 8508277
    # total is serialized before results.
    assert list(response.model_dump().keys())[0] == "total"
    assert session.execute.call_count == 2


def test_get_locations_empty_result():
    session = _mock_session(total=0, rows=[])
    response = LocationsApiImpl().get_locations(10, 0, None, None, None, None, db_session=session)
    assert response.total == 0
    assert response.results == []
