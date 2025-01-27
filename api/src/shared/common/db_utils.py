from geoalchemy2 import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import joinedload, Session
from sqlalchemy.orm.query import Query
from sqlalchemy.orm.strategy_options import _AbstractLoad

from shared.database_gen.sqlacodegen_models import (
    Feed,
    Gtfsdataset,
    Gtfsfeed,
    Location,
    Validationreport,
    Gtfsrealtimefeed,
    Entitytype,
    Redirectingid,
)

from shared.feed_filters.gtfs_feed_filter import GtfsFeedFilter, LocationFilter
from shared.feed_filters.gtfs_rt_feed_filter import GtfsRtFeedFilter, EntityTypeFilter

from .entity_type_enum import EntityType

from sqlalchemy import or_

from .error_handling import raise_internal_http_validation_error, invalid_bounding_coordinates, invalid_bounding_method


def get_gtfs_feeds_query(
    limit: int | None,
    offset: int | None,
    provider: str | None,
    producer_url: str | None,
    country_code: str | None,
    subdivision_name: str | None,
    municipality: str | None,
    dataset_latitudes: str | None,
    dataset_longitudes: str | None,
    bounding_filter_method: str | None,
    is_official: bool = False,
    include_wip: bool = False,
    db_session: Session = None,
) -> Query[any]:
    """Get the DB query to use to retrieve the GTFS feeds.."""
    gtfs_feed_filter = GtfsFeedFilter(
        stable_id=None,
        provider__ilike=provider,
        producer_url__ilike=producer_url,
        location=LocationFilter(
            country_code=country_code,
            subdivision_name__ilike=subdivision_name,
            municipality__ilike=municipality,
        ),
    )

    subquery = gtfs_feed_filter.filter(select(Gtfsfeed.id).join(Location, Gtfsfeed.locations))
    subquery = apply_bounding_filtering(
        subquery, dataset_latitudes, dataset_longitudes, bounding_filter_method
    ).subquery()

    feed_query = db_session.query(Gtfsfeed).filter(Gtfsfeed.id.in_(subquery))
    if not include_wip:
        feed_query = feed_query.filter(
            or_(Gtfsfeed.operational_status == None, Gtfsfeed.operational_status != "wip")  # noqa: E711
        )

    feed_query = feed_query.options(
        joinedload(Gtfsfeed.gtfsdatasets)
        .joinedload(Gtfsdataset.validation_reports)
        .joinedload(Validationreport.notices),
        *get_joinedload_options(),
    ).order_by(Gtfsfeed.provider, Gtfsfeed.stable_id)
    if is_official:
        feed_query = feed_query.filter(Feed.official)
    feed_query = feed_query.limit(limit).offset(offset)
    return feed_query


def get_all_gtfs_feeds_query(
    include_wip: bool = False,
    db_session: Session = None,
) -> Query[any]:
    """Get the DB query to use to retrieve all the GTFS feeds, filtering out the WIP is needed"""

    feed_query = db_session.query(Gtfsfeed)

    if not include_wip:
        feed_query = feed_query.filter(
            or_(Gtfsfeed.operational_status == None, Gtfsfeed.operational_status != "wip")  # noqa: E711
        )

    feed_query = feed_query.options(
        joinedload(Gtfsfeed.gtfsdatasets)
        .joinedload(Gtfsdataset.validation_reports)
        .joinedload(Validationreport.features),
        *get_joinedload_options(),
    ).order_by(Gtfsfeed.stable_id)

    return feed_query


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
    include_wip: bool = False,
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
        .join(Location, Gtfsrealtimefeed.locations)
        .join(Entitytype, Gtfsrealtimefeed.entitytypes)
    ).subquery()
    feed_query = db_session.query(Gtfsrealtimefeed).filter(Gtfsrealtimefeed.id.in_(subquery))

    if not include_wip:
        feed_query = feed_query.filter(
            or_(
                Gtfsrealtimefeed.operational_status == None,  # noqa: E711
                Gtfsrealtimefeed.operational_status != "wip",
            )
        )

    feed_query = feed_query.options(
        joinedload(Gtfsrealtimefeed.entitytypes),
        joinedload(Gtfsrealtimefeed.gtfs_feeds),
        *get_joinedload_options(),
    )
    if is_official:
        feed_query = feed_query.filter(Feed.official)
    feed_query = feed_query.limit(limit).offset(offset)
    return feed_query


def get_all_gtfs_rt_feeds_query(
    include_wip: bool = False,
    db_session: Session = None,
) -> Query:
    """Get the DB query to use to retrieve all the GTFS rt feeds, filtering out the WIP is needed"""
    feed_query = db_session.query(Gtfsrealtimefeed)

    if not include_wip:
        feed_query = feed_query.filter(
            or_(
                Gtfsrealtimefeed.operational_status == None,  # noqa: E711
                Gtfsrealtimefeed.operational_status != "wip",
            )
        )

    feed_query = feed_query.options(
        joinedload(Gtfsrealtimefeed.entitytypes),
        joinedload(Gtfsrealtimefeed.gtfs_feeds),
        *get_joinedload_options(),
    ).order_by(Gtfsfeed.stable_id)

    return feed_query


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


def get_joinedload_options() -> [_AbstractLoad]:
    """Returns common joinedload options for feeds queries."""
    return [
        joinedload(Feed.locations),
        joinedload(Feed.externalids),
        joinedload(Feed.redirectingids).joinedload(Redirectingid.target),
        joinedload(Feed.officialstatushistories),
    ]
