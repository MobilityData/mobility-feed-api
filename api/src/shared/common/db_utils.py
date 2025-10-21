import os
from typing import Iterator, List, Dict, Optional

from geoalchemy2 import WKTElement
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.orm import joinedload, Session, contains_eager, load_only
from sqlalchemy.orm.query import Query
from sqlalchemy.orm.strategy_options import _AbstractLoad
from sqlalchemy import func
from sqlalchemy.sql import and_
from shared.database_gen.sqlacodegen_models import (
    Feed,
    Gtfsdataset,
    Gtfsfeed,
    Location,
    Validationreport,
    Gtfsrealtimefeed,
    Entitytype,
    Redirectingid,
    Feedosmlocationgroup,
    Geopolygon,
    Gbfsfeed,
    Gbfsversion,
    Gbfsvalidationreport,
)
from shared.feed_filters.gtfs_feed_filter import GtfsFeedFilter, LocationFilter
from shared.feed_filters.gtfs_rt_feed_filter import GtfsRtFeedFilter, EntityTypeFilter
from .entity_type_enum import EntityType
from .error_handling import raise_internal_http_validation_error, invalid_bounding_coordinates, invalid_bounding_method
from .iter_utils import batched
from ..feed_filters.gbfs_feed_filter import GbfsFeedFilter, GbfsVersionFilter


def get_gtfs_feeds_query(
    db_session: Session,
    stable_id: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    provider: str | None = None,
    producer_url: str | None = None,
    country_code: str | None = None,
    subdivision_name: str | None = None,
    municipality: str | None = None,
    dataset_latitudes: str | None = None,
    dataset_longitudes: str | None = None,
    bounding_filter_method: str | None = None,
    is_official: bool | None = None,
    published_only: bool = True,
    include_options_for_joinedload: bool = True,
) -> Query[any]:
    """Get the DB query to use to retrieve the GTFS feeds.."""
    gtfs_feed_filter = GtfsFeedFilter(
        stable_id=stable_id,
        provider__ilike=provider,
        producer_url__ilike=producer_url,
        location=None,
    )

    subquery = gtfs_feed_filter.filter(select(Gtfsfeed.id))
    subquery = apply_bounding_filtering(
        subquery, dataset_latitudes, dataset_longitudes, bounding_filter_method
    ).subquery()
    feed_query = db_session.query(Gtfsfeed).filter(Gtfsfeed.id.in_(subquery))

    if country_code or subdivision_name or municipality:
        location_filter = LocationFilter(
            country_code=country_code,
            subdivision_name__ilike=subdivision_name,
            municipality__ilike=municipality,
        )
        location_subquery = location_filter.filter(select(Location.id))
        feed_query = feed_query.filter(Gtfsfeed.locations.any(Location.id.in_(location_subquery)))

    if published_only:
        feed_query = feed_query.filter(Gtfsfeed.operational_status == "published")

    feed_query = add_official_filter(feed_query, is_official)

    if include_options_for_joinedload:
        feed_query = feed_query.options(
            joinedload(Gtfsfeed.latest_dataset)
            .joinedload(Gtfsdataset.validation_reports)
            .joinedload(Validationreport.features),
            joinedload(Gtfsfeed.visualization_dataset),
            *get_joinedload_options(),
        ).order_by(Gtfsfeed.provider, Gtfsfeed.stable_id)

    feed_query = feed_query.limit(limit).offset(offset)
    return feed_query


def apply_most_common_location_filter(query: Query, db_session: Session) -> Query:
    """
    Apply the most common location filter to the query.
    :param query: The query to apply the filter to.
    :param db_session: The database session.

    :return: The query with the most common location filter applied.
    """
    most_common_location_subquery = (
        db_session.query(
            Feedosmlocationgroup.feed_id, func.max(Feedosmlocationgroup.stops_count).label("max_stops_count")
        )
        .group_by(Feedosmlocationgroup.feed_id)
        .subquery()
    )
    return query.outerjoin(Feed.feedosmlocationgroups).filter(
        Feedosmlocationgroup.stops_count == most_common_location_subquery.c.max_stops_count,
        Feedosmlocationgroup.feed_id == most_common_location_subquery.c.feed_id,
    )


