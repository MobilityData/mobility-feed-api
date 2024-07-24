from datetime import datetime
from typing import List, Union

from sqlalchemy.orm import joinedload

from database.database import Database
from database_gen.sqlacodegen_models import (
    Feed,
    Gtfsdataset,
    Gtfsfeed,
    Gtfsrealtimefeed,
    Location,
    Validationreport,
    Entitytype,
)
from feeds.filters.feed_filter import FeedFilter
from feeds.filters.gtfs_dataset_filter import GtfsDatasetFilter
from feeds.filters.gtfs_feed_filter import GtfsFeedFilter, LocationFilter
from feeds.filters.gtfs_rt_feed_filter import GtfsRtFeedFilter, EntityTypeFilter
from feeds.impl.datasets_api_impl import DatasetsApiImpl
from feeds.impl.error_handling import (
    raise_http_validation_error,
    invalid_date_message,
    raise_http_error,
    feed_not_found,
    gtfs_feed_not_found,
    gtfs_rt_feed_not_found,
)
from feeds.impl.models.basic_feed_impl import BasicFeedImpl
from feeds.impl.models.gtfs_feed_impl import GtfsFeedImpl
from feeds.impl.models.gtfs_rt_feed_impl import GtfsRTFeedImpl
from feeds_gen.apis.feeds_api_base import BaseFeedsApi
from feeds_gen.models.basic_feed import BasicFeed
from feeds_gen.models.gtfs_dataset import GtfsDataset
from feeds_gen.models.gtfs_feed import GtfsFeed
from feeds_gen.models.gtfs_rt_feed import GtfsRTFeed
from utils.date_utils import valid_iso_date


