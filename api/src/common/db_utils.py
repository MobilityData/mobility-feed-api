from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.query import Query

from common.common import apply_bounding_filtering, get_joinedload_options
from common.error_handling import raise_internal_http_validation_error
from database.database import Database
from database_gen.sqlacodegen_models import (
    Gtfsdataset,
    Gtfsfeed,
    Location,
    Validationreport,
    Gtfsrealtimefeed,
    Entitytype,
)

from feeds.filters.gtfs_feed_filter import GtfsFeedFilter, LocationFilter
from feeds.filters.gtfs_rt_feed_filter import GtfsRtFeedFilter, EntityTypeFilter

from common.entity_type_enum import EntityType

from middleware.request_context import is_user_email_restricted
from sqlalchemy import or_


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
    never_return_wip: bool = False,
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

    feed_query = Database().get_session().query(Gtfsfeed).filter(Gtfsfeed.id.in_(subquery))
    if never_return_wip:
        feed_query = feed_query.filter(
            or_(Gtfsfeed.operational_status == None, Gtfsfeed.operational_status != "wip")  # noqa: E711
        )
    else:
        feed_query = feed_query.filter(
            or_(
                Gtfsfeed.operational_status == None,  # noqa: E711
                Gtfsfeed.operational_status != "wip",
                not is_user_email_restricted(),  # Allow all feeds to be returned if the user is not restricted
            )
        )

    feed_query = (
        feed_query.options(
            joinedload(Gtfsfeed.gtfsdatasets)
            .joinedload(Gtfsdataset.validation_reports)
            .joinedload(Validationreport.notices),
            *get_joinedload_options(),
        )
        .order_by(Gtfsfeed.provider, Gtfsfeed.stable_id)
        .limit(limit)
        .offset(offset)
    )
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
    never_return_wip: bool = False,
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
    feed_query = Database().get_session().query(Gtfsrealtimefeed).filter(Gtfsrealtimefeed.id.in_(subquery))
    if never_return_wip:
        feed_query = feed_query.filter(
            or_(Gtfsfeed.operational_status == None, Gtfsfeed.operational_status != "wip")  # noqa: E711
        )
    else:
        feed_query = feed_query.filter(
            or_(
                Gtfsrealtimefeed.operational_status == None,  # noqa: E711
                Gtfsrealtimefeed.operational_status != "wip",
                not is_user_email_restricted(),  # Allow all feeds to be returned if the user is not restricted
            )
        )

    feed_query = (
        feed_query.options(
            joinedload(Gtfsrealtimefeed.entitytypes),
            joinedload(Gtfsrealtimefeed.gtfs_feeds),
            *get_joinedload_options(),
        )
        .order_by(Gtfsrealtimefeed.provider, Gtfsrealtimefeed.stable_id)
        .limit(limit)
        .offset(offset)
    )
    return feed_query
