"""Feeds located in a location of the geopolygon read model, for the location filters of /v1/search.

A feed is linked to the locations of its reverse-geolocated stops: feedosmlocationgroup (feed_id, group_id,
stops_count) -> osmlocationgroupgeopolygon (group_id, osm_id). Each group is the full chain of areas covering some
of the feed's stops, from the country down, so the feeds linked to an osm_id already include the feeds of its
sub-areas. A feed that was never reverse-geolocated has no group, so it is in no location. A continent's groups are
the groups containing one of its countries.

The feed counts of /v1/locations follow the same rules, precomputed in the locationfeedcount materialized view.
"""

from typing import Final, Optional

from sqlalchemy import Float, Select, cast, func, or_, select
from sqlalchemy.orm import Session, aliased

from shared.database_gen.sqlacodegen_models import (
    Continent,
    CountryContinent,
    Feedosmlocationgroup,
    Geopolygon,
    t_osmlocationgroupgeopolygon as location_group_geopolygon,
)

LOCATION_TYPE_CONTINENT: Final = "continent"


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


def location_groups(location_id: int) -> Select:
    """The location groups containing the location. An unknown id has no group.

    A country can have several boundaries with the same ISO code; the read model keeps one of them as the country.
    The groups of the other boundaries are the country's too, as in the precomputed feed counts.
    """
    location_country_code = select(Geopolygon.iso_3166_1_code).where(Geopolygon.osm_id == location_id).scalar_subquery()
    same_country = select(Geopolygon.osm_id).where(Geopolygon.iso_3166_1_code == location_country_code)
    return select(location_group_geopolygon.c.group_id).where(
        or_(location_group_geopolygon.c.osm_id == location_id, location_group_geopolygon.c.osm_id.in_(same_country))
    )


def continent_groups(continent_code: str) -> Select:
    """The location groups containing a country of the continent, given by its code."""
    return (
        select(location_group_geopolygon.c.group_id)
        .join(Geopolygon, Geopolygon.osm_id == location_group_geopolygon.c.osm_id)
        .join(CountryContinent, CountryContinent.country_code == Geopolygon.iso_3166_1_code)
        .where(CountryContinent.continent_code == continent_code)
    )


def located_feeds(groups: Select, with_stop_share: bool = False):
    """Subquery of the feeds with stops in the given location groups, used by /v1/search to filter and sort.

    It applies no status or visibility rule: /v1/search applies its own filters. With `with_stop_share`, it also
    returns `stop_share`, the share of the feed's stops inside the location: the stops of its groups that are in
    `groups` over the stops of all its groups (NULL when the feed has no stop count).
    """
    feed_ids = select(Feedosmlocationgroup.feed_id).where(Feedosmlocationgroup.group_id.in_(groups))
    if not with_stop_share:
        return feed_ids.distinct().subquery("located_feed")
    feed_group = aliased(Feedosmlocationgroup)
    in_location = feed_group.group_id.in_(groups)
    located_stops = func.coalesce(func.sum(feed_group.stops_count).filter(in_location), 0)
    all_stops = func.nullif(func.sum(feed_group.stops_count), 0)
    return (
        select(
            feed_group.feed_id,
            (cast(located_stops, Float) / all_stops).label("stop_share"),
        )
        .where(feed_group.feed_id.in_(feed_ids))
        .group_by(feed_group.feed_id)
        .subquery("located_feed")
    )
