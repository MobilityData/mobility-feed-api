import re
from typing import Final, List, Optional

from sqlalchemy import Integer, String, Text, and_, cast, func, literal, null, select, union_all
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.orm import Session

from feeds.impl.error_handling import (
    locations_include_unsupported,
    locations_sort_unsupported,
    raise_http_error,
)
from feeds.impl.location_feeds import LOCATION_TYPE_CONTINENT, clean_param, resolve_continent_code
from feeds_gen.apis.locations_api_base import BaseLocationsApi
from feeds_gen.models.location_feed_counts import LocationFeedCounts
from feeds_gen.models.location_search_response import LocationSearchResponse
from middleware.request_context import is_user_email_restricted
from shared.database.database import with_db_session
from shared.database.sql_functions.unaccent import unaccent
from shared.database_gen.sqlacodegen_models import (
    Continent,
    t_geopolygonlocationsearch as location_search,
    t_locationfeedcount as location_feed_count,
)
from shared.db_models.location_search_result_impl import LocationSearchResultImpl

SORT_BY_ADMIN_LEVEL: Final = "admin_level"
SORT_BY_FEED_COUNT: Final = "feed_count"
SORTS: Final = (SORT_BY_ADMIN_LEVEL, SORT_BY_FEED_COUNT)

INCLUDE_FEED_COUNTS: Final = "feed_counts"
INCLUDES: Final = (INCLUDE_FEED_COUNTS,)


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


def _parse_sort(sort: Optional[str]) -> str:
    """The sort order, `admin_level` by default. Raises a 400 error for an unsupported value."""
    sort = clean_param(sort) or SORT_BY_ADMIN_LEVEL
    if sort not in SORTS:
        raise_http_error(400, locations_sort_unsupported.format(sort))
    return sort


def _parse_include(include: Optional[List[str]]) -> set:
    """The `include` values, given comma-separated or as repeated parameters. Raises a 400 error for an unsupported
    value."""
    values = {value.strip() for item in include or [] for value in item.split(",") if value.strip()}
    for value in sorted(values):
        if value not in INCLUDES:
            raise_http_error(
                400, locations_include_unsupported.format(value, ", ".join(f"'{name}'" for name in INCLUDES))
            )
    return values


def _counts_of(counts, published_only: bool, *conditions):
    """The join condition of the precomputed feed counts, for the caller's visibility."""
    return and_(counts.c.published_only == published_only, *conditions)


def _place_rows(published_only: bool):
    """The OSM areas of the read model, with their feed counts (NULL without any counted feed)."""
    counts = location_feed_count.alias("place_feed_count")
    return select(
        location_search.c.osm_id,
        location_search.c.parent_osm_id,
        location_search.c.name,
        location_search.c.alt_name,
        location_search.c.location_type,
        location_search.c.admin_level,
        location_search.c.continent_code,
        location_search.c.slug,
        location_search.c.path_slugs,
        location_search.c.country_name,
        location_search.c.country_code,
        location_search.c.subdivision_name,
        location_search.c.subdivision_code,
        location_search.c.path_names,
        location_search.c.display_name,
        location_search.c.document,
        counts.c.gtfs,
        counts.c.gtfs_rt,
        counts.c.gbfs,
        counts.c.total,
    ).select_from(
        location_search.outerjoin(
            counts, _counts_of(counts, published_only, counts.c.osm_id == location_search.c.osm_id)
        )
    )


def _continent_rows(published_only: bool):
    """The continents, from the continent table, shaped like the rows of the read model: no OSM id, no parent, admin
    level 0 so that they sort before the countries."""
    counts = location_feed_count.alias("continent_feed_count")
    return select(
        cast(null(), Integer).label("osm_id"),
        cast(null(), Integer).label("parent_osm_id"),
        cast(Continent.name, String(255)).label("name"),
        cast(null(), String(255)).label("alt_name"),
        cast(literal(LOCATION_TYPE_CONTINENT), Text).label("location_type"),
        literal(0).label("admin_level"),
        Continent.code.label("continent_code"),
        cast(Continent.slug, Text).label("slug"),
        array([cast(Continent.slug, Text)]).label("path_slugs"),
        cast(null(), String(255)).label("country_name"),
        cast(null(), String(3)).label("country_code"),
        cast(null(), String(255)).label("subdivision_name"),
        cast(null(), String(8)).label("subdivision_code"),
        array([cast(Continent.name, String)]).label("path_names"),
        cast(Continent.name, Text).label("display_name"),
        func.to_tsvector("english", unaccent(Continent.name)).label("document"),
        counts.c.gtfs,
        counts.c.gtfs_rt,
        counts.c.gbfs,
        counts.c.total,
    ).select_from(
        Continent.__table__.outerjoin(
            counts,
            _counts_of(counts, published_only, counts.c.continent_code == Continent.code, counts.c.osm_id.is_(None)),
        )
    )


