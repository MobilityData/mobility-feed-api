from datetime import datetime
from typing import List, Union, TypeVar, Optional

from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.orm import joinedload, contains_eager, selectinload, Session
from sqlalchemy.orm.query import Query

from feeds.impl.datasets_api_impl import DatasetsApiImpl
from feeds.impl.error_handling import raise_http_error, raise_http_validation_error, convert_exception
from shared.db_models.entity_type_enum import EntityType
from shared.db_models.feed_impl import FeedImpl
from shared.db_models.gbfs_feed_impl import GbfsFeedImpl
from shared.db_models.gtfs_feed_impl import GtfsFeedImpl
from shared.db_models.gtfs_rt_feed_impl import GtfsRTFeedImpl
from feeds_gen.apis.feeds_api_base import BaseFeedsApi
from feeds_gen.models.feed import Feed
from feeds_gen.models.gbfs_feed import GbfsFeed
from feeds_gen.models.gtfs_dataset import GtfsDataset
from feeds_gen.models.gtfs_feed import GtfsFeed
from feeds_gen.models.gtfs_rt_feed import GtfsRTFeed
from middleware.request_context import is_user_email_restricted
from shared.common.db_utils import (
    get_gtfs_feeds_query,
    get_gtfs_rt_feeds_query,
    get_joinedload_options,
    add_official_filter,
    get_gbfs_feeds_query,
)
from shared.common.error_handling import (
    invalid_date_message,
    feed_not_found,
    gtfs_feed_not_found,
    gtfs_rt_feed_not_found,
    InternalHTTPException,
    gbfs_feed_not_found,
)
from shared.database.database import Database, with_db_session
from shared.database_gen.sqlacodegen_models import (
    Feed as FeedOrm,
    Gtfsdataset,
    Gtfsfeed,
    Gtfsrealtimefeed,
    Location,
    Entitytype,
)
from shared.feed_filters.feed_filter import FeedFilter
from shared.feed_filters.gtfs_dataset_filter import GtfsDatasetFilter
from shared.feed_filters.gtfs_feed_filter import LocationFilter
from shared.feed_filters.gtfs_rt_feed_filter import GtfsRtFeedFilter, EntityTypeFilter
from utils.date_utils import valid_iso_date
from utils.logger import get_logger

T = TypeVar("T", bound="Feed")


