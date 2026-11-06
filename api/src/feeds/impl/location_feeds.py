"""Feeds located in a location of the geopolygon read model, shared by /v1/locations and /v1/search.

A feed is linked to the locations of its reverse-geolocated stops: feedosmlocationgroup (feed_id, group_id,
stops_count) -> osmlocationgroupgeopolygon (group_id, osm_id). Each group is the full chain of areas covering some
of the feed's stops, from the country down to the most local level, so the feeds linked to an osm_id already include
the feeds of its sub-areas. Continents are not geopolygons: they are rows of the read model with a negative location id
(continent.location_id), and a feed is in a continent when one of its groups contains a country of that continent.

GTFS Realtime feeds have no stops, so they are rarely geolocated: a realtime feed without location group takes the
groups of the schedule feeds it references (feedreference). See `feed_location_groups`.
"""

from typing import Final, Optional

from sqlalchemy import Float, Select, Subquery, and_, cast, distinct, func, or_, select, union_all
from sqlalchemy.orm import Session, aliased

from middleware.request_context import is_user_email_restricted
from shared.database_gen.sqlacodegen_models import (
    Continent,
    Feed,
    Feedosmlocationgroup,
    t_feedreference as feed_reference,
    t_geopolygonlocationsearch as location_search,
    t_osmlocationgroupgeopolygon as location_group_geopolygon,
)

# Statuses of the feeds counted in a location, as listed by the location directory.
LOCATION_FEED_STATUSES: Final = ("active", "inactive", "development", "future")
FEED_DATA_TYPES: Final = ("gtfs", "gtfs_rt", "gbfs")


def clean_param(value: Optional[str]) -> Optional[str]:
    if value is None or len(value.strip()) == 0:
        return None
    return value.strip()


LOCATION_TYPE_CONTINENT: Final = "continent"
LOCATION_TYPE_COUNTRY: Final = "country"


def resolve_continent_code(db_session: Session, continent: str) -> Optional[str]:
    """The code of the continent given by its slug or its code, case-insensitive. None when it is unknown."""
    return db_session.execute(
        select(Continent.code).where(
            or_(func.lower(Continent.slug) == continent.lower(), Continent.code == continent.upper())
        )
    ).scalar_one_or_none()


def normalize_path(path: Optional[str]) -> Optional[str]:
    """A location path as stored in the read model: leading and trailing slashes are ignored (`canada/quebec/` is
    `canada/quebec`), and slugs are lowercase, so lowercasing the path makes the exact match case-insensitive. A path of
    only slashes is no path."""
    path = clean_param(path)
    if path is None:
        return None
    return clean_param(path.strip("/").lower())


def resolve_location_id_by_path(db_session: Session, path: str) -> Optional[int]:
    """The location id of the location at this path (see `normalize_path`). None when no location has that path.

    Paths are unique by construction (sibling slugs never collide), but not by constraint: should two locations share a
    path, the broadest one, then the lowest id, is returned rather than failing.
    """
    normalized_path = normalize_path(path)
    if normalized_path is None:
        return None
    return db_session.execute(
        select(location_search.c.osm_id)
        .where(location_search.c.path == normalized_path)
        .order_by(location_search.c.admin_level.asc(), location_search.c.osm_id.asc())
        .limit(1)
    ).scalar_one_or_none()


def location_groups(location_id: int) -> Select:
    """The location groups containing the location: an OSM area, or a country of the continent for a continent id
    (negative). An unknown id has no group."""
    if location_id < 0:
        return continent_groups(location_id)
    return select(location_group_geopolygon.c.group_id).where(location_group_geopolygon.c.osm_id == location_id)


def _continent_countries(name: str):
    """An alias of the read model, to join the countries of a continent."""
    return location_search.alias(name)


def continent_groups(continent_location_id: int) -> Select:
    """The location groups containing a country of the continent, given by its (negative) location id."""
    country = _continent_countries("continent_country")
    return (
        select(location_group_geopolygon.c.group_id)
        .join(country, country.c.osm_id == location_group_geopolygon.c.osm_id)
        .where(country.c.location_type == LOCATION_TYPE_COUNTRY, country.c.parent_osm_id == continent_location_id)
    )


def feed_location_groups(name: str = "feed_location_group") -> Subquery:
    """Subquery of the location groups of each feed: `feed_id`, `group_id` and `stops_count`.

    These are the feed's own groups (feedosmlocationgroup). A GTFS Realtime feed without group of its own takes the
    groups of the schedule feeds it references, with their stop counts. A feed referencing several schedule feeds
    that share a group has that group once per schedule feed.
    """
    own_groups = select(Feedosmlocationgroup.feed_id, Feedosmlocationgroup.group_id, Feedosmlocationgroup.stops_count)
    schedule_group = aliased(Feedosmlocationgroup)
    realtime_group = aliased(Feedosmlocationgroup)
    inherited_groups = (
        select(
            feed_reference.c.gtfs_rt_feed_id.label("feed_id"),
            schedule_group.group_id,
            schedule_group.stops_count,
        )
        .select_from(feed_reference)
        .join(schedule_group, schedule_group.feed_id == feed_reference.c.gtfs_feed_id)
        .where(
            ~select(realtime_group.feed_id).where(realtime_group.feed_id == feed_reference.c.gtfs_rt_feed_id).exists()
        )
    )
    return union_all(own_groups, inherited_groups).subquery(name)


