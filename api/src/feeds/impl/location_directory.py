"""Feed location directory: browse feeds by continent > country > subdivision > municipality.

The directory is built from the feeds' declared locations (feed <-> locationfeed <-> location), not from the OSM
geopolygons. Continents come from a static country code mapping, passed to the database as a VALUES list so that
the aggregation stays in SQL. Countries are identified by a slug of their name (`portugal`) from another static
table, and resolved to their ISO code when the request is parsed. Subdivision and municipality slugs are computed in
SQL: the same expression produces the slugs returned to clients and matches the ones they send back, so the two
cannot drift apart. The feeds of a node are listed by /v1/search, which filters with `located_feeds`.
"""

import logging
import unicodedata
from dataclasses import dataclass, replace
from typing import Final, List, Optional, Set

from sqlalchemy import String, and_, case, column, distinct, func, or_, select, values
from sqlalchemy.orm import Session

from feeds.impl.error_handling import (
    location_directory_country_not_in_continent,
    location_directory_not_found,
    location_directory_parent_required,
    raise_http_error,
)
from feeds_gen.models.location_directory_feed_counts import LocationDirectoryFeedCounts
from feeds_gen.models.location_directory_level import LocationDirectoryLevel
from feeds_gen.models.location_directory_node import LocationDirectoryNode
from feeds_gen.models.location_directory_response import LocationDirectoryResponse
from middleware.request_context import is_user_email_restricted
from shared.common.continents import CONTINENTS, CONTINENTS_BY_SLUG, COUNTRY_CONTINENTS, Continent
from shared.common.country_slugs import COUNTRY_SLUGS, get_country_code, get_country_name
from shared.database.sql_functions.unaccent import unaccent
from shared.database_gen.sqlacodegen_models import Feed, Location, t_locationfeed

DIRECTORY_FEED_STATUSES: Final = ("active", "inactive", "development", "future")
DIRECTORY_DATA_TYPES: Final = ("gtfs", "gtfs_rt", "gbfs")

# Country codes already reported as missing from the continent mapping, so the warning is logged once per process.
_reported_unmapped_country_codes: Set[str] = set()


@dataclass(frozen=True)
class DirectoryNode:
    """A node of the directory, identified by the request parameters. Unset levels are None."""

    continent: Optional[Continent] = None
    country_code: Optional[str] = None
    subdivision: Optional[str] = None
    municipality: Optional[str] = None

    @property
    def level(self) -> LocationDirectoryLevel:
        if self.municipality:
            return LocationDirectoryLevel.MUNICIPALITY
        if self.subdivision:
            return LocationDirectoryLevel.SUBDIVISION
        if self.country_code:
            return LocationDirectoryLevel.COUNTRY
        if self.continent:
            return LocationDirectoryLevel.CONTINENT
        return LocationDirectoryLevel.ROOT

    def path(self) -> List["DirectoryNode"]:
        """The nodes from the continent down to this node, inclusive. Empty for the root."""
        candidates = [
            DirectoryNode(continent=self.continent),
            replace(self, subdivision=None, municipality=None),
            replace(self, municipality=None),
            self,
        ]
        depth = [
            LocationDirectoryLevel.ROOT,
            LocationDirectoryLevel.CONTINENT,
            LocationDirectoryLevel.COUNTRY,
            LocationDirectoryLevel.SUBDIVISION,
            LocationDirectoryLevel.MUNICIPALITY,
        ].index(self.level)
        return candidates[:depth]


def _clean_param(value: Optional[str]) -> Optional[str]:
    if value is None or len(value.strip()) == 0:
        return None
    return value.strip()