def get_geopolygons(db_session: Session, feeds: List[Feed], include_geometry: bool = False) -> Dict[str, Geopolygon]:
    """
    Get the geolocations for the given feeds.
    :param db_session: The database session.
    :param feeds: The feeds to get the geolocations for.
    :param include_geometry: Whether to include the geometry in the result.

    :return: The geolocations for the given location groups.
    """
    location_groups = [feed.feedosmlocationgroups for feed in feeds]
    location_groups = [item for sublist in location_groups for item in sublist]

    if not location_groups:
        return dict()
    geo_polygons_osm_ids = []
    for location_group in location_groups:
        split_ids = location_group.group_id.split(".")
        if not split_ids:
            continue
        geo_polygons_osm_ids += [int(split_id) for split_id in split_ids if split_id.isdigit()]
    if not geo_polygons_osm_ids:
        return dict()
    geo_polygons_osm_ids = list(set(geo_polygons_osm_ids))
    query = db_session.query(Geopolygon).filter(Geopolygon.osm_id.in_(geo_polygons_osm_ids))
    if not include_geometry:
        query = query.options(
            load_only(Geopolygon.osm_id, Geopolygon.name, Geopolygon.iso_3166_2_code, Geopolygon.iso_3166_1_code)
        )
    query = query.order_by(Geopolygon.admin_level)
    geopolygons = query.all()
    geopolygon_map = {str(geopolygon.osm_id): geopolygon for geopolygon in geopolygons}
    return geopolygon_map


def get_all_gtfs_feeds(
    db_session: Session,
    published_only: bool = True,
    w_extracted_locations_only: bool = False,
) -> Iterator[Gtfsfeed]:
    """
    Fetch all GTFS feeds.

    :param db_session: The database session.
    :param published_only: Include only the published feeds.
    :param w_extracted_locations_only: Whether to include only feeds with extracted locations.

    :return: The GTFS feeds in an iterator.
    """
    batch_size = int(os.getenv("BATCH_SIZE", "500"))
    batch_query = db_session.query(Gtfsfeed).order_by(Gtfsfeed.stable_id).yield_per(batch_size)
    if published_only:
        batch_query = batch_query.filter(Gtfsfeed.operational_status == "published")

    for batch in batched(batch_query, batch_size):
        stable_ids = (f.stable_id for f in batch)
        if w_extracted_locations_only:
            feed_query = apply_most_common_location_filter(db_session.query(Gtfsfeed), db_session)
            yield from (
                feed_query.filter(Gtfsfeed.stable_id.in_(stable_ids)).options(
                    joinedload(Gtfsfeed.latest_dataset)
                    .joinedload(Gtfsdataset.validation_reports)
                    .joinedload(Validationreport.features),
                    *get_joinedload_options(include_extracted_location_entities=True),
                )
            )
        else:
            yield from (
                db_session.query(Gtfsfeed)
                .outerjoin(Gtfsfeed.gtfsdatasets)
                .filter(Gtfsfeed.stable_id.in_(stable_ids))
                .options(
                    joinedload(Gtfsfeed.latest_dataset)
                    .joinedload(Gtfsdataset.validation_reports)
                    .joinedload(Validationreport.features),
                    *get_joinedload_options(include_extracted_location_entities=False),
                )
            )


def get_gtfs_rt_feeds_query(
    limit: int | None,
    offset: int | None,
    provider: str | None,
    producer_url: str | None,
    entity_types: str | None,
    country_code: str | None,
    subdivision_name: str | None,
    municipality: str | None,
    is_official: bool | None,
    published_only: bool = True,
    db_session: Session = None,
) -> Query:
    """Get some (or all) GTFS Realtime feeds from the Mobility Database."""
    entity_types_list = entity_types.split(",") if entity_types else None

    # Validate entity types using the EntityType enum
    if entity_types_list:
        try:
            entity_types_list = [EntityType(et.strip()).value for et in entity_types_list]
        except ValueError:
            raise_internal_http_validation_error(
                "Entity types must be the value 'vp', 'sa', or 'tu'. "
                "When provided a list values must be separated by commas."
            )

    gtfs_rt_feed_filter = GtfsRtFeedFilter(
        stable_id=None,
        provider__ilike=provider,
        producer_url__ilike=producer_url,
        entity_types=EntityTypeFilter(name__in=entity_types_list),
        location=LocationFilter(
            country_code=country_code,
            subdivision_name__ilike=subdivision_name,
            municipality__ilike=municipality,
        ),
    )
    subquery = gtfs_rt_feed_filter.filter(
        select(Gtfsrealtimefeed.id)
        .join(Location, Gtfsrealtimefeed.locations, isouter=True)
        .join(Entitytype, Gtfsrealtimefeed.entitytypes)
    ).subquery()
    feed_query = db_session.query(Gtfsrealtimefeed).filter(Gtfsrealtimefeed.id.in_(subquery))

    if published_only:
        feed_query = feed_query.filter(Gtfsrealtimefeed.operational_status == "published")

    feed_query = feed_query.options(
        joinedload(Gtfsrealtimefeed.entitytypes),
        joinedload(Gtfsrealtimefeed.gtfs_feeds),
        *get_joinedload_options(),
    )
    feed_query = add_official_filter(feed_query, is_official)

    feed_query = feed_query.limit(limit).offset(offset)
    return feed_query


