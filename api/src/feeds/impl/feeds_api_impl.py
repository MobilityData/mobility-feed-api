import itertools
from typing import List, Type, Set, Union

from fastapi import HTTPException
from sqlalchemy import select, func, literal_column
from sqlalchemy.orm import joinedload, Query
from sqlalchemy.sql import Select

from database.database import Database
from database_gen.sqlacodegen_models import Externalid, Feed, Gtfsdataset, Gtfsfeed, Gtfsrealtimefeed
from database_gen.sqlacodegen_models import t_redirectingid, t_entitytypefeed, t_feedreference
from feeds.impl.datasets_api_impl import DatasetsApiImpl
from feeds_gen.apis.feeds_api_base import BaseFeedsApi
from feeds_gen.models.basic_feed import BasicFeed
from feeds_gen.models.external_id import ExternalId
from feeds_gen.models.extra_models import TokenModel
from feeds_gen.models.feed_log import FeedLog
from feeds_gen.models.gtfs_dataset import GtfsDataset
from feeds_gen.models.gtfs_feed import GtfsFeed
from feeds_gen.models.gtfs_rt_feed import GtfsRTFeed
from feeds_gen.models.latest_dataset import LatestDataset
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

        params = {"id": database_feed.id,
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
                  "redirects": list(redirects),
                  "external_ids": [ExternalId(external_id=external_id.associated_id, source=external_id.source) for
                                   external_id in external_ids]}
        obj = clazz(**params)
        return obj

    @staticmethod
    def get_feeds_query() -> Select:
        return (((select(*Feed.__table__.columns,
                         func.string_agg(Externalid.associated_id, literal_column("','")).label("associated_ids"),
                         func.string_agg(Externalid.source, literal_column("','")).label("sources"),
                         func.string_agg(t_redirectingid.c.target_id, literal_column("','")).label("target_ids"))
                  .outerjoin(Externalid, Feed.id == Externalid.feed_id))
                 .outerjoin(t_redirectingid, Feed.id == t_redirectingid.c.source_id))
                .group_by(*Feed.__table__.columns))

    @staticmethod
    def map_feed(feed: Feed) -> BasicFeed:
        """
        Maps sqlalchemy data model Feed to API data model BasicFeed
        """
        redirects = [target for target in feed.target_ids.split(",")] if feed.target_ids else []
        external_ids = [ExternalId(external_id=associated_id, source=source)
                        for associated_id, source
                        in zip(feed.associated_ids.split(","), feed.sources.split(","))] \
            if feed.associated_ids and feed.sources else []
        return BasicFeed(id=feed.stable_id, data_type=feed.data_type, status=feed.status,
                         feed_name=feed.feed_name, note=feed.note, provider=feed.provider,
                         redirects=redirects, external_ids=external_ids,
                         source_info=SourceInfo(producer_url=feed.producer_url,
                                                authentication_type=feed.authentication_type,
                                                authentication_info_url=feed.authentication_info_url,
                                                api_key_parameter_name=feed.api_key_parameter_name,
                                                license_url=feed.license_url))

    @staticmethod
    def _create_feeds_query(feed_type: Type[Feed]) -> Query:
        return (Query([feed_type, t_redirectingid.c['target_id'], Externalid])
                .options(joinedload(feed_type.locations))
                .join(t_redirectingid, feed_type.id == t_redirectingid.c['source_id'], isouter=True)
                .join(Externalid, feed_type.id == Externalid.feed_id, isouter=True))

    @staticmethod
    def _get_gtfs_feeds(limit: int = None,
                        offset: int = None,
                        conditions: List[Query] = None,
                        bounding_latitudes: str = None,
                        bounding_longitudes: str = None,
                        bounding_filter_method: str = None) -> List[GtfsFeed]:
        query = (FeedsApiImpl._create_feeds_query(Gtfsfeed)
                 .join(Gtfsdataset, Gtfsfeed.id == Gtfsdataset.feed_id, isouter=True)
                 .add_entity(Gtfsdataset))
        query = DatasetsApiImpl.apply_bounding_filtering(query, bounding_latitudes, bounding_longitudes,
                                                         bounding_filter_method)
        db = Database()
        all_rows = [[x for x in y] for _, y in
                    itertools.groupby(db.select(query=query, limit=limit, offset=offset, conditions=conditions),
                                      lambda x: x[0].id)]
        gtfs_feeds = []
        for row in all_rows:
            redirects = {x[1] for x in row if x[1]}
            external_ids = {x[2] for x in row if x[2]}

            gtfs_feed = FeedsApiImpl._create_common_feed(row[0][0], GtfsFeed, redirects, external_ids)
            latest_datasets = {x[3] for x in row if x[3]}

            if latest_dataset := next(filter(lambda x: x.latest, latest_datasets), None):
                # better check if there are more than one latest dataset
                gtfs_feed.latest_dataset = LatestDataset(id=latest_dataset.id, hosted_url=latest_dataset.hosted_url)

            gtfs_feeds.append(gtfs_feed)

        return gtfs_feeds

    @staticmethod
    def _get_gtfs_rt_feeds(limit: int = None, offset: int = None, conditions: List[Query] = None) -> List[GtfsRTFeed]:
        query = (FeedsApiImpl._create_feeds_query(Gtfsrealtimefeed)
                 .join(t_entitytypefeed, isouter=True)
                 .join(t_feedreference, isouter=True)
                 .add_columns(t_entitytypefeed.c['entity_name'], t_feedreference.c['gtfs_feed_id']))
        db = Database()
        all_rows = [[x for x in y] for _, y in
                    itertools.groupby(db.select(query=query, limit=limit, offset=offset, conditions=conditions),
                                      lambda x: x[0].id)]
        gtfs_rt_feeds = []
        for row in all_rows:
            redirects = {x[1] for x in row if x[1]}
            external_ids = {x[2] for x in row if x[2]}

            gtfs_rt_feed = FeedsApiImpl._create_common_feed(row[0][0], GtfsRTFeed, redirects, external_ids)
            gtfs_rt_feed.entity_types = {x[3] for x in row if x[3]}
            gtfs_rt_feed.feed_references = {x[4] for x in row if x[4]}
            gtfs_rt_feeds.append(gtfs_rt_feed)

        return gtfs_rt_feeds

    def get_feed(
            self,
            id: str,
    ) -> BasicFeed:
        """Get the specified feed from the Mobility Database."""
        feeds = Database().select(query=self.get_feeds_query(), conditions=[Feed.stable_id == id])
        if len(feeds) == 1:
            return self.map_feed(feeds[0])
        raise HTTPException(status_code=404, detail=f"Feed {id} not found")

    def get_feed_logs(
            id: str,
            limit: int,
            offset: int,
            filter: str,
            sort: str,
            token_ApiKeyAuth: TokenModel,
    ) -> List[FeedLog]:
        """Get a list of logs related to a feed."""
        return []

    def get_feeds(
            self,
            limit: int,
            offset: int,
            filter: str,
            sort: str,
    ) -> List[BasicFeed]:
        """Get some (or all) feeds from the Mobility Database."""
        return [self.map_feed(feed) for feed in
                Database().select(query=self.get_feeds_query(), limit=limit, offset=offset)]

    def get_gtfs_feed(
            self,
            id: str,
    ) -> GtfsFeed:
        """Get the specified feed from the Mobility Database."""
        if (ret := self._get_gtfs_feeds(conditions=[Gtfsfeed.id == id])) and len(ret) == 1:
            return ret[0]
        else:
            raise HTTPException(status_code=404, detail=f"GTFS feed {id} not found")

    def get_gtfs_feed_datasets(
            self,
            id: str,
            latest: bool,
            limit: int,
            offset: int,
            filter: str,
            sort: str,
            bounding_latitudes: str,
            bounding_longitudes: str,
            bounding_filter_method: str,
    ) -> List[GtfsDataset]:
        """Get a list of datasets related to a feed."""
        # getting the bounding box as JSON to make it easier to process
        query = DatasetsApiImpl.create_dataset_query().filter(Gtfsdataset.feed_id == id)
        query = DatasetsApiImpl.apply_bounding_filtering(query, bounding_latitudes, bounding_longitudes,
                                                         bounding_filter_method)

        if latest:
            query = query.filter(Gtfsdataset.latest)

        return DatasetsApiImpl.get_datasets_gtfs(query, limit=limit, offset=offset)

    def get_gtfs_feeds(
            self,
            limit: int,
            offset: int,
            filter: str,
            sort: str,
            bounding_latitudes: str,
            bounding_longitudes: str,
            bounding_filter_method: str,
    ) -> List[GtfsFeed]:
        """Get some (or all) GTFS feeds from the Mobility Database."""
        return self._get_gtfs_feeds(limit=limit, offset=offset, bounding_latitudes=bounding_latitudes,
                                    bounding_longitudes=bounding_longitudes,
                                    bounding_filter_method=bounding_filter_method)

    def get_gtfs_rt_feed(
            self,
            id: str,
    ) -> GtfsRTFeed:
        """Get the specified GTFS Realtime feed from the Mobility Database."""
        if (ret := self._get_gtfs_rt_feeds(conditions=[Gtfsrealtimefeed.id == id])) and len(ret) == 1:
            return ret[0]
        else:
            raise HTTPException(status_code=404, detail=f"GTFS realtime feed {id} not found")

    def get_gtfs_rt_feeds(
            self,
            limit: int,
            offset: int,
            filter: str,
            sort: str,
    ) -> List[GtfsRTFeed]:
        """Get some (or all) GTFS feeds from the Mobility Database."""
        return self._get_gtfs_rt_feeds(limit, offset)
