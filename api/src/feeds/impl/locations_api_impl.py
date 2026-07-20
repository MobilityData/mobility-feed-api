import re

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from feeds_gen.apis.locations_api_base import BaseLocationsApi
from feeds_gen.models.location_search_response import LocationSearchResponse
from feeds_gen.models.location_search_result import LocationSearchResult
from shared.database.database import with_db_session
from shared.database.sql_functions.unaccent import unaccent
from shared.database_gen.sqlacodegen_models import t_geopolygonlocationsearch as location_search


def _to_prefix_tsquery(search_query: str) -> str | None:
    # Full-text search matches whole lexemes, so turn each word into a prefix
    # term ("mon" -> "mon:*") to support typeahead-style matching.
    tokens = re.findall(r"\w+", search_query, flags=re.UNICODE)
    if not tokens:
        return None
    return " & ".join(f"{token}:*" for token in tokens)


def _ts_query(search_query: str):
    return func.to_tsquery("english", unaccent(_to_prefix_tsquery(search_query)))


def _normalize_search_query(search_query: str | None) -> str | None:
    if search_query is None or len(search_query.strip()) == 0:
        return None
    if _to_prefix_tsquery(search_query) is None:
        return None
    return search_query.strip()


def _normalize_location_code(location_code: str | None) -> str | None:
    if location_code is None or len(location_code.strip()) == 0:
        return None
    return location_code.strip().upper()


def _build_locations_conditions(
    search_query: str | None,
    country_code: str | None,
    subdivision_code: str | None,
    location_type: str | None,
):
    normalized_query = _normalize_search_query(search_query)
    normalized_country = _normalize_location_code(country_code)
    normalized_subdivision = _normalize_location_code(subdivision_code)
    conditions = []
    if normalized_query is not None:
        conditions.append(location_search.c.document.op("@@")(_ts_query(normalized_query)))
    if normalized_country is not None:
        conditions.append(location_search.c.country_code == normalized_country)
    if normalized_subdivision is not None:
        conditions.append(location_search.c.subdivision_code == normalized_subdivision)
    if location_type is not None:
        conditions.append(location_search.c.location_type == location_type)
    return conditions, normalized_query


def _location_from_row(row) -> LocationSearchResult:
    return LocationSearchResult(
        location_id=row["osm_id"],
        parent_location_id=row["parent_osm_id"],
        name=row["name"],
        alt_name=row["alt_name"],
        location_type=row["location_type"],
        country_name=row["country_name"],
        country_code=row["country_code"],
        subdivision_name=row["subdivision_name"],
        subdivision_code=row["subdivision_code"],
        path_names=row["path_names"] or [],
        display_name=row["display_name"],
    )


class LocationsApiImpl(BaseLocationsApi):
    """This class represents the implementation of the `/locations` endpoints."""

    @with_db_session
    def get_locations(
        self,
        limit: int,
        offset: int,
        search_query: str,
        country_code: str,
        subdivision_code: str,
        location_type: str,
        db_session: Session,
    ) -> LocationSearchResponse:
        """Search locations from the geopolygon materialized read model."""
        conditions, normalized_query = _build_locations_conditions(
            search_query, country_code, subdivision_code, location_type
        )

        count_query = select(func.count(location_search.c.osm_id))
        if conditions:
            count_query = count_query.where(and_(*conditions))
        total = db_session.execute(count_query).scalar_one()

        locations_query = select(
            location_search.c.osm_id,
            location_search.c.parent_osm_id,
            location_search.c.name,
            location_search.c.alt_name,
            location_search.c.location_type,
            location_search.c.country_name,
            location_search.c.country_code,
            location_search.c.subdivision_name,
            location_search.c.subdivision_code,
            location_search.c.path_names,
            location_search.c.display_name,
        )
        if conditions:
            locations_query = locations_query.where(and_(*conditions))
        if normalized_query is not None:
            locations_query = locations_query.order_by(
                location_search.c.admin_level.asc(),
                func.ts_rank(location_search.c.document, _ts_query(normalized_query)).desc(),
                location_search.c.display_name.asc(),
            )
        else:
            locations_query = locations_query.order_by(
                location_search.c.admin_level.asc(),
                location_search.c.display_name.asc(),
            )
        locations_query = locations_query.limit(limit).offset(offset)

        rows = db_session.execute(locations_query).mappings().all()
        return LocationSearchResponse(
            total=total,
            results=[_location_from_row(row) for row in rows],
        )