def located_feeds(groups: Select, with_stop_share: bool = False):
    """Subquery of the feeds with stops in the given location groups, used by /v1/search to filter and sort.

    It applies no status or visibility rule: /v1/search applies its own filters. With `with_stop_share`, it also
    returns `stop_share`, the share of the feed's stops inside the location: the stops of its groups that are in
    `groups` over the stops of all its groups (NULL when the feed has no stop count).
    """
    feed_group = feed_location_groups()
    if not with_stop_share:
        return select(feed_group.c.feed_id).where(feed_group.c.group_id.in_(groups)).distinct().subquery("located_feed")
    located_feed_group = feed_location_groups("located_feed_group")
    in_location = feed_group.c.group_id.in_(groups)
    located_stops = func.coalesce(func.sum(feed_group.c.stops_count).filter(in_location), 0)
    all_stops = func.nullif(func.sum(feed_group.c.stops_count), 0)
    return (
        select(
            feed_group.c.feed_id,
            (cast(located_stops, Float) / all_stops).label("stop_share"),
        )
        # Only the feeds with a group in the location, with all their groups.
        .where(
            feed_group.c.feed_id.in_(
                select(located_feed_group.c.feed_id).where(located_feed_group.c.group_id.in_(groups))
            )
        )
        .group_by(feed_group.c.feed_id)
        .subquery("located_feed")
    )


def counted_feed_conditions() -> list:
    """The feeds counted in a location: the directory statuses, with the same visibility rule as /v1/search."""
    return [
        Feed.status.in_(LOCATION_FEED_STATUSES),
        or_(Feed.operational_status == "published", not is_user_email_restricted()),
    ]


def feed_count_columns() -> list:
    """Distinct counted feeds per data type and in total, labelled `gtfs`, `gtfs_rt`, `gbfs` and `total`."""
    return [
        *(
            func.count(distinct(Feed.id)).filter(Feed.data_type == data_type).label(data_type)
            for data_type in FEED_DATA_TYPES
        ),
        func.count(distinct(Feed.id)).label("total"),
    ]


def _location_feeds_query(*columns) -> Select:
    feed_group = feed_location_groups()
    return (
        select(*columns)
        .select_from(location_group_geopolygon)
        .join(feed_group, feed_group.c.group_id == location_group_geopolygon.c.group_id)
        .join(Feed, Feed.id == feed_group.c.feed_id)
    )


def has_counted_feeds():
    """Whether the location of the enclosing geopolygonlocationsearch row has at least one counted feed.

    For a continent row, whether one of its countries has one.
    """
    in_location = (
        _location_feeds_query(location_group_geopolygon.c.osm_id)
        .where(location_group_geopolygon.c.osm_id == location_search.c.osm_id, *counted_feed_conditions())
        .exists()
    )
    country = _continent_countries("continent_country")
    in_continent = (
        _location_feeds_query(location_group_geopolygon.c.osm_id)
        .join(country, country.c.osm_id == location_group_geopolygon.c.osm_id)
        .where(
            country.c.location_type == LOCATION_TYPE_COUNTRY,
            country.c.parent_osm_id == location_search.c.osm_id,
            *counted_feed_conditions(),
        )
        .exists()
    )
    return or_(
        and_(location_search.c.location_type != LOCATION_TYPE_CONTINENT, in_location),
        and_(location_search.c.location_type == LOCATION_TYPE_CONTINENT, in_continent),
    )


def location_feed_counts(location_ids):
    """Subquery of the feed counts of the given locations (a list or a select of location ids), one row per `osm_id`.

    A continent counts the feeds of its countries, each feed once even when it has stops in several of them. Locations
    without any counted feed have no row.
    """
    place_counts = (
        _location_feeds_query(location_group_geopolygon.c.osm_id.label("osm_id"), *feed_count_columns())
        .where(location_group_geopolygon.c.osm_id.in_(location_ids), *counted_feed_conditions())
        .group_by(location_group_geopolygon.c.osm_id)
    )
    return union_all(place_counts, _continent_feed_counts(location_ids)).subquery("location_feed_counts")


def _continent_feed_counts(location_ids) -> Select:
    """The feed counts of the continents among the given location ids, one row per continent `osm_id`."""
    country = _continent_countries("continent_country")
    return (
        _location_feeds_query(country.c.parent_osm_id.label("osm_id"), *feed_count_columns())
        .join(country, country.c.osm_id == location_group_geopolygon.c.osm_id)
        .where(
            country.c.location_type == LOCATION_TYPE_COUNTRY,
            country.c.parent_osm_id.in_(location_ids),
            *counted_feed_conditions(),
        )
        .group_by(country.c.parent_osm_id)
    )
