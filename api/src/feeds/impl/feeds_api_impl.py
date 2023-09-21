from typing import List, Type, Set, Union

from fastapi import HTTPException
from sqlalchemy.orm import Query, aliased

from database.database import Database
from database_gen.sqlacodegen_models import Externalid, Feed, Gtfsdataset, Gtfsfeed, Gtfsrealtimefeed, t_locationfeed, \
    Location, Entitytype
from database_gen.sqlacodegen_models import t_redirectingid, t_entitytypefeed, t_feedreference
from feeds.filters.feed_filter import FeedFilter
from feeds.filters.gtfs_dataset_filter import GtfsDatasetFilter
from feeds.filters.gtfs_feed_filter import GtfsFeedFilter, LocationFilter
from feeds.filters.gtfs_rt_feed_filter import GtfsRtFeedFilter, EntityTypeFilter
from feeds.impl.datasets_api_impl import DatasetsApiImpl
from feeds_gen.apis.feeds_api_base import BaseFeedsApi
from feeds_gen.models.basic_feed import BasicFeed
from feeds_gen.models.external_id import ExternalId
from feeds_gen.models.gtfs_dataset import GtfsDataset
from feeds_gen.models.gtfs_feed import GtfsFeed
from feeds_gen.models.gtfs_rt_feed import GtfsRTFeed
from feeds_gen.models.latest_dataset import LatestDataset
from feeds_gen.models.location import Location as ApiLocation
from feeds_gen.models.source_info import SourceInfo


