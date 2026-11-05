import re
from typing import Final, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from feeds.impl.error_handling import locations_sort_unsupported, raise_http_error
from feeds.impl.location_feeds import (
    clean_param,
    continent_feed_counts,
    has_counted_feeds,
    location_feed_counts,
    resolve_continent_code,
)
from feeds_gen.apis.locations_api_base import BaseLocationsApi
from feeds_gen.models.location_feed_counts import LocationFeedCounts
from feeds_gen.models.location_search_response import LocationSearchResponse
from shared.database.database import with_db_session
from shared.database.sql_functions.unaccent import unaccent
from shared.database_gen.sqlacodegen_models import Continent, t_geopolygonlocationsearch as location_search
from shared.db_models.location_search_result_impl import LOCATION_TYPE_CONTINENT, LocationSearchResultImpl

SORT_BY_ADMIN_LEVEL: Final = "admin_level"
SORT_BY_FEED_COUNT: Final = "feed_count"

_location_columns = [
    location_search.c.osm_id,
    location_search.c.parent_osm_id,
    location_search.c.name,
    location_search.c.alt_name,
    location_search.c.location_type,
    location_search.c.continent_code,
    Continent.slug.label("continent_slug"),
    Continent.name.label("continent_name"),
    location_search.c.slug,
    location_search.c.path_slugs,
    location_search.c.country_name,
    location_search.c.country_code,
    location_search.c.subdivision_name,
    location_search.c.subdivision_code,
    location_search.c.path_names,
    location_search.c.display_name,
]


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


def _normalize_path(path: str | None) -> str | None:
    # Leading and trailing slashes are ignored (`canada/quebec/` is `canada/quebec`), and slugs are lowercase, so
    # lowercasing the path makes the exact match case-insensitive. A path of only slashes is no path.
    path = clean_param(path)
    if path is None:
        return None
    return clean_param(path.strip("/").lower())


def _build_locations_conditions(
    search_query: str | None,
    country_code: str | None,
    subdivision_code: str | None,
    location_type: str | None,
    continent_code: str | None = None,
    parent_location_id: int | None = None,
    path: str | None = None,
):
    normalized_query = _normalize_search_query(search_query)
    normalized_country = _normalize_location_code(country_code)
    normalized_subdivision = _normalize_location_code(subdivision_code)
    normalized_path = _normalize_path(path)
    conditions = []
    if normalized_query is not None:
        conditions.append(location_search.c.document.op("@@")(_ts_query(normalized_query)))
    if normalized_country is not None:
        conditions.append(location_search.c.country_code == normalized_country)
    if normalized_subdivision is not None:
        conditions.append(location_search.c.subdivision_code == normalized_subdivision)
    if location_type is not None:
        conditions.append(location_search.c.location_type == location_type)
    if continent_code is not None:
        conditions.append(location_search.c.continent_code == continent_code)
    if parent_location_id is not None:
        conditions.append(location_search.c.parent_osm_id == parent_location_id)
    if normalized_path is not None:
        conditions.append(location_search.c.path == normalized_path)
    return conditions, normalized_query


def _feed_counts(row=None) -> LocationFeedCounts:
    """The feed counts of a row carrying the `gtfs`, `gtfs_rt`, `gbfs` and `total` columns, 0 when missing."""
    return LocationFeedCounts(
        gtfs=getattr(row, "gtfs", None) or 0,
        gtfs_rt=getattr(row, "gtfs_rt", None) or 0,
        gbfs=getattr(row, "gbfs", None) or 0,
        total=getattr(row, "total", None) or 0,
    )