class FeedsApiImpl(BaseFeedsApi):
    """
    This class represents the implementation of the `/feeds` endpoints.
    All methods from the parent class `feeds_gen.apis.feeds_api_base.BaseFeedsApi` should be implemented.
    If a method is left blank the associated endpoint will return a 500 HTTP response.
    """

    APIFeedType = Union[FeedOrm, GtfsFeed, GtfsRTFeed]

    def __init__(self) -> None:
        self.logger = get_logger("FeedsApiImpl")

    @with_db_session
    def get_feed(self, id: str, db_session: Session) -> Feed:
        """Get the specified feed from the Mobility Database."""
        is_email_restricted = is_user_email_restricted()
        self.logger.debug(f"User email is restricted: {is_email_restricted}")

        # Use an explicit LEFT OUTER JOIN and contains_eager so the License relationship
        # is populated from the same SQL result without causing N+1 queries.
        feed = (
            FeedFilter(stable_id=id, provider__ilike=None, producer_url__ilike=None, status=None)
            .filter(Database().get_query_model(db_session, FeedOrm))
            .outerjoin(FeedOrm.license)
            .options(contains_eager(FeedOrm.license))
            .filter(
                or_(
                    FeedOrm.operational_status == "published",
                    not is_email_restricted,  # Allow all feeds to be returned if the user is not restricted
                )
            )
            .first()
        )
        if feed:
            return FeedImpl.from_orm(feed)
        else:
            raise_http_error(404, feed_not_found.format(id))

    @with_db_session
    def get_feeds(
        self,
        limit: int,
        offset: int,
        status: str,
        provider: str,
        producer_url: str,
        is_official: bool,
        db_session: Session,
    ) -> List[Feed]:
        """Get some (or all) feeds from the Mobility Database."""
        is_email_restricted = is_user_email_restricted()
        self.logger.debug(f"User email is restricted: {is_email_restricted}")
        feed_filter = FeedFilter(
            status=status, provider__ilike=provider, producer_url__ilike=producer_url, stable_id=None
        )
        feed_query = feed_filter.filter(Database().get_query_model(db_session, FeedOrm))
        feed_query = add_official_filter(feed_query, is_official)
        feed_query = feed_query.filter(
            or_(
                FeedOrm.operational_status == "published",
                not is_email_restricted,  # Allow all feeds to be returned if the user is not restricted
            )
        )
        # Results are sorted by provider
        feed_query = feed_query.order_by(FeedOrm.provider, FeedOrm.stable_id)
        # Ensure license relationship is available to the model conversion without extra queries
        feed_query = feed_query.options(*get_joinedload_options(), selectinload(FeedOrm.license))
        if limit is not None:
            feed_query = feed_query.limit(limit)
        if offset is not None:
            feed_query = feed_query.offset(offset)

        results = feed_query.all()
        return [FeedImpl.from_orm(feed) for feed in results]

    @with_db_session
    def get_gtfs_feed(self, id: str, db_session: Session) -> GtfsFeed:
        """Get the specified gtfs feed from the Mobility Database."""
        feed = self._get_gtfs_feed(id, db_session)
        if feed:
            return GtfsFeedImpl.from_orm(feed)
        else:
            raise_http_error(404, gtfs_feed_not_found.format(id))

    def _get_gtfs_feed(
        self, stable_id: str, db_session: Session, include_options_for_joinedload: bool = True
    ) -> Optional[Gtfsfeed]:
        published_only = is_user_email_restricted()
        query = get_gtfs_feeds_query(
            db_session=db_session,
            stable_id=stable_id,
            include_options_for_joinedload=include_options_for_joinedload,
            published_only=published_only,
        )
        results = query.all()
        if len(results) == 0:
            return None
        return results[0]

    @with_db_session
    def get_gtfs_feed_datasets(
        self,
        gtfs_feed_id: str,
        latest: bool,
        limit: int,
        offset: int,
        downloaded_after: str,
        downloaded_before: str,
        db_session: Session,
    ) -> List[GtfsDataset]:
        """Get a list of datasets related to a feed."""
        if downloaded_before and not valid_iso_date(downloaded_before):
            raise_http_validation_error(invalid_date_message.format("downloaded_before"))
        if downloaded_after and not valid_iso_date(downloaded_after):
            raise_http_validation_error(invalid_date_message.format("downloaded_after"))

        # First make sure the feed exists. If not it's an error 404
        feed = self._get_gtfs_feed(gtfs_feed_id, db_session, include_options_for_joinedload=False)

        if not feed:
            raise_http_error(404, f"FeedOrm with id {gtfs_feed_id} not found")

        # Replace Z with +00:00 to make the datetime object timezone aware
        # Due to https://github.com/python/cpython/issues/80010, once migrate to Python 3.11, we can use fromisoformat
        query = GtfsDatasetFilter(
            downloaded_at__lte=(
                datetime.fromisoformat(downloaded_before.replace("Z", "+00:00")) if downloaded_before else None
            ),
            downloaded_at__gte=(
                datetime.fromisoformat(downloaded_after.replace("Z", "+00:00")) if downloaded_after else None
            ),
        ).filter(DatasetsApiImpl.create_dataset_query().filter(FeedOrm.stable_id == gtfs_feed_id))

        if latest:
            query = query.join(Gtfsfeed, Gtfsfeed.latest_dataset_id == Gtfsdataset.id)

        return DatasetsApiImpl.get_datasets_gtfs(query, session=db_session, limit=limit, offset=offset)

    @with_db_session
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
        db_session: Session,
    ) -> List[GtfsFeed]:
        try:
            published_only = is_user_email_restricted()
            feed_query = get_gtfs_feeds_query(
                limit=limit,
                offset=offset,
                provider=provider,
                producer_url=producer_url,
                country_code=country_code,
                subdivision_name=subdivision_name,
                municipality=municipality,
                dataset_latitudes=dataset_latitudes,
                dataset_longitudes=dataset_longitudes,
                bounding_filter_method=bounding_filter_method,
                is_official=is_official,
                published_only=published_only,
                db_session=db_session,
            )
        except InternalHTTPException as e:
            # get_gtfs_feeds_query cannot throw HTTPException since it's part of fastapi and it's
            # not necessarily deployed (e.g. for python functions). Instead it throws an InternalHTTPException
            # that needs to be converted to HTTPException before being thrown.
            raise convert_exception(e)

        return self._get_response(feed_query, GtfsFeedImpl)

    @with_db_session
    def get_gtfs_rt_feed(self, id: str, db_session: Session) -> GtfsRTFeed:
        """Get the specified GTFS Realtime feed from the Mobility Database."""
        gtfs_rt_feed_filter = GtfsRtFeedFilter(
            stable_id=id,
            provider__ilike=None,
            producer_url__ilike=None,
            entity_types=None,
            location=None,
        )
        results = gtfs_rt_feed_filter.filter(
            db_session.query(Gtfsrealtimefeed)
            .filter(
                or_(
                    Gtfsrealtimefeed.operational_status == "published",
                    not is_user_email_restricted(),  # Allow all feeds to be returned if the user is not restricted
                )
            )
            .outerjoin(Location, Gtfsrealtimefeed.locations)
            .options(
                joinedload(Gtfsrealtimefeed.entitytypes),
                joinedload(Gtfsrealtimefeed.gtfs_feeds),
                *get_joinedload_options(),
            )
        ).all()

        if len(results) > 0 and results[0]:
            return GtfsRTFeedImpl.from_orm(results[0])
        else:
            raise_http_error(404, gtfs_rt_feed_not_found.format(id))

    @with_db_session
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
        db_session: Session,
    ) -> List[GtfsRTFeed]:
        """Get some (or all) GTFS Realtime feeds from the Mobility Database."""
        try:
            published_only = is_user_email_restricted()
            feed_query = get_gtfs_rt_feeds_query(
                limit=limit,
                offset=offset,
                provider=provider,
                producer_url=producer_url,
                entity_types=entity_types,
                country_code=country_code,
                subdivision_name=subdivision_name,
                municipality=municipality,
                is_official=is_official,
                published_only=published_only,
                db_session=db_session,
            )
        except InternalHTTPException as e:
            raise convert_exception(e)

        return self._get_response(feed_query, GtfsRTFeedImpl)

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
            db_session.query(Gtfsrealtimefeed)
            .filter(Gtfsrealtimefeed.id.in_(subquery))
            .filter(
                or_(
                    Gtfsrealtimefeed.operational_status == "published",
                    not is_user_email_restricted(),  # Allow all feeds to be returned if the user is not restricted
                )
            )
            .options(
                joinedload(Gtfsrealtimefeed.entitytypes),
                joinedload(Gtfsrealtimefeed.gtfs_feeds),
                *get_joinedload_options(),
            )
            .order_by(Gtfsrealtimefeed.provider, Gtfsrealtimefeed.stable_id)
        )
        feed_query = add_official_filter(feed_query, is_official)

        feed_query = feed_query.limit(limit).offset(offset)
        return self._get_response(feed_query, GtfsRTFeedImpl)

    @staticmethod
    def _get_response(feed_query: Query, impl_cls: type[T]) -> List[T]:
        """Get the response for the feed query."""
        results = feed_query.all()
        response = [impl_cls.from_orm(feed) for feed in results]
        return list({feed.id: feed for feed in response}.values())

    @with_db_session
    def get_gtfs_feed_gtfs_rt_feeds(self, id: str, db_session: Session) -> List[GtfsRTFeed]:
        """Get a list of GTFS Realtime related to a GTFS feed."""
        feed = self._get_gtfs_feed(id, db_session)
        if feed:
            return [GtfsRTFeedImpl.from_orm(gtfs_rt_feed) for gtfs_rt_feed in feed.gtfs_rt_feeds]
        else:
            raise_http_error(404, gtfs_feed_not_found.format(id))

    @with_db_session
    def get_gbfs_feed(
        self,
        id: str,
        db_session: Session,
    ) -> GbfsFeed:
        """Get the specified GBFS feed from the Mobility Database."""
        result = get_gbfs_feeds_query(db_session, stable_id=id).one_or_none()
        if result:
            return GbfsFeedImpl.from_orm(result)
        else:
            raise_http_error(404, gbfs_feed_not_found.format(id))

    @with_db_session
    def get_gbfs_feeds(
        self,
        limit: int,
        offset: int,
        provider: str,
        producer_url: str,
        country_code: str,
        subdivision_name: str,
        municipality: str,
        system_id: str,
        version: str,
        db_session: Session,
    ) -> List[GbfsFeed]:
        query = get_gbfs_feeds_query(
            db_session=db_session,
            provider=provider,
            producer_url=producer_url,
            country_code=country_code,
            subdivision_name=subdivision_name,
            municipality=municipality,
            system_id=system_id,
            version=version,
        )
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        results = query.all()
        return [GbfsFeedImpl.from_orm(feed) for feed in results]
