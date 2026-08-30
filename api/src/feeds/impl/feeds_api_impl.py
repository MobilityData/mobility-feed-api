from typing import List, Union, TypeVar, Optional

from sqlalchemy import or_, desc, nullslast
from sqlalchemy.orm import contains_eager, selectinload, Session
from sqlalchemy.orm.query import Query

from feeds.impl.datasets_api_impl import DatasetsApiImpl
from feeds.impl.error_handling import raise_http_error, raise_http_validation_error, convert_exception
from shared.db_models.feed_impl import FeedImpl
from shared.db_models.feed_reliability_report_impl import FeedReliabilityReportImpl
from shared.db_models.gbfs_feed_impl import GbfsFeedImpl
from shared.db_models.gtfs_feed_availability_check_impl import GtfsFeedAvailabilityCheckImpl
from shared.db_models.gtfs_feed_continuous_coverage_impl import GtfsFeedContinuousCoverageImpl
from shared.db_models.gtfs_feed_impl import GtfsFeedImpl
from shared.db_models.gtfs_rt_feed_impl import GtfsRTFeedImpl
from feeds_gen.apis.feeds_api_base import BaseFeedsApi
from feeds_gen.models.feed import Feed
from feeds_gen.models.feed_reliability_report import FeedReliabilityReport
from feeds_gen.models.gbfs_feed import GbfsFeed
from feeds_gen.models.gtfs_dataset import GtfsDataset
from feeds_gen.models.gtfs_feed import GtfsFeed
from feeds_gen.models.gtfs_feed_availability_response import GtfsFeedAvailabilityResponse
from feeds_gen.models.gtfs_feed_continuous_coverage import GtfsFeedContinuousCoverage
from feeds_gen.models.gtfs_feed_continuous_coverage_file import GtfsFeedContinuousCoverageFile
from feeds_gen.models.gtfs_feed_continuous_coverage_response import GtfsFeedContinuousCoverageResponse
from feeds_gen.models.gtfs_rt_feed import GtfsRTFeed
from middleware.request_context import is_user_email_restricted
from shared.common.continuous_coverage import COVERAGE_FILES
from shared.common.db_utils import (
    get_gtfs_feeds_query,
    get_gtfs_rt_feeds_query,
    get_selectinload_options,
    add_official_filter,
    get_gbfs_feeds_query,
)
from shared.common.error_handling import (
    availability_from_after_to,
    continuous_coverage_downloaded_after_before,
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
    GtfsFeedAvailabilityCheck,
    Gtfsrealtimefeed,
)
from shared.feed_filters.feed_filter import FeedFilter
from shared.feed_filters.gtfs_dataset_filter import GtfsDatasetFilter
from shared.feed_filters.gtfs_rt_feed_filter import GtfsRtFeedFilter
from utils.date_utils import parse_iso_datetime, valid_iso_date
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
        created_after: str,
        created_before: str,
        is_official: bool,
        db_session: Session,
    ) -> List[Feed]:
        """Get some (or all) feeds from the Mobility Database."""
        is_email_restricted = is_user_email_restricted()
        self.logger.debug(f"User email is restricted: {is_email_restricted}")
        if created_after and not valid_iso_date(created_after):
            raise_http_validation_error(invalid_date_message.format("created_after"))
        if created_before and not valid_iso_date(created_before):
            raise_http_validation_error(invalid_date_message.format("created_before"))

        feed_filter = FeedFilter(
            status=status,
            provider__ilike=provider,
            producer_url__ilike=producer_url,
            stable_id=None,
            created_at__gte=parse_iso_datetime(created_after),
            created_at__lte=parse_iso_datetime(created_before),
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
        feed_query = feed_query.options(*get_selectinload_options(), selectinload(FeedOrm.license))
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

        query = GtfsDatasetFilter(
            downloaded_at__lte=parse_iso_datetime(downloaded_before),
            downloaded_at__gte=parse_iso_datetime(downloaded_after),
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
        created_after: str,
        created_before: str,
        country_code: str,
        subdivision_name: str,
        municipality: str,
        dataset_latitudes: str,
        dataset_longitudes: str,
        bounding_filter_method: str,
        is_official: bool,
        db_session: Session,
    ) -> List[GtfsFeed]:
        if created_after and not valid_iso_date(created_after):
            raise_http_validation_error(invalid_date_message.format("created_after"))
        if created_before and not valid_iso_date(created_before):
            raise_http_validation_error(invalid_date_message.format("created_before"))

        try:
            published_only = is_user_email_restricted()
            feed_query = get_gtfs_feeds_query(
                limit=limit,
                offset=offset,
                provider=provider,
                producer_url=producer_url,
                created_after=parse_iso_datetime(created_after),
                created_before=parse_iso_datetime(created_before),
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
            .options(
                selectinload(Gtfsrealtimefeed.entitytypes),
                selectinload(Gtfsrealtimefeed.gtfs_feeds),
                *get_selectinload_options(),
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
        created_after: str,
        created_before: str,
        entity_types: str,
        country_code: str,
        subdivision_name: str,
        municipality: str,
        is_official: bool,
        db_session: Session,
    ) -> List[GtfsRTFeed]:
        """Get some (or all) GTFS Realtime feeds from the Mobility Database."""
        if created_after and not valid_iso_date(created_after):
            raise_http_validation_error(invalid_date_message.format("created_after"))
        if created_before and not valid_iso_date(created_before):
            raise_http_validation_error(invalid_date_message.format("created_before"))

        try:
            published_only = is_user_email_restricted()
            feed_query = get_gtfs_rt_feeds_query(
                limit=limit,
                offset=offset,
                provider=provider,
                producer_url=producer_url,
                created_after=parse_iso_datetime(created_after),
                created_before=parse_iso_datetime(created_before),
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

    @staticmethod
    def _get_response(feed_query: Query, impl_cls: type[T]) -> List[T]:
        """Get the response for the feed query."""
        results = feed_query.all()
        return [impl_cls.from_orm(feed) for feed in results]

    @with_db_session
    def get_gtfs_feed_gtfs_rt_feeds(self, id: str, db_session: Session) -> List[GtfsRTFeed]:
        """Get a list of GTFS Realtime related to a GTFS feed."""
        feed = self._get_gtfs_feed(id, db_session)
        if feed:
            return [GtfsRTFeedImpl.from_orm(gtfs_rt_feed) for gtfs_rt_feed in feed.gtfs_rt_feeds]
        else:
            raise_http_error(404, gtfs_feed_not_found.format(id))

    @with_db_session
    def get_gtfs_feed_reliability(self, id: str, db_session: Session) -> FeedReliabilityReport:
        """Returns the Seal of Reliability breakdown for a GTFS feed."""
        feed = self._get_gtfs_feed(id, db_session, include_options_for_joinedload=False)
        if not feed:
            raise_http_error(404, gtfs_feed_not_found.format(id))

        # No seal row means the nightly job has not reached this feed. That is reported as a feed
        # that simply does not hold the seal, with every criterion never evaluated, rather than a
        # 404: the feed exists, we just have nothing to say about it yet.
        try:
            return FeedReliabilityReportImpl.from_orm(feed)
        except InternalHTTPException as e:
            # A stored criterion this build does not know about. The impl lives under shared/ and
            # cannot depend on fastapi, so it raises InternalHTTPException for conversion here.
            raise convert_exception(e)

    @with_db_session
    def get_gtfs_feed_availability(
        self,
        id: str,
        _from: str,
        to: str,
        limit: int,
        offset: int,
        sort: str,
        db_session: Session,
    ) -> GtfsFeedAvailabilityResponse:
        """Returns historical availability checks for a GTFS feed."""
        if _from and not valid_iso_date(_from):
            raise_http_validation_error(invalid_date_message.format("from"))
        if to and not valid_iso_date(to):
            raise_http_validation_error(invalid_date_message.format("to"))

        from_dt = parse_iso_datetime(_from)
        to_dt = parse_iso_datetime(to)

        if from_dt and to_dt and from_dt > to_dt:
            raise_http_validation_error(availability_from_after_to)

        feed = self._get_gtfs_feed(id, db_session, include_options_for_joinedload=False)
        if not feed:
            raise_http_error(404, gtfs_feed_not_found.format(id))

        query = db_session.query(GtfsFeedAvailabilityCheck).filter(GtfsFeedAvailabilityCheck.feed_id == feed.id)
        if from_dt:
            query = query.filter(GtfsFeedAvailabilityCheck.checked_at >= from_dt)
        if to_dt:
            query = query.filter(GtfsFeedAvailabilityCheck.checked_at <= to_dt)

        total = query.count()
        order = (
            GtfsFeedAvailabilityCheck.checked_at.asc() if sort == "asc" else GtfsFeedAvailabilityCheck.checked_at.desc()
        )
        checks = query.order_by(order).offset(offset).limit(limit).all()

        return GtfsFeedAvailabilityResponse(
            feed_id=id,
            total=total,
            offset=offset,
            limit=limit,
            checks=[GtfsFeedAvailabilityCheckImpl.from_orm(c) for c in checks],
        )

    @with_db_session
    def get_gtfs_feed_continuous_coverage(
        self,
        id: str,
        downloaded_after: str,
        downloaded_before: str,
        limit: int,
        offset: int,
        db_session: Session,
    ) -> GtfsFeedContinuousCoverageResponse:
        """Returns the continuous coverage history for a GTFS feed."""
        if downloaded_after and not valid_iso_date(downloaded_after):
            raise_http_validation_error(invalid_date_message.format("downloaded_after"))
        if downloaded_before and not valid_iso_date(downloaded_before):
            raise_http_validation_error(invalid_date_message.format("downloaded_before"))

        after_dt = parse_iso_datetime(downloaded_after)
        before_dt = parse_iso_datetime(downloaded_before)

        if after_dt and before_dt and after_dt > before_dt:
            raise_http_validation_error(continuous_coverage_downloaded_after_before)

        feed = self._get_gtfs_feed(id, db_session, include_options_for_joinedload=False)
        if not feed:
            raise_http_error(404, gtfs_feed_not_found.format(id))

        # Kept separate from the filtered query: the dataset immediately older than the page is
        # looked up here, and it may well be one the date filters excluded.
        feed_datasets = db_session.query(Gtfsdataset).filter(Gtfsdataset.feed_id == feed.id)

        query = feed_datasets
        if after_dt:
            query = query.filter(Gtfsdataset.downloaded_at >= after_dt)
        if before_dt:
            query = query.filter(Gtfsdataset.downloaded_at <= before_dt)

        total = query.count()
        page = (
            query.order_by(*self._continuous_coverage_order())
            .offset(offset)
            .limit(limit)
            .options(selectinload(Gtfsdataset.feed_info), selectinload(Gtfsdataset.gtfsfiles))
            .all()
        )

        # Each item's overlap is measured against the dataset downloaded just before it. Within the
        # page that is usually the next item, but the oldest item's neighbour lies outside the page,
        # and any item bordering a null-`downloaded_at` run can't trust its positional neighbour
        # either - `_predecessor` falls back to a real lookup in both cases.
        predecessors = [
            self._predecessor(feed_datasets, dataset, next_dataset)
            for dataset, next_dataset in zip(page, page[1:] + [None])
        ]

        latest_coverage = self._latest_continuous_coverage(feed, feed_datasets)

        return GtfsFeedContinuousCoverageResponse(
            feed_id=id,
            total=total,
            offset=offset,
            limit=limit,
            latest_files=(
                latest_coverage.files
                if latest_coverage
                else [GtfsFeedContinuousCoverageFile(name=name, present=False) for name in COVERAGE_FILES]
            ),
            latest_coverage_window=latest_coverage.coverage_window if latest_coverage else None,
            latest_coverage_window_source=latest_coverage.coverage_window_source if latest_coverage else None,
            latest_within_max_coverage_window=(latest_coverage.within_max_coverage_window if latest_coverage else None),
            latest_service_window=latest_coverage.service_window if latest_coverage else None,
            latest_feed_info_window=latest_coverage.feed_info_window if latest_coverage else None,
            latest_feed_info_matches=latest_coverage.feed_info_matches if latest_coverage else None,
            latest_overlap_days=latest_coverage.overlap_days if latest_coverage else None,
            latest_gap_days=latest_coverage.gap_days if latest_coverage else None,
            items=[
                GtfsFeedContinuousCoverageImpl.from_orm(
                    dataset,
                    previous_dataset=previous,
                    is_latest=dataset.id == feed.latest_dataset_id,
                )
                for dataset, previous in zip(page, predecessors)
            ],
        )

    @staticmethod
    def _latest_continuous_coverage(feed: Gtfsfeed, feed_datasets: Query) -> Optional[GtfsFeedContinuousCoverage]:
        """The coverage snapshot for the feed's latest dataset, independent of the requested page or
        date filters - the root `latest_*` response fields always describe this dataset, even when it
        falls outside the current page or date range.
        """
        if feed.latest_dataset_id is None:
            return None
        latest_dataset = (
            feed_datasets.filter(Gtfsdataset.id == feed.latest_dataset_id)
            .options(selectinload(Gtfsdataset.feed_info), selectinload(Gtfsdataset.gtfsfiles))
            .first()
        )
        if latest_dataset is None:
            return None
        previous = FeedsApiImpl._previous_dataset(feed_datasets, latest_dataset)
        return GtfsFeedContinuousCoverageImpl.from_orm(latest_dataset, previous_dataset=previous, is_latest=True)

    @staticmethod
    def _continuous_coverage_order() -> tuple:
        """Newest dataset first, with a deterministic tiebreak.

        `downloaded_at` is nullable, and a dataset with no download timestamp cannot be placed in a
        chronological chain at all, so those sort last rather than ahead of everything. `stable_id`
        breaks ties so that paging over datasets sharing a timestamp cannot repeat or skip a row.
        """
        return nullslast(desc(Gtfsdataset.downloaded_at)), desc(Gtfsdataset.stable_id)

    @staticmethod
    def _previous_dataset(feed_datasets: Query, dataset: Gtfsdataset) -> Optional[Gtfsdataset]:
        """The feed's dataset downloaded immediately before `dataset`, ignoring any date filter.

        Returns None for a dataset with no download timestamp: there is no "before" to look for, and
        ordering it against timestamped datasets would invent a neighbour.
        """
        if dataset.downloaded_at is None:
            return None
        return (
            feed_datasets.filter(Gtfsdataset.downloaded_at < dataset.downloaded_at)
            .order_by(*FeedsApiImpl._continuous_coverage_order())
            .options(selectinload(Gtfsdataset.feed_info))
            .first()
        )

    @staticmethod
    def _predecessor(
        feed_datasets: Query, dataset: Gtfsdataset, positional_next: Optional[Gtfsdataset]
    ) -> Optional[Gtfsdataset]:
        """The predecessor to use for one page row.

        The next row in the page is a valid predecessor only when both it and `dataset` have a
        real `downloaded_at` - `_continuous_coverage_order`'s `nullslast` sorts undated datasets to
        the end of the page, so a positional neighbour next to one of them is not necessarily who
        was downloaded immediately before it. Falling back to `_previous_dataset` covers that case
        and the page's actual last row (`positional_next is None`) alike.
        """
        if (
            dataset.downloaded_at is not None
            and positional_next is not None
            and positional_next.downloaded_at is not None
        ):
            return positional_next
        return FeedsApiImpl._previous_dataset(feed_datasets, dataset)

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
        created_after: str,
        created_before: str,
        country_code: str,
        subdivision_name: str,
        municipality: str,
        system_id: str,
        version: str,
        db_session: Session,
    ) -> List[GbfsFeed]:
        if created_after and not valid_iso_date(created_after):
            raise_http_validation_error(invalid_date_message.format("created_after"))
        if created_before and not valid_iso_date(created_before):
            raise_http_validation_error(invalid_date_message.format("created_before"))

        query = get_gbfs_feeds_query(
            db_session=db_session,
            provider=provider,
            producer_url=producer_url,
            created_after=parse_iso_datetime(created_after),
            created_before=parse_iso_datetime(created_before),
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