def _empty_response() -> LocationSearchResponse:
    return LocationSearchResponse(total=0, results=[])


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
        continent: Optional[str],
        parent_location_id: Optional[int],
        path: Optional[str],
        has_feeds: Optional[bool],
        include_feed_counts: Optional[bool],
        sort: Optional[str],
        db_session: Session,
    ) -> LocationSearchResponse:
        """Search locations from the geopolygon materialized read model, or the continents."""
        sort = sort or SORT_BY_ADMIN_LEVEL
        if sort not in (SORT_BY_ADMIN_LEVEL, SORT_BY_FEED_COUNT):
            raise_http_error(400, locations_sort_unsupported.format(sort))
        continent_code = None
        if (continent := clean_param(continent)) is not None:
            continent_code = resolve_continent_code(db_session, continent)
            if continent_code is None:
                return _empty_response()

        if location_type == LOCATION_TYPE_CONTINENT:
            if any(
                value is not None
                for value in (
                    _normalize_location_code(country_code),
                    _normalize_location_code(subdivision_code),
                    parent_location_id,
                    _normalize_path(path),
                )
            ):
                # Continents are not contained in any location and have no path.
                return _empty_response()
            return self._get_continents(
                db_session, limit, offset, search_query, continent_code, has_feeds, include_feed_counts, sort
            )

        conditions, normalized_query = _build_locations_conditions(
            search_query, country_code, subdivision_code, location_type, continent_code, parent_location_id, path
        )
        if has_feeds:
            conditions.append(has_counted_feeds())

        count_query = select(func.count(location_search.c.osm_id))
        if conditions:
            count_query = count_query.where(and_(*conditions))
        total = db_session.execute(count_query).scalar_one()

        locations_query = select(*_location_columns).select_from(
            location_search.outerjoin(Continent, Continent.code == location_search.c.continent_code)
        )
        if conditions:
            locations_query = locations_query.where(and_(*conditions))
        counts = None
        if sort == SORT_BY_FEED_COUNT:
            # Count only the feeds of the filtered locations, before paginating.
            filtered_osm_ids = select(location_search.c.osm_id)
            if conditions:
                filtered_osm_ids = filtered_osm_ids.where(and_(*conditions))
            counts = location_feed_counts(filtered_osm_ids)
            locations_query = (
                locations_query.add_columns(counts.c.gtfs, counts.c.gtfs_rt, counts.c.gbfs, counts.c.total)
                .outerjoin(counts, counts.c.osm_id == location_search.c.osm_id)
                .order_by(
                    func.coalesce(counts.c.total, 0).desc(),
                    location_search.c.display_name.asc(),
                    location_search.c.osm_id.asc(),  # deterministic tiebreaker for stable pagination
                )
            )
        elif normalized_query is not None:
            locations_query = locations_query.order_by(
                location_search.c.admin_level.asc(),
                func.ts_rank(location_search.c.document, _ts_query(normalized_query)).desc(),
                location_search.c.display_name.asc(),
                location_search.c.osm_id.asc(),  # deterministic tiebreaker for stable pagination
            )
        else:
            locations_query = locations_query.order_by(
                location_search.c.admin_level.asc(),
                location_search.c.display_name.asc(),
                location_search.c.osm_id.asc(),  # deterministic tiebreaker for stable pagination
            )
        locations_query = locations_query.limit(limit).offset(offset)

        rows = db_session.execute(locations_query).all()
        feed_counts_by_osm_id = {}
        if include_feed_counts:
            if counts is not None:
                feed_counts_by_osm_id = {row.osm_id: _feed_counts(row) for row in rows}
            elif rows:
                # Count only the feeds of the returned page.
                page_counts = location_feed_counts([row.osm_id for row in rows])
                feed_counts_by_osm_id = {
                    row.osm_id: _feed_counts(row) for row in db_session.execute(select(page_counts)).all()
                }
        return LocationSearchResponse(
            total=total,
            results=[
                LocationSearchResultImpl.from_orm(
                    row,
                    feed_counts=(
                        (feed_counts_by_osm_id.get(row.osm_id) or _feed_counts()) if include_feed_counts else None
                    ),
                )
                for row in rows
            ],
        )

    @staticmethod
    def _get_continents(
        db_session: Session,
        limit: int,
        offset: int,
        search_query: Optional[str],
        continent_code: Optional[str],
        has_feeds: Optional[bool],
        include_feed_counts: Optional[bool],
        sort: str,
    ) -> LocationSearchResponse:
        """List the continents. `search_query` is matched against their name only, and the default sort is by name,
        as continents have no admin level."""
        conditions = []
        if continent_code is not None:
            conditions.append(Continent.code == continent_code)
        if (normalized_query := _normalize_search_query(search_query)) is not None:
            conditions.append(
                func.to_tsvector("english", unaccent(Continent.name)).op("@@")(_ts_query(normalized_query))
            )
        query = select(Continent.code, Continent.slug, Continent.name)
        counts = None
        if has_feeds or include_feed_counts or sort == SORT_BY_FEED_COUNT:
            counts = continent_feed_counts()
            query = query.add_columns(counts.c.gtfs, counts.c.gtfs_rt, counts.c.gbfs, counts.c.total).outerjoin(
                counts, counts.c.continent_code == Continent.code
            )
            if has_feeds:
                conditions.append(counts.c.total > 0)
        query = query.where(*conditions)

        total = db_session.execute(select(func.count()).select_from(query.subquery())).scalar_one()
        if sort == SORT_BY_FEED_COUNT:
            query = query.order_by(func.coalesce(counts.c.total, 0).desc(), Continent.name.asc(), Continent.code.asc())
        else:
            query = query.order_by(Continent.name.asc(), Continent.code.asc())
        rows = db_session.execute(query.limit(limit).offset(offset)).all()
        return LocationSearchResponse(
            total=total,
            results=[
                LocationSearchResultImpl.from_continent(
                    row, feed_counts=_feed_counts(row) if include_feed_counts else None
                )
                for row in rows
            ],
        )
