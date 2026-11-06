"""Feeds located in a location of the geopolygon read model, shared by /v1/locations and /v1/search.

A feed is linked to the locations of its reverse-geolocated stops: feedosmlocationgroup (feed_id, group_id,
stops_count) -> osmlocationgroupgeopolygon (group_id, osm_id). Each group is the full chain of areas covering some
of the feed's stops, from the country down to the most local level, so the feeds linked to an osm_id already include
the feeds of its sub-areas. Continents are not geopolygons: they are rows of the read model with a negative location id
(continent.location_id), and a feed is in a continent when one of its groups contains a country of that continent.

GTFS Realtime feeds have no stops, so they are rarely geolocated: a realtime feed without location group takes the
groups of the schedule feeds it references (feedreference).

Performance: every query below filters by location (or by feed) inside each part of its UNION ALL, own groups and
inherited groups alike, instead of filtering a union of all feed groups. PostgreSQL cannot push a join condition into
a UNION ALL branch that is itself a join, and it estimates the inherited part at about one row, so a filter applied to
the whole union made it rebuild the inherited groups of every realtime feed once per location group in a nested loop:
minutes for a continent.
"""

from typing import Final, Optional

from sqlalchemy import Float, Select, Subquery, cast, distinct, func, or_, select, union_all
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


def _own_feed_groups():
    """Alias of feedosmlocationgroup for the feeds' own groups."""
    return aliased(Feedosmlocationgroup)


def _without_own_groups(realtime_feed_id):
    """Condition: the realtime feed has no location group of its own, so it takes its schedule feeds' groups."""
    realtime_group = aliased(Feedosmlocationgroup)
    return ~select(realtime_group.feed_id).where(realtime_group.feed_id == realtime_feed_id).exists()


def _feed_groups_in(groups: Select) -> list:
    """(feed_id, group_id, stops_count) of the feeds' groups among `groups`: own, then inherited."""
    own = _own_feed_groups()
    schedule_group = aliased(Feedosmlocationgroup)
    return [
        select(own.feed_id, own.group_id, own.stops_count).where(own.group_id.in_(groups)),
        select(feed_reference.c.gtfs_rt_feed_id.label("feed_id"), schedule_group.group_id, schedule_group.stops_count)
        .select_from(schedule_group)
        .join(feed_reference, feed_reference.c.gtfs_feed_id == schedule_group.feed_id)
        .where(schedule_group.group_id.in_(groups), _without_own_groups(feed_reference.c.gtfs_rt_feed_id)),
    ]


def _groups_of_feeds(feed_ids: Select, name: str) -> Subquery:
    """All the groups of the given feeds, own or inherited: `feed_id`, `group_id` and `stops_count`.

    A realtime feed referencing several schedule feeds that share a group has that group once per schedule feed.
    """
    own = _own_feed_groups()
    schedule_group = aliased(Feedosmlocationgroup)
    return union_all(
        select(own.feed_id, own.group_id, own.stops_count).where(own.feed_id.in_(feed_ids)),
        select(feed_reference.c.gtfs_rt_feed_id.label("feed_id"), schedule_group.group_id, schedule_group.stops_count)
        .select_from(feed_reference)
        .join(schedule_group, schedule_group.feed_id == feed_reference.c.gtfs_feed_id)
        .where(feed_reference.c.gtfs_rt_feed_id.in_(feed_ids), _without_own_groups(feed_reference.c.gtfs_rt_feed_id)),
    ).subquery(name)