def _feed_counts(row=None) -> LocationFeedCounts:
    """The feed counts of a row carrying the `gtfs`, `gtfs_rt`, `gbfs` and `total` columns, 0 when missing."""
    return LocationFeedCounts(
        gtfs=getattr(row, "gtfs", None) or 0,
        gtfs_rt=getattr(row, "gtfs_rt", None) or 0,
        gbfs=getattr(row, "gbfs", None) or 0,
        total=getattr(row, "total", None) or 0,
    )


def _location_order(locations, sort: str, normalized_query: Optional[str]) -> list:
    """The ORDER BY of a locations page, with deterministic tiebreakers for stable pagination (a continent has no OSM
    id, its code tells it apart)."""
    tiebreakers = [locations.c.display_name.asc(), locations.c.osm_id.asc(), locations.c.continent_code.asc()]
    if sort == SORT_BY_FEED_COUNT:
        return [func.coalesce(locations.c.total, 0).desc(), *tiebreakers]
    if normalized_query is not None:
        return [
            locations.c.admin_level.asc(),
            func.ts_rank(locations.c.document, _ts_query(normalized_query)).desc(),
            *tiebreakers,
        ]
    return [locations.c.admin_level.asc(), *tiebreakers]


class LocationsApiImpl(BaseLocationsApi):
    """This class represents the implementation of the `/locations` endpoints."""

    @with_db_session
    def get_locations(
        self,
        limit: int,
        offset: int,
        search_query: Optional[str],
        location_id: Optional[int],
        parent_location_id: Optional[int],
        continent: Optional[str],
        country_code: Optional[str],
        subdivision_code: Optional[str],
        location_type: Optional[str],
        has_feeds: Optional[bool],
        include: Optional[List[str]],
        sort: Optional[str],
        db_session: Session,
    ) -> LocationSearchResponse:
        """Search and filter locations: the OSM areas of the geopolygon read model, and the continents."""
        sort = _parse_sort(sort)
        with_feed_counts = INCLUDE_FEED_COUNTS in _parse_include(include)
        continent_code = None
        if (continent := clean_param(continent)) is not None:
            continent_code = resolve_continent_code(db_session, continent)
            if continent_code is None:
                return LocationSearchResponse(total=0, results=[])
        normalized_query = _normalize_search_query(search_query)
        normalized_country = _normalize_location_code(country_code)
        normalized_subdivision = _normalize_location_code(subdivision_code)
        location_type = clean_param(location_type)

        # Continents have no id, parent, country or subdivision: they can only match the other filters.
        place_only_filter = any(
            value is not None for value in (location_id, parent_location_id, normalized_country, normalized_subdivision)
        )
        published_only = is_user_email_restricted()
        branches = []
        if location_type != LOCATION_TYPE_CONTINENT:
            branches.append(_place_rows(published_only))
        if location_type in (None, LOCATION_TYPE_CONTINENT) and not place_only_filter:
            branches.append(_continent_rows(published_only))
        if not branches:
            return LocationSearchResponse(total=0, results=[])
        locations = (union_all(*branches) if len(branches) > 1 else branches[0]).subquery("locations")

        conditions = []
        if normalized_query is not None:
            conditions.append(locations.c.document.op("@@")(_ts_query(normalized_query)))
        if location_id is not None:
            conditions.append(locations.c.osm_id == location_id)
        if parent_location_id is not None:
            conditions.append(locations.c.parent_osm_id == parent_location_id)
        if continent_code is not None:
            # A continent's own code matches, so the continent is included.
            conditions.append(locations.c.continent_code == continent_code)
        if normalized_country is not None:
            conditions.append(locations.c.country_code == normalized_country)
        if normalized_subdivision is not None:
            conditions.append(locations.c.subdivision_code == normalized_subdivision)
        if location_type is not None:
            conditions.append(locations.c.location_type == location_type)
        if has_feeds:
            # A location without any counted feed has no counts row.
            conditions.append(locations.c.total > 0)

        rows = db_session.execute(
            select(locations, func.count().over().label("matching_locations"))
            .where(*conditions)
            .order_by(*_location_order(locations, sort, normalized_query))
            .limit(limit)
            .offset(offset)
        ).all()
        if rows:
            total = rows[0].matching_locations
        elif offset > 0 or limit == 0:
            # A page past the last one, or an empty page (limit=0), has no row to carry the window count.
            total = db_session.execute(select(func.count()).select_from(locations).where(*conditions)).scalar_one()
        else:
            total = 0
        return LocationSearchResponse(
            total=total,
            results=[
                LocationSearchResultImpl.from_orm(row, feed_counts=_feed_counts(row) if with_feed_counts else None)
                for row in rows
            ],
        )
