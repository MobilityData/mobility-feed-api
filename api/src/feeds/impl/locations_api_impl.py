import re
from typing import Final, List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from feeds.impl.error_handling import (
    location_not_found,
    location_path_not_found,
    location_path_required,
    locations_include_unsupported,
    locations_sort_unsupported,
    raise_http_error,
)
from feeds.impl.location_feeds import (
    clean_param,
    located_location_ids,
    location_feed_counts,
    normalize_path,
    resolve_continent_code,
)
from feeds_gen.apis.locations_api_base import BaseLocationsApi
from feeds_gen.models.location_detail import LocationDetail
from feeds_gen.models.location_feed_counts import LocationFeedCounts
from feeds_gen.models.location_search_response import LocationSearchResponse
from shared.database.database import with_db_session
from shared.database.sql_functions.unaccent import unaccent
from shared.database_gen.sqlacodegen_models import t_geopolygonlocationsearch as location_search
from shared.db_models.location_detail_impl import LocationDetailImpl
from shared.db_models.location_search_result_impl import LocationSearchResultImpl

SORT_BY_ADMIN_LEVEL: Final = "admin_level"
SORT_BY_FEED_COUNT: Final = "feed_count"
SORTS: Final = (SORT_BY_ADMIN_LEVEL, SORT_BY_FEED_COUNT)

INCLUDE_FEED_COUNTS: Final = "feed_counts"
INCLUDE_CHILDREN: Final = "children"
# The `include` values of the endpoints returning a list of locations, and of those returning one location.
LIST_INCLUDES: Final = (INCLUDE_FEED_COUNTS,)
DETAIL_INCLUDES: Final = (INCLUDE_FEED_COUNTS, INCLUDE_CHILDREN)