def parse_directory_node(
    continent: Optional[str],
    country: Optional[str],
    subdivision: Optional[str],
    municipality: Optional[str],
) -> Optional[DirectoryNode]:
    """Validate the request parameters and return the requested node.

    Raises a 400 when a parameter is given without its parent or when the country is not in the continent.
    Returns None when the continent or country slug is unknown: such a node exists but contains no feed.
    """
    continent = _clean_param(continent)
    country = _clean_param(country)
    subdivision = _clean_param(subdivision)
    municipality = _clean_param(municipality)
    for child_name, child, parent_name, parent in (
        ("municipality", municipality, "subdivision", subdivision),
        ("subdivision", subdivision, "country", country),
        ("country", country, "continent", continent),
    ):
        if child is not None and parent is None:
            raise_http_error(400, location_directory_parent_required.format(child_name, parent_name))

    if continent is None:
        return DirectoryNode()
    matching_continent = CONTINENTS_BY_SLUG.get(continent.lower())
    if matching_continent is None:
        return None
    country_code = None
    if country is not None:
        country_code = get_country_code(country)
        if country_code is None:
            return None
        if COUNTRY_CONTINENTS.get(country_code) != matching_continent.code:
            raise_http_error(400, location_directory_country_not_in_continent.format(country, continent))
    return DirectoryNode(
        continent=matching_continent,
        country_code=country_code,
        subdivision=subdivision.lower() if subdivision else None,
        municipality=municipality.lower() if municipality else None,
    )


def _slug(name):
    """Lowercase, unaccent and replace every run of non-alphanumeric characters with a single hyphen."""
    return func.nullif(
        func.btrim(func.regexp_replace(func.lower(unaccent(name)), "[^a-z0-9]+", "-", "g"), "-"),
        "",
    )


def _clean_name(name):
    return func.nullif(func.btrim(name), "")


def _feed_scope_conditions():
    """Same visibility rules as /v1/search, restricted to the statuses listed in the directory."""
    return [
        Feed.status.in_(DIRECTORY_FEED_STATUSES),
        or_(Feed.operational_status == "published", not is_user_email_restricted()),
    ]


def _feed_locations(in_scope: bool = True):
    """One row per (feed, declared location), with its continent, slugs and depth.

    Only feeds in the directory's scope are kept unless `in_scope` is False.
    The depth of a location is 1 when it only declares a country, 2 with a subdivision and 3 with a municipality.
    Locations whose country code is missing from the continent mapping are left out.
    """
    continent_map = values(
        column("country_code", String),
        column("continent_code", String),
        name="continent_map",
    ).data(sorted(COUNTRY_CONTINENTS.items()))
    country_code = func.upper(func.btrim(Location.country_code))
    subdivision_name = _clean_name(Location.subdivision_name)
    municipality_name = _clean_name(Location.municipality)
    subdivision_slug = _slug(subdivision_name)
    municipality_slug = _slug(municipality_name)
    return (
        select(
            Feed.id.label("feed_id"),
            Feed.data_type.label("data_type"),
            continent_map.c.continent_code,
            country_code.label("country_code"),
            _clean_name(Location.country).label("country_name"),
            subdivision_name.label("subdivision_name"),
            subdivision_slug.label("subdivision_slug"),
            municipality_name.label("municipality_name"),
            municipality_slug.label("municipality_slug"),
            case(
                (municipality_slug.isnot(None), 3),
                (subdivision_slug.isnot(None), 2),
                else_=1,
            ).label("depth"),
        )
        .select_from(Feed)
        .join(t_locationfeed, t_locationfeed.c.feed_id == Feed.id)
        .join(Location, Location.id == t_locationfeed.c.location_id)
        .join(continent_map, continent_map.c.country_code == country_code)
        .where(*(_feed_scope_conditions() if in_scope else []))
        .subquery("feed_location")
    )


def _node_conditions(feed_locations, node: DirectoryNode) -> list:
    conditions = []
    if node.continent:
        conditions.append(feed_locations.c.continent_code == node.continent.code)
    if node.country_code:
        conditions.append(feed_locations.c.country_code == node.country_code)
    if node.subdivision:
        conditions.append(feed_locations.c.subdivision_slug == node.subdivision)
    if node.municipality:
        conditions.append(feed_locations.c.municipality_slug == node.municipality)
    return conditions