def add_official_filter(query: Query, is_official: bool | None) -> Query:
    """
    Add the is_official filter to the query if necessary
    """
    if is_official is not None:
        if is_official:
            query = query.filter(Feed.official.is_(True))
        else:
            query = query.filter(or_(Feed.official.is_(False), Feed.official.is_(None)))
    return query


def get_all_gtfs_rt_feeds(
    db_session: Session,
    published_only: bool = True,
    batch_size: int = 250,
    w_extracted_locations_only: bool = False,
) -> Iterator[Gtfsrealtimefeed]:
    """
    Fetch all GTFS realtime feeds.

    :param db_session: The database session.
    :param published_only: Include only the published feeds.
    :param batch_size: The number of feeds to fetch from the database at a time.
        A lower value means less memory but more queries.
    :param w_extracted_locations_only: Whether to include only feeds with extracted locations.

    :return: The GTFS realtime feeds in an iterator.
    """
    batched_query = (
        db_session.query(Gtfsrealtimefeed.stable_id).order_by(Gtfsrealtimefeed.stable_id).yield_per(batch_size)
    )
    if published_only:
        batched_query = batched_query.filter(Gtfsrealtimefeed.operational_status == "published")

    for batch in batched(batched_query, batch_size):
        stable_ids = (f.stable_id for f in batch)
        if w_extracted_locations_only:
            feed_query = apply_most_common_location_filter(db_session.query(Gtfsrealtimefeed), db_session)
            yield from (
                feed_query.filter(Gtfsrealtimefeed.stable_id.in_(stable_ids))
                .options(
                    joinedload(Gtfsrealtimefeed.entitytypes),
                    joinedload(Gtfsrealtimefeed.gtfs_feeds),
                    *get_joinedload_options(include_extracted_location_entities=True),
                )
                .order_by(Gtfsfeed.stable_id)
            )
        else:
            yield from (
                db_session.query(Gtfsrealtimefeed)
                .filter(Gtfsrealtimefeed.stable_id.in_(stable_ids))
                .options(
                    joinedload(Gtfsrealtimefeed.entitytypes),
                    joinedload(Gtfsrealtimefeed.gtfs_feeds),
                    *get_joinedload_options(include_extracted_location_entities=False),
                )
            )