_location_columns = [
    location_search.c.osm_id,
    location_search.c.parent_osm_id,
    location_search.c.name,
    location_search.c.alt_name,
    location_search.c.location_type,
    location_search.c.continent_code,
    location_search.c.slug,
    location_search.c.path,
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


def _parse_sort(sort: Optional[str]) -> str:
    """The sort order, `admin_level` by default. Raises a 400 error for an unsupported value."""
    sort = clean_param(sort) or SORT_BY_ADMIN_LEVEL
    if sort not in SORTS:
        raise_http_error(400, locations_sort_unsupported.format(sort))
    return sort


def _parse_include(include: Optional[List[str]], supported: tuple) -> set:
    """The `include` values, given comma-separated or as repeated parameters. Raises a 400 error for an unsupported
    value."""
    values = {value.strip() for item in include or [] for value in item.split(",") if value.strip()}
    for value in sorted(values):
        if value not in supported:
            raise_http_error(
                400, locations_include_unsupported.format(value, ", ".join(f"'{name}'" for name in supported))
            )
    return values


def _build_locations_conditions(
    search_query: str | None,
    country_code: str | None,
    subdivision_code: str | None,
    location_type: str | None,
    continent_code: str | None = None,
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
    if continent_code is not None:
        # The continent row has its own code, so it is included.
        conditions.append(location_search.c.continent_code == continent_code)
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


def _page_feed_counts(db_session: Session, location_ids: list) -> dict:
    """The feed counts of the given locations, by location id. Locations without any counted feed are missing."""
    if not location_ids:
        return {}
    counts = location_feed_counts(location_ids)
    return {row.osm_id: _feed_counts(row) for row in db_session.execute(select(counts)).all()}


def _search_locations(
    db_session: Session,
    conditions: list,
    normalized_query: Optional[str],
    has_feeds: Optional[bool],
    with_feed_counts: bool,
    sort: str,
    limit: int,
    offset: int,
) -> LocationSearchResponse:
    """A page of the locations matching the conditions, with their total."""
    conditions = list(conditions)
    if has_feeds:
        # Count the feeds of the candidate locations once, rather than checking each location in a subquery.
        candidate_location_ids = select(location_search.c.osm_id)
        if conditions:
            candidate_location_ids = candidate_location_ids.where(and_(*conditions))
        conditions.append(location_search.c.osm_id.in_(located_location_ids(candidate_location_ids)))

    count_query = select(func.count(location_search.c.osm_id))
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total = db_session.execute(count_query).scalar_one()

    locations_query = select(*_location_columns)
    if conditions:
        locations_query = locations_query.where(and_(*conditions))
    counts = None
    if sort == SORT_BY_FEED_COUNT:
        # Count only the feeds of the filtered locations, before paginating.
        filtered_location_ids = select(location_search.c.osm_id)
        if conditions:
            filtered_location_ids = filtered_location_ids.where(and_(*conditions))
        counts = location_feed_counts(filtered_location_ids)
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
    feed_counts_by_location_id = {}
    if with_feed_counts:
        if counts is not None:
            feed_counts_by_location_id = {row.osm_id: _feed_counts(row) for row in rows}
        else:
            # Count only the feeds of the returned page.
            feed_counts_by_location_id = _page_feed_counts(db_session, [row.osm_id for row in rows])
    return LocationSearchResponse(
        total=total,
        results=[
            LocationSearchResultImpl.from_orm(
                row,
                feed_counts=(
                    (feed_counts_by_location_id.get(row.osm_id) or _feed_counts()) if with_feed_counts else None
                ),
            )
            for row in rows
        ],
    )


def _location_exists(db_session: Session, location_id: int) -> bool:
    return (
        db_session.execute(
            select(location_search.c.osm_id).where(location_search.c.osm_id == location_id)
        ).scalar_one_or_none()
        is not None
    )


class LocationsApiImpl(BaseLocationsApi):
    """This class represents the implementation of the `/locations` endpoints."""

    @with_db_session
    def get_locations(
        self,
        limit: int,
        offset: int,
        search_query: Optional[str],
        continent: Optional[str],
        country_code: Optional[str],
        subdivision_code: Optional[str],
        location_type: Optional[str],
        has_feeds: Optional[bool],
        include: Optional[List[str]],
        sort: Optional[str],
        db_session: Session,
    ) -> LocationSearchResponse:
        """Search locations, continents included, from the geopolygon materialized read model."""
        sort = _parse_sort(sort)
        includes = _parse_include(include, LIST_INCLUDES)
        continent_code = None
        if (continent := clean_param(continent)) is not None:
            continent_code = resolve_continent_code(db_session, continent)
            if continent_code is None:
                return _empty_response()

        conditions, normalized_query = _build_locations_conditions(
            search_query, country_code, subdivision_code, location_type, continent_code
        )
        return _search_locations(
            db_session,
            conditions,
            normalized_query,
            has_feeds,
            INCLUDE_FEED_COUNTS in includes,
            sort,
            limit,
            offset,
        )

    @with_db_session
    def get_location(
        self,
        location_id: int,
        include: Optional[List[str]],
        has_feeds: Optional[bool],
        sort: Optional[str],
        limit: int,
        offset: int,
        db_session: Session,
    ) -> LocationDetail:
        """Get one location by its id, with its direct children when requested."""
        return self._get_location_detail(
            db_session,
            location_search.c.osm_id == location_id,
            location_not_found.format(location_id),
            include,
            has_feeds,
            sort,
            limit,
            offset,
        )

    @with_db_session
    def get_location_by_path(
        self,
        path: Optional[str],
        include: Optional[List[str]],
        has_feeds: Optional[bool],
        sort: Optional[str],
        limit: int,
        offset: int,
        db_session: Session,
    ) -> LocationDetail:
        """Get one location by its path, with its direct children when requested."""
        normalized_path = normalize_path(path)
        if normalized_path is None:
            raise_http_error(400, location_path_required)
        return self._get_location_detail(
            db_session,
            location_search.c.path == normalized_path,
            location_path_not_found.format(normalized_path),
            include,
            has_feeds,
            sort,
            limit,
            offset,
        )

    @with_db_session
    def get_location_children(
        self,
        location_id: int,
        limit: int,
        offset: int,
        has_feeds: Optional[bool],
        include: Optional[List[str]],
        sort: Optional[str],
        db_session: Session,
    ) -> LocationSearchResponse:
        """List the direct children of a location."""
        sort = _parse_sort(sort)
        includes = _parse_include(include, LIST_INCLUDES)
        if not _location_exists(db_session, location_id):
            raise_http_error(404, location_not_found.format(location_id))
        return _search_locations(
            db_session,
            [location_search.c.parent_osm_id == location_id],
            None,
            has_feeds,
            INCLUDE_FEED_COUNTS in includes,
            sort,
            limit,
            offset,
        )

    @staticmethod
    def _get_location_detail(
        db_session: Session,
        condition,
        not_found_message: str,
        include: Optional[List[str]],
        has_feeds: Optional[bool],
        sort: Optional[str],
        limit: int,
        offset: int,
    ) -> LocationDetail:
        """The location matching the condition. `has_feeds`, `sort`, `limit` and `offset` apply to its children."""
        sort = _parse_sort(sort)
        includes = _parse_include(include, DETAIL_INCLUDES)
        with_feed_counts = INCLUDE_FEED_COUNTS in includes
        # Ordered like `resolve_location_id_by_path`, should two locations share a path.
        row = db_session.execute(
            select(*_location_columns)
            .where(condition)
            .order_by(location_search.c.admin_level.asc(), location_search.c.osm_id.asc())
            .limit(1)
        ).one_or_none()
        if row is None:
            raise_http_error(404, not_found_message)
        feed_counts = None
        if with_feed_counts:
            feed_counts = _page_feed_counts(db_session, [row.osm_id]).get(row.osm_id) or _feed_counts()
        children = None
        if INCLUDE_CHILDREN in includes:
            children = _search_locations(
                db_session,
                [location_search.c.parent_osm_id == row.osm_id],
                None,
                has_feeds,
                with_feed_counts,
                sort,
                limit,
                offset,
            )
        return LocationDetailImpl.from_orm(row, feed_counts=feed_counts, children=children)