class FeedsApiImpl(BaseFeedsApi):
    """
    This class represents the implementation of the `/feeds` endpoints.
    All methods from the parent class `feeds_gen.apis.feeds_api_base.BaseFeedsApi` should be implemented.
    If a method is left blank the associated endpoint will return a 500 HTTP response.
    """
    APIFeedType = Union[BasicFeed, GtfsFeed, GtfsRTFeed]

    @staticmethod
    def _create_common_feed(database_feed: Feed,
                            clazz: Type[APIFeedType],
                            redirects: Set[str],
                            external_ids: Set[Externalid]) -> Union[APIFeedType]:
        """ Maps the ORM object Feed to API data model specified by clazz"""

        params = {"id": database_feed.stable_id,
                  "data_type": database_feed.data_type,
                  "status": database_feed.status,
                  "feed_name": database_feed.feed_name,
                  "note": database_feed.note,
                  "provider": database_feed.provider,
                  "source_info": SourceInfo(producer_url=database_feed.producer_url,
                                            authentication_type=database_feed.authentication_type,
                                            authentication_info_url=database_feed.authentication_info_url,
                                            api_key_parameter_name=database_feed.api_key_parameter_name,
                                            license_url=database_feed.license_url),
                  "redirects": [redirect for redirect in redirects if redirect is not None],
                  "external_ids": [ExternalId(external_id=external_id.associated_id, source=external_id.source) for
                                   external_id in external_ids if external_id is not None]}
        obj = clazz(**params)
        return obj

    @staticmethod
    def _create_feeds_query(feed_type: Type[Feed]) -> Query:
        target_feed = aliased(Feed)
        return (Query([feed_type, target_feed.stable_id, Externalid])
                .join(t_redirectingid, feed_type.id == t_redirectingid.c['source_id'], isouter=True)
                .join(target_feed, t_redirectingid.c.target_id == target_feed.id, isouter=True)
                .join(Externalid, feed_type.id == Externalid.feed_id, isouter=True))

    @staticmethod
    def _get_basic_feeds(feed_filter: FeedFilter,
                         limit: int = None,
                         offset: int = None,
                         ) -> List[BasicFeed]:
        """
        Maps sqlalchemy data model Feed to API data model BasicFeed
        """
        # Results are sorted by stable_id because Database.select(group_by=) requires it so
        feed_query = feed_filter.filter(FeedsApiImpl._create_feeds_query(Feed)).order_by(Feed.stable_id)
        feed_groups = Database().select(query=feed_query,
                                        limit=limit, offset=offset,
                                        group_by=lambda x: x[0].stable_id)
        basic_feeds = []
        for feed_group in feed_groups:
            feed_objects, redirects, external_ids = zip(*feed_group)
            basic_feeds.append(
                FeedsApiImpl._create_common_feed(feed_objects[0], BasicFeed, set(redirects), set(external_ids)))
        return basic_feeds

    @staticmethod
    def _get_gtfs_feeds(feed_filter: GtfsFeedFilter,
                        limit: int = None,
                        offset: int = None,
                        conditions: List[Query] = None,
                        bounding_latitudes: str = None,
                        bounding_longitudes: str = None,
                        bounding_filter_method: str = None) -> List[GtfsFeed]:
        query = feed_filter.filter(FeedsApiImpl._create_feeds_query(Gtfsfeed)
                                   .join(Gtfsdataset, Gtfsfeed.id == Gtfsdataset.feed_id, isouter=True)
                                   .add_entity(Gtfsdataset)
                                   .join(t_locationfeed, t_locationfeed.c.feed_id == Gtfsfeed.id, isouter=True)
                                   .join(Location, t_locationfeed.c.location_id == Location.id, isouter=True)
                                   .add_entity(Location)
                                   .order_by(Gtfsfeed.stable_id))
        query = DatasetsApiImpl.apply_bounding_filtering(query, bounding_latitudes, bounding_longitudes,
                                                         bounding_filter_method)
        db = Database()
        feed_groups = db.select(query=query, limit=limit, offset=offset,
                                conditions=conditions, group_by=lambda x: x[0].stable_id)
        gtfs_feeds = []
        for feed_group in feed_groups:
            feed_objects, redirects, external_ids, latest_datasets, locations = zip(*feed_group)

            gtfs_feed = FeedsApiImpl._create_common_feed(feed_objects[0], GtfsFeed, set(redirects), set(external_ids))
            gtfs_feed.locations = [ApiLocation(country_code=location.country_code,
                                               subdivision_name=location.subdivision_name,
                                               municipality=location.municipality)
                                   for location in locations if location is not None]
            if latest_dataset := next(filter(lambda x: x is not None and x.latest, latest_datasets), None):
                # better check if there are more than one latest dataset
                gtfs_feed.latest_dataset = LatestDataset(id=latest_dataset.stable_id,
                                                         hosted_url=latest_dataset.hosted_url)

            gtfs_feeds.append(gtfs_feed)

        return gtfs_feeds

    @staticmethod
    def _get_gtfs_rt_feeds(feed_filter: GtfsRtFeedFilter,
                           limit: int = None, offset: int = None, conditions: List[Query] = None) -> List[GtfsRTFeed]:
        referenced_feed = aliased(Feed)
        query = feed_filter.filter(FeedsApiImpl._create_feeds_query(Gtfsrealtimefeed)
                                   .join(t_entitytypefeed, isouter=True)
                                   .join(Entitytype, isouter=True)
                                   .join(t_feedreference, isouter=True)
                                   .join(referenced_feed, referenced_feed.id == t_feedreference.c.gtfs_feed_id,
                                         isouter=True)
                                   .add_columns(Entitytype.name, referenced_feed.stable_id)
                                   .order_by(Feed.stable_id))
        # Results are sorted by stable_id because Database.select(group_by=) requires it so
        feed_groups = Database().select(query=query, limit=limit, offset=offset,
                                        conditions=conditions, group_by=lambda x: x[0].stable_id)
        gtfs_rt_feeds = []
        for feed_group in feed_groups:
            feed_objects, redirects, external_ids, entity_types, feed_references = zip(*feed_group)

            gtfs_rt_feed = FeedsApiImpl._create_common_feed(feed_objects[0], GtfsRTFeed, set(redirects),
                                                            set(external_ids))
            gtfs_rt_feed.entity_types = {entity_type for entity_type in entity_types if entity_type is not None}
            gtfs_rt_feed.feed_references = {reference for reference in feed_references if reference is not None}
            gtfs_rt_feeds.append(gtfs_rt_feed)

        return gtfs_rt_feeds

    def get_feed(
            self,
            id: str,
    ) -> BasicFeed:
        """Get the specified feed from the Mobility Database."""
        if (ret := self._get_basic_feeds(FeedFilter(stable_id=id))) and len(ret) == 1:
            return ret[0]
        else:
            raise HTTPException(status_code=404, detail=f"Feed {id} not found")

    def get_feeds(
            self,
            limit: int,
            offset: int,
            status: str,
            provider: str,
            producer_url: str,
            sort: str,
    ) -> List[BasicFeed]:
        """Get some (or all) feeds from the Mobility Database."""
        feed_filter = FeedFilter(status=status, provider__ilike=provider, producer_url__ilike=producer_url)
        return self._get_basic_feeds(feed_filter, limit, offset)

    def get_gtfs_feed(
            self,
            id: str,
    ) -> GtfsFeed:
        """Get the specified feed from the Mobility Database."""
        if (ret := self._get_gtfs_feeds(GtfsFeedFilter(stable_id=id))) and len(ret) == 1:
            return ret[0]
        else:
            raise HTTPException(status_code=404, detail=f"GTFS feed {id} not found")

    def get_gtfs_feed_datasets(
            self,
            id: str,
            latest: bool,
            limit: int,
            offset: int,
            downloaded_date_gte: str,
            downloaded_date_lte: str,
            sort: str,
            bounding_latitudes: str,
            bounding_longitudes: str,
            bounding_filter_method: str,
    ) -> List[GtfsDataset]:
        """Get a list of datasets related to a feed."""
        # getting the bounding box as JSON to make it easier to process
        query = (GtfsDatasetFilter(download_date__lte=downloaded_date_lte, download_date__gte=downloaded_date_gte)
                 .filter(DatasetsApiImpl.create_dataset_query().filter(Feed.stable_id == id)))
        query = DatasetsApiImpl.apply_bounding_filtering(query, bounding_latitudes, bounding_longitudes,
                                                         bounding_filter_method)

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
            sort: str,
            bounding_latitudes: str,
            bounding_longitudes: str,
            bounding_filter_method: str,
    ) -> List[GtfsFeed]:
        """Get some (or all) GTFS feeds from the Mobility Database."""
        location_filter = LocationFilter(country_code=country_code,
                                         subdivision_name__ilike=subdivision_name,
                                         municipality__ilike=municipality)
        feed_filter = GtfsFeedFilter(provider__ilike=provider, producer_url__ilike=producer_url,
                                     location=location_filter)
        return self._get_gtfs_feeds(feed_filter, limit=limit, offset=offset,
                                    bounding_latitudes=bounding_latitudes,
                                    bounding_longitudes=bounding_longitudes,
                                    bounding_filter_method=bounding_filter_method)

    def get_gtfs_rt_feed(
            self,
            id: str,
    ) -> GtfsRTFeed:
        """Get the specified GTFS Realtime feed from the Mobility Database."""
        if (ret := self._get_gtfs_rt_feeds(GtfsRtFeedFilter(stable_id=id))) and len(ret) == 1:
            return ret[0]
        else:
            raise HTTPException(status_code=404, detail=f"GTFS realtime feed {id} not found")

    def get_gtfs_rt_feeds(
            self,
            limit: int,
            offset: int,
            provider: str,
            producer_url: str,
            entity_types: str,
            sort: str,
    ) -> List[GtfsRTFeed]:
        """Get some (or all) GTFS feeds from the Mobility Database."""
        return self._get_gtfs_rt_feeds(GtfsRtFeedFilter(provider__ilike=provider, producer_url__ilike=producer_url,
                                                        entity_types=EntityTypeFilter(name__in=entity_types)),
                                       limit, offset)
