"""Feeds located in a location of the geopolygon read model, shared by /v1/locations and /v1/search.

A feed is linked to the locations of its reverse-geolocated stops: feedosmlocationgroup (feed_id, group_id,
stops_count) -> osmlocationgroupgeopolygon (group_id, osm_id). Each group is the full chain of areas covering some
of the feed's stops, from the country down to the most local level, so the feeds linked to an osm_id already include
the feeds of its sub-areas. Continents are not geopolygons: a feed is in a continent when one of its groups contains a
country of that continent.
"""

from typing import Final, Optional

from sqlalchemy import Float, Select, cast, distinct, func, or_, select
from sqlalchemy.orm import Session, aliased

from middleware.request_context import is_user_email_restricted
from shared.database_gen.sqlacodegen_models import (
    Continent,
    Feed,
    Feedosmlocationgroup,
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


def resolve_continent_code(db_session: Session, continent: str) -> Optional[str]:
    """The code of the continent given by its slug or its code, case-insensitive. None when it is unknown."""
    return db_session.execute(
        select(Continent.code).where(
            or_(func.lower(Continent.slug) == continent.lower(), Continent.code == continent.upper())
        )
    ).scalar_one_or_none()


def location_groups(osm_id: int, continent_code: Optional[str] = None) -> Select:
    """The location groups containing the location and, when `continent_code` is given, a country of the continent."""
    groups = select(location_group_geopolygon.c.group_id).where(location_group_geopolygon.c.osm_id == osm_id)
    if continent_code is not None:
        groups = groups.where(
            location_group_geopolygon.c.group_id.in_(continent_groups(continent_code).correlate(None))
        )
    return groups


def continent_groups(continent_code: str) -> Select:
    """The location groups containing a country of the continent."""
    return (
        select(location_group_geopolygon.c.group_id)
        .join(location_search, location_search.c.osm_id == location_group_geopolygon.c.osm_id)
        .where(location_search.c.location_type == "country", location_search.c.continent_code == continent_code)
    )


def located_feeds(groups: Select, with_stop_share: bool = False):
    """Subquery of the feeds with stops in the given location groups, used by /v1/search to filter and sort.

    It applies no status or visibility rule: /v1/search applies its own filters. With `with_stop_share`, it also
    returns `stop_share`, the share of the feed's stops inside the location: the stops of its groups that are in
    `groups` over the stops of all its groups (NULL when the feed has no stop count).
    """
    if not with_stop_share:
        return (
            select(Feedosmlocationgroup.feed_id)
            .where(Feedosmlocationgroup.group_id.in_(groups))
            .distinct()
            .subquery("located_feed")
        )
    feed_group = aliased(Feedosmlocationgroup)
    in_location = Feedosmlocationgroup.group_id.in_(groups)
    located_stops = func.coalesce(func.sum(Feedosmlocationgroup.stops_count).filter(in_location), 0)
    all_stops = func.nullif(func.sum(Feedosmlocationgroup.stops_count), 0)
    return (
        select(
            Feedosmlocationgroup.feed_id,
            (cast(located_stops, Float) / all_stops).label("stop_share"),
        )
        # Only the feeds with a group in the location, with all their groups.
        .where(Feedosmlocationgroup.feed_id.in_(select(feed_group.feed_id).where(feed_group.group_id.in_(groups))))
        .group_by(Feedosmlocationgroup.feed_id)
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
    return (
        select(*columns)
        .select_from(location_group_geopolygon)
        .join(Feedosmlocationgroup, Feedosmlocationgroup.group_id == location_group_geopolygon.c.group_id)
        .join(Feed, Feed.id == Feedosmlocationgroup.feed_id)
    )


def has_counted_feeds():
    """Whether the location of the enclosing geopolygonlocationsearch row has at least one counted feed."""
    return (
        _location_feeds_query(location_group_geopolygon.c.osm_id)
        .where(location_group_geopolygon.c.osm_id == location_search.c.osm_id, *counted_feed_conditions())
        .exists()
    )


def location_feed_counts(osm_ids):
    """Subquery of the feed counts of the given locations (a list or a select of osm_ids), one row per osm_id.

    Locations without any counted feed have no row.
    """
    return (
        _location_feeds_query(location_group_geopolygon.c.osm_id, *feed_count_columns())
        .where(location_group_geopolygon.c.osm_id.in_(osm_ids), *counted_feed_conditions())
        .group_by(location_group_geopolygon.c.osm_id)
        .subquery("location_feed_counts")
    )


def continent_feed_counts():
    """Subquery of the feed counts of every continent with a counted feed, one row per continent_code.

    A feed is counted once per continent, even when it has stops in several of its countries.
    """
    return (
        _location_feeds_query(location_search.c.continent_code, *feed_count_columns())
        .join(location_search, location_search.c.osm_id == location_group_geopolygon.c.osm_id)
        .where(
            location_search.c.location_type == "country",
            location_search.c.continent_code.isnot(None),
            *counted_feed_conditions(),
        )
        .group_by(location_search.c.continent_code)
        .subquery("continent_feed_counts")
    )