class FeedsApiImpl(BaseFeedsApi):
    """
    This class represents the implementation of the `/feeds` endpoints.
    All methods from the parent class `feeds_gen.apis.feeds_api_base.BaseFeedsApi` should be implemented.
    If a method is left blank the associated endpoint will return a 500 HTTP response.
    """

    APIFeedType = Union[BasicFeed, GtfsFeed, GtfsRTFeed]

    def get_feed(
        self,
        id: str,
    ) -> BasicFeed:
        """Get the specified feed from the Mobility Database."""
        feed = (
            FeedFilter(stable_id=id, provider__ilike=None, producer_url__ilike=None, status=None)
            .filter(Database().get_query_model(Feed))
            .first()
        )
        if feed:
            return BasicFeedImpl.from_orm(feed)
        else:
            raise_http_error(404, feed_not_found.format(id))

    def get_feeds(
        self,
        limit: int,
        offset: int,
        status: str,
        provider: str,
        producer_url: str,
    ) -> List[BasicFeed]:
        """Get some (or all) feeds from the Mobility Database."""
        feed_filter = FeedFilter(
            status=status, provider__ilike=provider, producer_url__ilike=producer_url, stable_id=None
        )
        feed_query = feed_filter.filter(Database().get_query_model(Feed))
        # Results are sorted by provider
        feed_query = feed_query.order_by(Feed.provider, Feed.stable_id)
        feed_query = feed_query.options(*BasicFeedImpl.get_joinedload_options())
        if limit is not None:
            feed_query = feed_query.limit(limit)
        if offset is not None:
            feed_query = feed_query.offset(offset)

        results = feed_query.all()
        return [BasicFeedImpl.from_orm(feed) for feed in results]

    def get_gtfs_feed(
        self,
        id: str,
    ) -> GtfsFeed:
        """Get the specified gtfs feed from the Mobility Database."""
        feed = (
            FeedFilter(
                stable_id=id,
                status=None,
                provider__ilike=None,
                producer_url__ilike=None,
            )
            .filter(Database().get_query_model(Gtfsfeed))
            .first()
        )
        if feed:
            return GtfsFeedImpl.from_orm(feed)
        else:
            raise_http_error(404, gtfs_feed_not_found.format(id))

    def get_gtfs_feed_datasets(
        self,
        gtfs_feed_id: str,
        latest: bool,
        limit: int,
        offset: int,
        downloaded_after: str,
        downloaded_before: str,
    ) -> List[GtfsDataset]:
        """Get a list of datasets related to a feed."""
        if downloaded_before and not valid_iso_date(downloaded_before):
            raise_http_validation_error(invalid_date_message.format("downloaded_before"))
        if downloaded_after and not valid_iso_date(downloaded_after):
            raise_http_validation_error(invalid_date_message.format("downloaded_after"))

        # First make sure the feed exists. If not it's an error 404
        feed = (
            FeedFilter(
                stable_id=gtfs_feed_id,
                status=None,
                provider__ilike=None,
                producer_url__ilike=None,
            )
            .filter(Database().get_query_model(Gtfsfeed))
            .first()
        )

        if not feed:
            raise_http_error(404, f"Feed with id {gtfs_feed_id} not found")

        # Replace Z with +00:00 to make the datetime object timezone aware
        # Due to https://github.com/python/cpython/issues/80010, once migrate to Python 3.11, we can use fromisoformat
        query = GtfsDatasetFilter(
            downloaded_at__lte=datetime.fromisoformat(downloaded_before.replace("Z", "+00:00"))
            if downloaded_before
            else None,
            downloaded_at__gte=datetime.fromisoformat(downloaded_after.replace("Z", "+00:00"))
            if downloaded_after
            else None,
        ).filter(DatasetsApiImpl.create_dataset_query().filter(Feed.stable_id == gtfs_feed_id))

        if latest:
            query = query.filter(Gtfsdataset.latest)

        return DatasetsApiImpl.get_datasets_gtfs(query, limit=limit, offset=offset)

    def get_gtfs_feeds(
        self,
        limit: int,
        offset: int,
        provider: str,
        producer_url: str,
        country_code: str,
        subdivision_name: str,
        municipality: str,
        dataset_latitudes: str,
        dataset_longitudes: str,
        bounding_filter_method: str,
    ) -> List[GtfsFeed]:
        """Get some (or all) GTFS feeds from the Mobility Database."""
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
        gtfs_feed_query = gtfs_feed_filter.filter(Database().get_query_model(Gtfsfeed))

        gtfs_feed_query = gtfs_feed_query.outerjoin(Location, Feed.locations).options(
            joinedload(Gtfsfeed.gtfsdatasets)
            .joinedload(Gtfsdataset.validation_reports)
            .joinedload(Validationreport.notices),
            *BasicFeedImpl.get_joinedload_options(),
        )
        gtfs_feed_query = gtfs_feed_query.order_by(Gtfsfeed.provider, Gtfsfeed.stable_id)
        gtfs_feed_query = DatasetsApiImpl.apply_bounding_filtering(
            gtfs_feed_query, dataset_latitudes, dataset_longitudes, bounding_filter_method
        )
        if limit is not None:
            gtfs_feed_query = gtfs_feed_query.limit(limit)
        if offset is not None:
            gtfs_feed_query = gtfs_feed_query.offset(offset)
        results = gtfs_feed_query.all()
        return [GtfsFeedImpl.from_orm(gtfs_feed) for gtfs_feed in results]

    def get_gtfs_rt_feed(
        self,
        id: str,
    ) -> GtfsRTFeed:
        """Get the specified GTFS Realtime feed from the Mobility Database."""
        feed = (
            GtfsRtFeedFilter(
                stable_id=id,
                provider__ilike=None,
                producer_url__ilike=None,
                entity_types=None,
                location=None,
            )
            .filter(Database().get_query_model(Gtfsrealtimefeed))
            .first()
        )
        if feed:
            return GtfsRTFeedImpl.from_orm(feed)
        else:
            raise_http_error(404, gtfs_rt_feed_not_found.format(id))

    def get_gtfs_rt_feeds(
        self,
        limit: int,
        offset: int,
        provider: str,
        producer_url: str,
        entity_types: str,
        country_code: str,
        subdivision_name: str,
        municipality: str,
    ) -> List[GtfsRTFeed]:
        """Get some (or all) GTFS Realtime feeds from the Mobility Database."""
        entity_types_list = entity_types.split(",") if entity_types else None

        # Validate entity types are in [vp, sa, tu]
        if entity_types_list and not all(entity_type in ["vp", "sa", "tu"] for entity_type in entity_types_list):
            raise_http_validation_error(
                "Entity types must be the value 'vp,' 'sa,' or 'tu,'. "
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
        gtfs_rt_feed_query = gtfs_rt_feed_filter.filter(Database().get_query_model(Gtfsrealtimefeed)).options(
            *BasicFeedImpl.get_joinedload_options()
        )
        gtfs_rt_feed_query = gtfs_rt_feed_query.outerjoin(Entitytype, Gtfsrealtimefeed.entitytypes)
        gtfs_rt_feed_query = gtfs_rt_feed_query.outerjoin(Location, Feed.locations)

        gtfs_rt_feed_query = gtfs_rt_feed_query.order_by(Gtfsrealtimefeed.provider, Gtfsrealtimefeed.stable_id)
        if limit is not None:
            gtfs_rt_feed_query = gtfs_rt_feed_query.limit(limit)
        if offset is not None:
            gtfs_rt_feed_query = gtfs_rt_feed_query.offset(offset)
        results = gtfs_rt_feed_query.all()
        return [GtfsRTFeedImpl.from_orm(gtfs_rt_feed) for gtfs_rt_feed in results]

    def get_gtfs_feed_gtfs_rt_feeds(
        self,
        id: str,
    ) -> List[GtfsRTFeed]:
        """Get a list of GTFS Realtime related to a GTFS feed."""
        feed = (
            FeedFilter(
                stable_id=id,
                status=None,
                provider__ilike=None,
                producer_url__ilike=None,
            )
            .filter(Database().get_query_model(Gtfsfeed))
            .first()
        )
        if feed:
            return [GtfsRTFeedImpl.from_orm(gtfs_rt_feed) for gtfs_rt_feed in feed.gtfs_rt_feeds]
        else:
            raise_http_error(404, gtfs_feed_not_found.format(id))