def apply_bounding_filtering(
    query: Query,
    bounding_latitudes: str,
    bounding_longitudes: str,
    bounding_filter_method: str,
) -> Query:
    """Create a new query based on the bounding parameters."""

    if not bounding_latitudes or not bounding_longitudes or not bounding_filter_method:
        return query

    if (
        len(bounding_latitudes_tokens := bounding_latitudes.split(",")) != 2
        or len(bounding_longitudes_tokens := bounding_longitudes.split(",")) != 2
    ):
        raise_internal_http_validation_error(
            invalid_bounding_coordinates.format(bounding_latitudes, bounding_longitudes)
        )
    min_latitude, max_latitude = bounding_latitudes_tokens
    min_longitude, max_longitude = bounding_longitudes_tokens
    try:
        min_latitude = float(min_latitude)
        max_latitude = float(max_latitude)
        min_longitude = float(min_longitude)
        max_longitude = float(max_longitude)
    except ValueError:
        raise_internal_http_validation_error(
            invalid_bounding_coordinates.format(bounding_latitudes, bounding_longitudes)
        )
    points = [
        (min_longitude, min_latitude),
        (min_longitude, max_latitude),
        (max_longitude, max_latitude),
        (max_longitude, min_latitude),
        (min_longitude, min_latitude),
    ]
    wkt_polygon = f"POLYGON(({', '.join(f'{lon} {lat}' for lon, lat in points)}))"
    bounding_box = WKTElement(
        wkt_polygon,
        srid=Gtfsdataset.bounding_box.type.srid,
    )
    query = query.join(Gtfsdataset, Gtfsdataset.feed_id == Gtfsfeed.id)

    if bounding_filter_method == "partially_enclosed":
        return query.filter(
            or_(
                Gtfsdataset.bounding_box.ST_Overlaps(bounding_box),
                Gtfsdataset.bounding_box.ST_Contains(bounding_box),
            )
        )
    elif bounding_filter_method == "completely_enclosed":
        return query.filter(bounding_box.ST_Covers(Gtfsdataset.bounding_box))
    elif bounding_filter_method == "disjoint":
        return query.filter(Gtfsdataset.bounding_box.ST_Disjoint(bounding_box))
    else:
        raise_internal_http_validation_error(invalid_bounding_method.format(bounding_filter_method))


def get_joinedload_options(include_extracted_location_entities: bool = False) -> [_AbstractLoad]:
    """
    Returns common joinedload options for feeds queries.
    :param include_extracted_location_entities: Whether to include extracted location entities.

    :return: A list of joinedload options.
    """
    joinedload_options = []
    if include_extracted_location_entities:
        joinedload_options = [contains_eager(Feed.feedosmlocationgroups).joinedload(Feedosmlocationgroup.group)]
    return joinedload_options + [
        joinedload(Feed.locations),
        joinedload(Feed.externalids),
        joinedload(Feed.redirectingids).joinedload(Redirectingid.target),
        joinedload(Feed.officialstatushistories),
    ]


def get_gbfs_feeds_query(
    db_session: Session,
    stable_id: Optional[str] = None,
    provider: Optional[str] = None,
    producer_url: Optional[str] = None,
    country_code: Optional[str] = None,
    subdivision_name: Optional[str] = None,
    municipality: Optional[str] = None,
    system_id: Optional[str] = None,
    version: Optional[str] = None,
) -> Query:
    gbfs_feed_filter = GbfsFeedFilter(
        stable_id=stable_id,
        provider__ilike=provider,
        producer_url__ilike=producer_url,
        system_id=system_id,
        location=LocationFilter(
            country_code=country_code,
            subdivision_name__ilike=subdivision_name,
            municipality__ilike=municipality,
        )
        if country_code or subdivision_name or municipality
        else None,
        version=GbfsVersionFilter(
            version=version,
        )
        if version
        else None,
    )
    # Subquery: latest report per version
    latest_report_subq = (
        db_session.query(
            Gbfsvalidationreport.gbfs_version_id.label("gbfs_version_id"),
            func.max(Gbfsvalidationreport.validated_at).label("latest_validated_at"),
        )
        .group_by(Gbfsvalidationreport.gbfs_version_id)
        .subquery()
    )

    # Join validation reports filtered by latest `validated_at`
    query = gbfs_feed_filter.filter(
        db_session.query(Gbfsfeed)
        .outerjoin(Location, Gbfsfeed.locations)
        .outerjoin(Gbfsfeed.gbfsversions)
        .outerjoin(latest_report_subq, Gbfsversion.id == latest_report_subq.c.gbfs_version_id)
        .outerjoin(
            Gbfsvalidationreport,
            and_(
                Gbfsversion.id == Gbfsvalidationreport.gbfs_version_id,
                Gbfsvalidationreport.validated_at == latest_report_subq.c.latest_validated_at,
            ),
        )
        .options(
            contains_eager(Gbfsfeed.gbfsversions).contains_eager(Gbfsversion.gbfsvalidationreports),
            contains_eager(Gbfsfeed.gbfsversions).joinedload(Gbfsversion.gbfsendpoints),
            joinedload(Feed.locations),
            joinedload(Feed.externalids),
            joinedload(Feed.redirectingids).joinedload(Redirectingid.target),
        )
    )
    return query