def _feed_count_columns(feed_locations, condition=None, prefix: str = "") -> list:
    """Distinct feed counts per data type and in total, optionally restricted to the rows matching `condition`."""

    def count(*conditions):
        conditions = [c for c in (condition, *conditions) if c is not None]
        expression = func.count(distinct(feed_locations.c.feed_id))
        return expression.filter(and_(*conditions)) if conditions else expression

    return [
        *(
            count(feed_locations.c.data_type == data_type).label(f"{prefix}{data_type}")
            for data_type in DIRECTORY_DATA_TYPES
        ),
        count().label(f"{prefix}total"),
    ]


def _feed_counts(row, prefix: str = "") -> LocationDirectoryFeedCounts:
    mapping = row._mapping
    return LocationDirectoryFeedCounts(
        gtfs=mapping[f"{prefix}gtfs"],
        gtfs_rt=mapping[f"{prefix}gtfs_rt"],
        gbfs=mapping[f"{prefix}gbfs"],
        total=mapping[f"{prefix}total"],
    )


def _country_name(country_code: str, declared_name: Optional[str]) -> str:
    # The English name, not the declared one (e.g. "Sverige"), so every country reads like its slug.
    return get_country_name(country_code) or declared_name or country_code


def _name_sort_key(node: LocationDirectoryNode):
    unaccented = "".join(c for c in unicodedata.normalize("NFKD", node.name or "") if not unicodedata.combining(c))
    return unaccented.casefold(), node.slug


def _make_node(level: LocationDirectoryLevel, key: str, name: Optional[str], counts) -> LocationDirectoryNode:
    match level:
        case LocationDirectoryLevel.CONTINENT:
            continent = CONTINENTS[key]
            return LocationDirectoryNode(
                level=level, slug=continent.slug, code=continent.code, name=continent.name, feed_counts=counts
            )
        case LocationDirectoryLevel.COUNTRY:
            return LocationDirectoryNode(
                level=level, slug=COUNTRY_SLUGS[key], code=key, name=_country_name(key, name), feed_counts=counts
            )
        case _:
            return LocationDirectoryNode(level=level, slug=key, code=None, name=name or key, feed_counts=counts)


_CHILD_LEVEL: Final = {
    LocationDirectoryLevel.ROOT: LocationDirectoryLevel.CONTINENT,
    LocationDirectoryLevel.CONTINENT: LocationDirectoryLevel.COUNTRY,
    LocationDirectoryLevel.COUNTRY: LocationDirectoryLevel.SUBDIVISION,
    LocationDirectoryLevel.SUBDIVISION: LocationDirectoryLevel.MUNICIPALITY,
}


def _key_and_name_columns(feed_locations, level: LocationDirectoryLevel):
    """The column identifying a node of `level`, and the column holding its declared name."""
    match level:
        case LocationDirectoryLevel.CONTINENT:
            return feed_locations.c.continent_code, None
        case LocationDirectoryLevel.COUNTRY:
            return feed_locations.c.country_code, feed_locations.c.country_name
        case LocationDirectoryLevel.SUBDIVISION:
            return feed_locations.c.subdivision_slug, feed_locations.c.subdivision_name
        case _:
            return feed_locations.c.municipality_slug, feed_locations.c.municipality_name


def _breadcrumb(db_session: Session, feed_locations, node: DirectoryNode) -> List[LocationDirectoryNode]:
    """Counts and display names of every node on the path, in a single aggregate over the continent."""
    path = node.path()
    columns = []
    for index, path_node in enumerate(path):
        condition = and_(*_node_conditions(feed_locations, path_node))
        columns.extend(_feed_count_columns(feed_locations, condition, f"n{index}_"))
        _, name_column = _key_and_name_columns(feed_locations, path_node.level)
        if name_column is not None:
            # mode() ignores NULLs, so this is the most frequent spelling among the rows of this node.
            columns.append(func.mode().within_group(case((condition, name_column))).label(f"n{index}_name"))
    row = db_session.execute(select(*columns).where(*_node_conditions(feed_locations, path[0]))).one()

    breadcrumb = []
    for index, path_node in enumerate(path):
        key = {
            LocationDirectoryLevel.CONTINENT: path_node.continent.code,
            LocationDirectoryLevel.COUNTRY: path_node.country_code,
            LocationDirectoryLevel.SUBDIVISION: path_node.subdivision,
            LocationDirectoryLevel.MUNICIPALITY: path_node.municipality,
        }[path_node.level]
        name = row._mapping.get(f"n{index}_name")
        breadcrumb.append(_make_node(path_node.level, key, name, _feed_counts(row, f"n{index}_")))
    return breadcrumb


