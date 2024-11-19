from datetime import datetime
from typing import List, Union, TypeVar

from sqlalchemy import or_
from sqlalchemy import select, desc
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.query import Query

from database.database import Database
from database_gen.sqlacodegen_models import (
    Feed,
    Gtfsdataset,
    Gtfsfeed,
    Gtfsrealtimefeed,
    Location,
    Validationreport,
    t_location_with_translations_en,
    Entitytype,
    Officialstatushistory,
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
from feeds.impl.models.entity_type_enum import EntityType
from feeds.impl.models.gtfs_feed_impl import GtfsFeedImpl
from feeds.impl.models.gtfs_rt_feed_impl import GtfsRTFeedImpl
from feeds_gen.apis.feeds_api_base import BaseFeedsApi
from feeds_gen.models.basic_feed import BasicFeed
from feeds_gen.models.gtfs_dataset import GtfsDataset
from feeds_gen.models.gtfs_feed import GtfsFeed
from feeds_gen.models.gtfs_rt_feed import GtfsRTFeed
from middleware.request_context import is_user_email_restricted
from utils.date_utils import valid_iso_date
from utils.location_translation import (
    create_location_translation_object,
    LocationTranslation,
    get_feeds_location_translations,
)

T = TypeVar("T", bound="BasicFeed")


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
            .filter(Feed.data_type != "gbfs")  # Filter out GBFS feeds
            .filter(
                or_(
                    Feed.operational_status == None,  # noqa: E711
                    Feed.operational_status != "wip",
                    not is_user_email_restricted(),  # Allow all feeds to be returned if the user is not restricted
                )
            )
            .first()
        )
        if feed:
            return BasicFeedImpl.from_orm(feed)
        else:
            raise_http_error(404, feed_not_found.format(id))

    @staticmethod
    def _get_latest_official_status_subquery(feed_query: Query, is_official: bool) -> Query:
        """Get the latest official status per feed using a subquery."""
        # Subquery to get the latest official status per feed
        latest_status_subquery = (
            Database()
            .get_query_model(Officialstatushistory)
            .with_entities(
                Officialstatushistory.feed_id,
                Officialstatushistory.is_official,
                Officialstatushistory.timestamp,
            )
            .distinct(Officialstatushistory.feed_id)  # DISTINCT ON feed_id
            .order_by(Officialstatushistory.feed_id, desc(Officialstatushistory.timestamp))
            .subquery()
        )

        # Join with the main query and filter by is_official
        return feed_query.join(
            latest_status_subquery,
            latest_status_subquery.c.feed_id == Feed.id,
        ).filter(latest_status_subquery.c.is_official == is_official)

    def get_feeds(
        self,
        limit: int,
        offset: int,
        status: str,
        provider: str,
        producer_url: str,
        is_official: bool,
    ) -> List[BasicFeed]:
        """Get some (or all) feeds from the Mobility Database."""
        feed_filter = FeedFilter(
            status=status, provider__ilike=provider, producer_url__ilike=producer_url, stable_id=None
        )
        feed_query = feed_filter.filter(Database().get_query_model(Feed))
        if is_official:
            feed_query = self._get_latest_official_status_subquery(feed_query, is_official)
        feed_query = feed_query.filter(Feed.data_type != "gbfs")  # Filter out GBFS feeds
        feed_query = feed_query.filter(
            or_(
                Feed.operational_status == None,  # noqa: E711
                Feed.operational_status != "wip",
                not is_user_email_restricted(),  # Allow all feeds to be returned if the user is not restricted
            )
        )
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
        feed, translations = self._get_gtfs_feed(id)
        if feed:
            return GtfsFeedImpl.from_orm(feed, translations)
        else:
            raise_http_error(404, gtfs_feed_not_found.format(id))

    @staticmethod
    def _get_gtfs_feed(stable_id: str) -> tuple[Gtfsfeed | None, dict[str, LocationTranslation]]:
        results = (
            FeedFilter(
                stable_id=stable_id,
                status=None,
                provider__ilike=None,
                producer_url__ilike=None,
            )
            .filter(Database().get_session().query(Gtfsfeed, t_location_with_translations_en))
            .filter(
                or_(
                    Gtfsfeed.operational_status == None,  # noqa: E711
                    Gtfsfeed.operational_status != "wip",
                    not is_user_email_restricted(),  # Allow all feeds to be returned if the user is not restricted
                )
            )
            .outerjoin(Location, Feed.locations)
            .outerjoin(t_location_with_translations_en, Location.id == t_location_with_translations_en.c.location_id)
            .options(
                joinedload(Gtfsfeed.gtfsdatasets)
                .joinedload(Gtfsdataset.validation_reports)
                .joinedload(Validationreport.notices),
                *BasicFeedImpl.get_joinedload_options(),
            )
        ).all()
        if len(results) > 0 and results[0].Gtfsfeed:
            translations = {result[1]: create_location_translation_object(result) for result in results}
            return results[0].Gtfsfeed, translations
        return None, {}

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
            .filter(
                or_(
                    Feed.operational_status == None,  # noqa: E711
                    Feed.operational_status != "wip",
                    not is_user_email_restricted(),  # Allow all feeds to be returned if the user is not restricted
                )
            )
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
        is_official: bool,
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

        subquery = gtfs_feed_filter.filter(select(Gtfsfeed.id).join(Location, Gtfsfeed.locations))
        subquery = DatasetsApiImpl.apply_bounding_filtering(
            subquery, dataset_latitudes, dataset_longitudes, bounding_filter_method
        ).subquery()

        feed_query = (
            Database()
            .get_session()
            .query(Gtfsfeed)
            .filter(Gtfsfeed.id.in_(subquery))
            .filter(
                or_(
                    Gtfsfeed.operational_status == None,  # noqa: E711
                    Gtfsfeed.operational_status != "wip",
                    not is_user_email_restricted(),  # Allow all feeds to be returned if the user is not restricted
                )
            )
            .options(
                joinedload(Gtfsfeed.gtfsdatasets)
                .joinedload(Gtfsdataset.validation_reports)
                .joinedload(Validationreport.notices),
                *BasicFeedImpl.get_joinedload_options(),
            )
            .order_by(Gtfsfeed.provider, Gtfsfeed.stable_id)
        )
        if is_official:
            feed_query = self._get_latest_official_status_subquery(feed_query, is_official)
        feed_query = feed_query.limit(limit).offset(offset)
        return self._get_response(feed_query, GtfsFeedImpl)

    def get_gtfs_rt_feed(
        self,
        id: str,
    ) -> GtfsRTFeed:
        """Get the specified GTFS Realtime feed from the Mobility Database."""
        gtfs_rt_feed_filter = GtfsRtFeedFilter(
            stable_id=id,
            provider__ilike=None,
            producer_url__ilike=None,
            entity_types=None,
            location=None,
        )
        results = gtfs_rt_feed_filter.filter(
            Database()
            .get_session()
            .query(Gtfsrealtimefeed, t_location_with_translations_en)
            .filter(
                or_(
                    Gtfsrealtimefeed.operational_status == None,  # noqa: E711
                    Gtfsrealtimefeed.operational_status != "wip",
                    not is_user_email_restricted(),  # Allow all feeds to be returned if the user is not restricted
                )
            )
            .outerjoin(Location, Gtfsrealtimefeed.locations)
            .outerjoin(t_location_with_translations_en, Location.id == t_location_with_translations_en.c.location_id)
            .options(
                joinedload(Gtfsrealtimefeed.entitytypes),
                joinedload(Gtfsrealtimefeed.gtfs_feeds),
                *BasicFeedImpl.get_joinedload_options(),
            )
        ).all()

        if len(results) > 0 and results[0].Gtfsrealtimefeed:
            translations = {result[1]: create_location_translation_object(result) for result in results}
            return GtfsRTFeedImpl.from_orm(results[0].Gtfsrealtimefeed, translations)
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
        is_official: bool,
    ) -> List[GtfsRTFeed]:
        """Get some (or all) GTFS Realtime feeds from the Mobility Database."""
        entity_types_list = entity_types.split(",") if entity_types else None

        # Validate entity types using the EntityType enum
        if entity_types_list:
            try:
                entity_types_list = [EntityType(et.strip()).value for et in entity_types_list]
            except ValueError:
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
        subquery = gtfs_rt_feed_filter.filter(
            select(Gtfsrealtimefeed.id)
            .join(Location, Gtfsrealtimefeed.locations)
            .join(Entitytype, Gtfsrealtimefeed.entitytypes)
        ).subquery()
        feed_query = (
            Database()
            .get_session()
            .query(Gtfsrealtimefeed)
            .filter(Gtfsrealtimefeed.id.in_(subquery))
            .filter(
                or_(
                    Gtfsrealtimefeed.operational_status == None,  # noqa: E711
                    Gtfsrealtimefeed.operational_status != "wip",
                    not is_user_email_restricted(),  # Allow all feeds to be returned if the user is not restricted
                )
            )
            .options(
                joinedload(Gtfsrealtimefeed.entitytypes),
                joinedload(Gtfsrealtimefeed.gtfs_feeds),
                *BasicFeedImpl.get_joinedload_options(),
            )
            .order_by(Gtfsrealtimefeed.provider, Gtfsrealtimefeed.stable_id)
        )
        if is_official:
            feed_query = self._get_latest_official_status_subquery(feed_query, is_official)
        feed_query = feed_query.limit(limit).offset(offset)
        return self._get_response(feed_query, GtfsRTFeedImpl)

    @staticmethod
    def _get_response(feed_query: Query, impl_cls: type[T]) -> List[T]:
        """Get the response for the feed query."""
        results = feed_query.all()
        location_translations = get_feeds_location_translations(results)
        response = [impl_cls.from_orm(feed, location_translations) for feed in results]
        return list({feed.id: feed for feed in response}.values())

    def get_gtfs_feed_gtfs_rt_feeds(
        self,
        id: str,
    ) -> List[GtfsRTFeed]:
        """Get a list of GTFS Realtime related to a GTFS feed."""
        feed, translations = self._get_gtfs_feed(id)
        if feed:
            return [GtfsRTFeedImpl.from_orm(gtfs_rt_feed, translations) for gtfs_rt_feed in feed.gtfs_rt_feeds]
        else:
            raise_http_error(404, gtfs_feed_not_found.format(id))