def located_feeds(groups: Select, with_stop_share: bool = False):
    """Subquery of the feeds with stops in the given location groups, used by /v1/search to filter and sort.

    It applies no status or visibility rule: /v1/search applies its own filters. With `with_stop_share`, it also
    returns `stop_share`, the share of the feed's stops inside the location: the stops of its groups that are in
    `groups` over the stops of all its groups (NULL when the feed has no stop count).
    """
    feeds_in_groups = union_all(*_feed_groups_in(groups)).subquery("feed_in_location_group")
    feed_ids = select(feeds_in_groups.c.feed_id).distinct()
    if not with_stop_share:
        return feed_ids.subquery("located_feed")
    feed_group = _groups_of_feeds(feed_ids, "feed_location_group")
    in_location = feed_group.c.group_id.in_(groups)
    located_stops = func.coalesce(func.sum(feed_group.c.stops_count).filter(in_location), 0)
    all_stops = func.nullif(func.sum(feed_group.c.stops_count), 0)
    return (
        select(
            feed_group.c.feed_id,
            (cast(located_stops, Float) / all_stops).label("stop_share"),
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


def _location_memberships(location_ids) -> list:
    """(location id, group_id) of the given locations, as (from clause, location id column, conditions).

    An OSM area is a member of its groups; a continent is a member of the groups of its countries. `location_ids` is a
    list or a select of location ids; the filter is part of each membership, so that it applies inside every branch.
    """
    place = location_group_geopolygon.alias("place_group")
    continent_member = location_group_geopolygon.alias("continent_group")
    country = _continent_countries("continent_country")
    return [
        (place, place.c.osm_id, place.c.group_id, [place.c.osm_id.in_(location_ids)]),
        (
            continent_member.join(country, country.c.osm_id == continent_member.c.osm_id),
            country.c.parent_osm_id,
            continent_member.c.group_id,
            [country.c.location_type == LOCATION_TYPE_COUNTRY, country.c.parent_osm_id.in_(location_ids)],
        ),
    ]


def location_feed_pairs(location_ids) -> Subquery:
    """Subquery of (`osm_id`, `feed_id`, `data_type`): the counted feeds with stops in each of the given locations.

    Feeds are reached through their own groups or, for a realtime feed without group, through its schedule feeds'
    groups. Each branch joins the feed and applies the counted-feed rules itself, so the union is only aggregated,
    never joined: a join on it could make PostgreSQL rebuild it for every row. The same feed can appear several times
    for a location (one row per group); count it with DISTINCT.
    """
    branches = []
    for from_clause, location_id, group_id, conditions in _location_memberships(location_ids):
        own = _own_feed_groups()
        branches.append(
            select(location_id.label("osm_id"), Feed.id.label("feed_id"), Feed.data_type.label("data_type"))
            .select_from(from_clause)
            .join(own, own.group_id == group_id)
            .join(Feed, Feed.id == own.feed_id)
            .where(*conditions, *counted_feed_conditions())
        )
        schedule_group = aliased(Feedosmlocationgroup)
        branches.append(
            select(location_id.label("osm_id"), Feed.id.label("feed_id"), Feed.data_type.label("data_type"))
            .select_from(from_clause)
            .join(schedule_group, schedule_group.group_id == group_id)
            .join(feed_reference, feed_reference.c.gtfs_feed_id == schedule_group.feed_id)
            .join(Feed, Feed.id == feed_reference.c.gtfs_rt_feed_id)
            .where(*conditions, *counted_feed_conditions(), _without_own_groups(feed_reference.c.gtfs_rt_feed_id))
        )
    return union_all(*branches).subquery("location_feed")


def located_location_ids(candidate_location_ids: Select) -> Select:
    """The ids among `candidate_location_ids` (a select of location ids) with at least one counted feed."""
    pairs = location_feed_pairs(candidate_location_ids.correlate(None))
    return select(pairs.c.osm_id).distinct().correlate(None)


def location_feed_counts(location_ids):
    """Subquery of the feed counts of the given locations (a list or a select of location ids), one row per `osm_id`.

    A continent counts the feeds of its countries, each feed once even when it has stops in several of them. Locations
    without any counted feed have no row.
    """
    if isinstance(location_ids, Select):
        location_ids = location_ids.correlate(None)
    pairs = location_feed_pairs(location_ids)
    return (
        select(
            pairs.c.osm_id.label("osm_id"),
            *(
                func.count(distinct(pairs.c.feed_id)).filter(pairs.c.data_type == data_type).label(data_type)
                for data_type in FEED_DATA_TYPES
            ),
            func.count(distinct(pairs.c.feed_id)).label("total"),
        )
        .group_by(pairs.c.osm_id)
        .subquery("location_feed_counts")
    )
