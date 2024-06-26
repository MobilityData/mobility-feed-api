from typing import List, Type, Set, Union
from datetime import datetime
from sqlalchemy.orm import Query, aliased

from database.database import Database
from database_gen.sqlacodegen_models import (
    Externalid,
    Feed,
    Gtfsdataset,
    Gtfsfeed,
    Gtfsrealtimefeed,
    t_locationfeed,
    Location,
    Entitytype,
    Redirectingid,
)
from database_gen.sqlacodegen_models import (
    t_entitytypefeed,
    t_feedreference,
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
from feeds.impl.models.location_impl import LocationImpl
from feeds.impl.models.latest_dataset_impl import LatestDatasetImpl
from feeds_gen.apis.feeds_api_base import BaseFeedsApi
from feeds_gen.models.basic_feed import BasicFeed
from feeds_gen.models.external_id import ExternalId
from feeds_gen.models.gtfs_dataset import GtfsDataset
from feeds_gen.models.gtfs_feed import GtfsFeed
from feeds_gen.models.gtfs_rt_feed import GtfsRTFeed
from feeds_gen.models.location import Location as ApiLocation
from feeds_gen.models.source_info import SourceInfo
from feeds_gen.models.redirect import Redirect
from utils.date_utils import valid_iso_date


class FeedsApiImpl(BaseFeedsApi):
    """
    This class represents the implementation of the `/feeds` endpoints.
    All methods from the parent class `feeds_gen.apis.feeds_api_base.BaseFeedsApi` should be implemented.
    If a method is left blank the associated endpoint will return a 500 HTTP response.
    """

    APIFeedType = Union[BasicFeed, GtfsFeed, GtfsRTFeed]

    @staticmethod
    def _create_common_feed(
        database_feed: Feed,
        clazz: Type[APIFeedType],
        redirects: [Redirect],
        external_ids: Set[Externalid],
    ) -> Union[APIFeedType]:
        """Maps the ORM object Feed to API data model specified by clazz"""

        params = {
            "id": database_feed.stable_id,
            "data_type": database_feed.data_type,
            "status": database_feed.status,
            "feed_name": database_feed.feed_name,
            "note": database_feed.note,
            "provider": database_feed.provider,
            "feed_contact_email": database_feed.feed_contact_email,
            "source_info": SourceInfo(
                producer_url=database_feed.producer_url,
                authentication_type=database_feed.authentication_type,
                authentication_info_url=database_feed.authentication_info_url,
                api_key_parameter_name=database_feed.api_key_parameter_name,
                license_url=database_feed.license_url,
            ),
            "redirects": [redirect for redirect in redirects if redirect is not None],
            "external_ids": [
                ExternalId(external_id=external_id.associated_id, source=external_id.source)
                for external_id in external_ids
                if external_id is not None
            ],
        }
        obj = clazz(**params)
        return obj

    @staticmethod
    def _create_feeds_query(feed_type: Type[Feed]) -> Query:
        target_feed = aliased(Feed)
        return (
            Query([feed_type, target_feed.stable_id, Externalid, Redirectingid.redirect_comment])
            .join(
                Redirectingid,
                feed_type.id == Redirectingid.source_id,
                isouter=True,
            )
            .join(target_feed, Redirectingid.target_id == target_feed.id, isouter=True)
            .join(Externalid, feed_type.id == Externalid.feed_id, isouter=True)
        )

    @staticmethod
    def _get_basic_feeds(
        feed_filter: FeedFilter,
        limit: int = None,
        offset: int = None,
    ) -> List[BasicFeed]:
        """
        Maps sqlalchemy data model Feed to API data model BasicFeed
        """
        # Results are sorted by stable_id because Database.select(group_by=) requires it so
        feed_query = feed_filter.filter(FeedsApiImpl._create_feeds_query(Feed)).order_by(Feed.stable_id)
        feed_groups = Database().select(
            query=feed_query,
            limit=limit,
            offset=offset,
            group_by=lambda x: x[0].stable_id,
        )
        basic_feeds = []
        for feed_group in feed_groups:
            feed_objects, redirect_ids, external_ids, redirect_comments = zip(*feed_group)
            # Put together the redirect ids and the corresponding comments. Eliminate Nones.
            redirects_list = [
                Redirect(target_id=redirect, comment=comment)
                for redirect, comment in zip(redirect_ids, redirect_comments)
                if redirect is not None
            ]

            basic_feeds.append(
                FeedsApiImpl._create_common_feed(feed_objects[0], BasicFeed, redirects_list, set(external_ids))
            )
        return basic_feeds

    @staticmethod
    def _get_gtfs_feeds(
        feed_filter: GtfsFeedFilter,
        limit: int = None,
        offset: int = None,
        conditions: List[Query] = None,
        bounding_latitudes: str = None,
        bounding_longitudes: str = None,
        bounding_filter_method: str = None,
    ) -> List[GtfsFeed]:
        order_by_columns = [Gtfsfeed.stable_id]
        query = feed_filter.filter(
            FeedsApiImpl._create_feeds_query(Gtfsfeed)
            .join(Gtfsdataset, Gtfsfeed.id == Gtfsdataset.feed_id, isouter=True)
            .add_entity(Gtfsdataset)
            .add_column(Gtfsdataset.bounding_box.ST_AsGeoJSON())
            .join(t_locationfeed, t_locationfeed.c.feed_id == Gtfsfeed.id, isouter=True)
            .join(Location, t_locationfeed.c.location_id == Location.id, isouter=True)
            .add_entity(Location)
            .order_by(*order_by_columns)
        )
        query = DatasetsApiImpl.apply_bounding_filtering(
            query, bounding_latitudes, bounding_longitudes, bounding_filter_method
        )
        db = Database()
        feed_groups = db.select(
            query=query,
            limit=limit,
            offset=offset,
            conditions=conditions,
            group_by=lambda x: x[0].stable_id,
        )
        gtfs_feeds = []
        for feed_group in feed_groups:
            feed_objects, redirect_ids, external_ids, redirect_comments, datasets, bounding_boxes, locations = zip(
                *feed_group
            )

            # We use a set to eliminate duplicate in the Redirects.
            # But we can't use the Redirect object directly since they are not hashable and making them
            # hashable is more tricky since the class is generated by the openapi generator.
            # So instead transfer the Redirect data to a simple dict to temporarily use in the set.
            redirects_set = set()
            for redirect, comment in zip(redirect_ids, redirect_comments):
                if redirect is not None:
                    redirect_tuple = (redirect, comment)
                    redirects_set.add(redirect_tuple)

            # Convert the set of unique tuples back to a list of Redirect objects
            redirects_list = [Redirect(target_id=redirect, comment=comment) for redirect, comment in redirects_set]

            gtfs_feed = FeedsApiImpl._create_common_feed(feed_objects[0], GtfsFeed, redirects_list, set(external_ids))

            # Iterate over locations and put in a set to eliminate duplicates
            unique_locations = set()
            for location in locations:
                if location is not None:
                    location_tuple = (location.country_code, location.subdivision_name, location.municipality)
                    unique_locations.add(location_tuple)

            gtfs_feed.locations = [
                ApiLocation(
                    country_code=country_code,
                    subdivision_name=subdivision_name,
                    municipality=municipality,
                )
                for country_code, subdivision_name, municipality in unique_locations
            ]

            latest_dataset = next((dataset for dataset in datasets if dataset is not None and dataset.latest), None)
            gtfs_feed.latest_dataset = LatestDatasetImpl.from_orm(latest_dataset)

            gtfs_feeds.append(gtfs_feed)

        return gtfs_feeds

    @staticmethod
    def _get_gtfs_rt_feeds(
        feed_filter: GtfsRtFeedFilter,
        limit: int = None,
        offset: int = None,
        conditions: List[Query] = None,
    ) -> List[GtfsRTFeed]:
        referenced_feed = aliased(Feed)
        query = feed_filter.filter(
            FeedsApiImpl._create_feeds_query(Gtfsrealtimefeed)
            .join(t_entitytypefeed, isouter=True)
            .join(Entitytype, isouter=True)
            .join(t_feedreference, isouter=True)
            .join(
                referenced_feed,
                referenced_feed.id == t_feedreference.c.gtfs_feed_id,
                isouter=True,
            )
            .join(t_locationfeed, t_locationfeed.c.feed_id == Gtfsrealtimefeed.id, isouter=True)
            .join(Location, t_locationfeed.c.location_id == Location.id, isouter=True)
            .add_columns(Entitytype.name, referenced_feed.stable_id)
            .order_by(Feed.stable_id)
        )
        # Results are sorted by stable_id because Database.select(group_by=) requires it so
        feed_groups = Database().select(
            query=query,
            limit=limit,
            offset=offset,
            conditions=conditions,
            group_by=lambda x: x[0].stable_id,
        )
        gtfs_rt_feeds = []
        for feed_group in feed_groups:
            feed_objects, redirect_ids, external_ids, redirect_comments, entity_types, feed_references = zip(
                *feed_group
            )

            # Put together the redirect ids and the corresponding comments. Eliminate Nones.
            redirects_list = [
                Redirect(target_id=redirect, comment=comment)
                for redirect, comment in zip(redirect_ids, redirect_comments)
                if redirect is not None
            ]

            gtfs_rt_feed = FeedsApiImpl._create_common_feed(
                feed_objects[0], GtfsRTFeed, redirects_list, set(external_ids)
            )
            gtfs_rt_feed.entity_types = {entity_type for entity_type in entity_types if entity_type is not None}
            gtfs_rt_feed.feed_references = {reference for reference in feed_references if reference is not None}
            gtfs_rt_feed.locations = [
                LocationImpl.from_orm(location)
                for location in feed_objects[0].locations
                if feed_objects[0].locations is not None
            ]
            gtfs_rt_feeds.append(gtfs_rt_feed)

        return gtfs_rt_feeds

    def get_feed(
        self,
        id: str,
    ) -> BasicFeed:
        """Get the specified feed from the Mobility Database."""
        feed = FeedFilter(stable_id=id).filter(Database().get_query_model(Feed)).first()
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
        feed_filter = FeedFilter(status=status, provider__ilike=provider, producer_url__ilike=producer_url)
        feed_query = feed_filter.filter(Database().get_query_model(Feed))
        # Results are sorted by provider
        feed_query = feed_query.order_by(Feed.provider, Feed.stable_id)
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
        """Get the specified feed from the Mobility Database."""
        if (ret := self._get_gtfs_feeds(GtfsFeedFilter(stable_id=id))) and len(ret) == 1:
            return ret[0]
        else:
            raise_http_error(404, gtfs_feed_not_found.format(id))

    def get_gtfs_feed_datasets(
        self,
        id: str,
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

        # Replace Z with +00:00 to make the datetime object timezone aware
        # Due to https://github.com/python/cpython/issues/80010, once migrate to Python 3.11, we can use fromisoformat
        query = GtfsDatasetFilter(
            downloaded_at__lte=datetime.fromisoformat(downloaded_before.replace("Z", "+00:00"))
            if downloaded_before
            else None,
            downloaded_at__gte=datetime.fromisoformat(downloaded_after.replace("Z", "+00:00"))
            if downloaded_after
            else None,
        ).filter(DatasetsApiImpl.create_dataset_query().filter(Feed.stable_id == id))

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
        location_filter = LocationFilter(
            country_code=country_code,
            subdivision_name__ilike=subdivision_name,
            municipality__ilike=municipality,
        )
        feed_filter = GtfsFeedFilter(
            provider__ilike=provider,
            producer_url__ilike=producer_url,
            location=location_filter,
        )
        return self._get_gtfs_feeds(
            feed_filter,
            limit=limit,
            offset=offset,
            bounding_latitudes=dataset_latitudes,
            bounding_longitudes=dataset_longitudes,
            bounding_filter_method=bounding_filter_method,
        )

    def get_gtfs_rt_feed(
        self,
        id: str,
    ) -> GtfsRTFeed:
        """Get the specified GTFS Realtime feed from the Mobility Database."""
        if (ret := self._get_gtfs_rt_feeds(GtfsRtFeedFilter(stable_id=id))) and len(ret) == 1:
            return ret[0]
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
        """Get some (or all) GTFS feeds from the Mobility Database."""
        return self._get_gtfs_rt_feeds(
            GtfsRtFeedFilter(
                provider__ilike=provider,
                producer_url__ilike=producer_url,
                entity_types=EntityTypeFilter(name__in=entity_types),
                location=LocationFilter(
                    country_code=country_code,
                    subdivision_name__ilike=subdivision_name,
                    municipality__ilike=municipality,
                ),
            ),
            limit,
            offset,
        )
