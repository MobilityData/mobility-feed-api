from fastapi import APIRouter, Query, Security
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from feeds_gen.models.extra_models import TokenModel
from feeds_gen.security_api import get_token_Authentication
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import t_geopolygonlocationsearch as location_search

router = APIRouter()


class LocationSearchResult(BaseModel):
    location_id: int
    parent_location_id: int | None = None
    name: str | None = None
    alt_name: str | None = None
    location_type: str
    country_name: str | None = None
    country_code: str | None = None
    subdivision_name: str | None = None
    subdivision_code: str | None = None
    path_names: list[str] = Field(default_factory=list)
    display_name: str | None = None


class LocationsSearchResponse(BaseModel):
    results: list[LocationSearchResult]
    total: int


def _normalize_search_query(search_query: str | None) -> str | None:
    if search_query is None or len(search_query.strip()) == 0:
        return None
    return search_query.strip()


def _normalize_country_code(country_code: str | None) -> str | None:
    if country_code is None or len(country_code.strip()) == 0:
        return None
    return country_code.strip().upper()


def _build_locations_conditions(search_query: str | None, country_code: str | None, location_type: str | None):
    normalized_query = _normalize_search_query(search_query)
    normalized_country = _normalize_country_code(country_code)
    conditions = []
    if normalized_query is not None:
        conditions.append(location_search.c.document.op("@@")(_ts_query(normalized_query)))
    if normalized_country is not None:
        conditions.append(location_search.c.country_code == normalized_country)
    if location_type is not None:
        conditions.append(location_search.c.location_type == location_type)
    return conditions, normalized_query


def _ts_query(search_query: str):
    return func.plainto_tsquery("english", func.unaccent(search_query))


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


@with_db_session
def search_locations(
    limit: int,
    offset: int,
    search_query: str | None,
    country_code: str | None,
    location_type: str | None,
    db_session: Session,
) -> LocationsSearchResponse:
    conditions, normalized_query = _build_locations_conditions(search_query, country_code, location_type)

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
            func.ts_rank(location_search.c.document, _ts_query(normalized_query)).desc(),
            location_search.c.display_name.asc(),
        )
    else:
        locations_query = locations_query.order_by(location_search.c.display_name.asc())
    locations_query = locations_query.limit(limit).offset(offset)

    rows = db_session.execute(locations_query).mappings().all()
    return LocationsSearchResponse(
        results=[_location_from_row(row) for row in rows],
        total=total,
    )


@router.get(
    "/v1/locations",
    tags=["locations"],
    response_model=LocationsSearchResponse,
    response_model_by_alias=True,
)
def get_locations(
    limit: int = Query(100, description="The number of locations to return.", alias="limit", ge=0, le=3500),
    offset: int = Query(0, description="Offset of the first location to return.", alias="offset", ge=0),
    search_query: str = Query(None, description="Location search query.", alias="search_query"),
    country_code: str = Query(None, description="ISO 3166-1 alpha-2 country code.", alias="country_code"),
    location_type: str = Query(
        None,
        description="Location type to return: country, subdivision, or municipality.",
        alias="location_type",
        pattern="^(country|subdivision|municipality)$",
    ),
    token_Authentication: TokenModel = Security(get_token_Authentication),
) -> LocationsSearchResponse:
    """Search locations from the geopolygon materialized read model."""
    return search_locations(limit, offset, search_query, country_code, location_type)