def _children(db_session: Session, feed_locations, node: DirectoryNode) -> List[LocationDirectoryNode]:
    child_level = _CHILD_LEVEL.get(node.level)
    if child_level is None:
        return []
    key_column, name_column = _key_and_name_columns(feed_locations, child_level)
    name = func.mode().within_group(name_column) if name_column is not None else None
    query = (
        select(
            key_column.label("key"),
            *([name.label("name")] if name is not None else []),
            *_feed_count_columns(feed_locations),
        )
        .where(*_node_conditions(feed_locations, node), key_column.isnot(None))
        .group_by(key_column)
    )
    children = [
        _make_node(child_level, row.key, row._mapping.get("name"), _feed_counts(row))
        for row in db_session.execute(query)
    ]
    return sorted(children, key=_name_sort_key)


def _warn_unmapped_country_codes(db_session: Session) -> None:
    """Log the declared country codes that the continent mapping does not know, as they are left out."""
    country_code = func.upper(func.btrim(Location.country_code))
    query = (
        select(country_code.label("country_code"))
        .distinct()
        .select_from(Feed)
        .join(t_locationfeed, t_locationfeed.c.feed_id == Feed.id)
        .join(Location, Location.id == t_locationfeed.c.location_id)
        .where(*_feed_scope_conditions(), func.coalesce(country_code, "") != "")
    )
    for code in db_session.execute(query).scalars():
        if code not in COUNTRY_CONTINENTS and code not in _reported_unmapped_country_codes:
            _reported_unmapped_country_codes.add(code)
            logging.warning("Country code '%s' has no continent mapping, its feeds are left out of the directory", code)


def get_location_directory(
    db_session: Session,
    continent: Optional[str],
    country: Optional[str],
    subdivision: Optional[str],
    municipality: Optional[str],
) -> LocationDirectoryResponse:
    node = parse_directory_node(continent, country, subdivision, municipality)
    if node is None:
        raise_http_error(404, location_directory_not_found)
    feed_locations = _feed_locations()

    if node.level == LocationDirectoryLevel.ROOT:
        _warn_unmapped_country_codes(db_session)
        breadcrumb = []
        feed_counts = _feed_counts(db_session.execute(select(*_feed_count_columns(feed_locations))).one())
    else:
        breadcrumb = _breadcrumb(db_session, feed_locations, node)
        feed_counts = breadcrumb[-1].feed_counts
        if feed_counts.total == 0:
            raise_http_error(404, location_directory_not_found)

    return LocationDirectoryResponse(
        level=node.level,
        breadcrumb=breadcrumb,
        feed_counts=feed_counts,
        children=_children(db_session, feed_locations, node),
    )


def located_feeds(node: DirectoryNode):
    """Subquery of the feeds with a declared location within `node`, used by /v1/search to filter and sort.

    Unlike the directory counts, it applies no status or visibility rule: /v1/search applies its own filters. A feed
    may declare several locations within the node; its `depth` is the one of the location closest to the node's level
    (1 country, 2 subdivision, 3 municipality), so that `sort=location` ranks it by its most relevant location.
    """
    feed_locations = _feed_locations(in_scope=False)
    return (
        select(feed_locations.c.feed_id, func.min(feed_locations.c.depth).label("depth"))
        .where(*_node_conditions(feed_locations, node))
        .group_by(feed_locations.c.feed_id)
        .subquery("located_feed")
    )
