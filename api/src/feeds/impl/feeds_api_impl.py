from datetime import date
from typing import List

from fastapi import HTTPException
from sqlalchemy import select, func, literal_column
from sqlalchemy.sql import Select

from database_gen.sqlacodegen_models import Feed, Externalid, t_redirectingid
from feeds_gen.apis.feeds_api_base import BaseFeedsApi
from feeds_gen.models.basic_feed import BasicFeed
from feeds_gen.models.bounding_box import BoundingBox
from feeds_gen.models.external_id import ExternalId
from feeds_gen.models.extra_models import TokenModel
from feeds_gen.models.feed_log import FeedLog
from feeds_gen.models.gtfs_dataset import GtfsDataset
from feeds_gen.models.gtfs_feed import GtfsFeed
from feeds_gen.models.gtfs_rt_feed import GtfsRTFeed
from feeds_gen.models.latest_dataset import LatestDataset
from feeds_gen.models.source_info import SourceInfo

from database.database import DB_ENGINE


class FeedsApiImpl(BaseFeedsApi):
    """
    This class represents the implementation of the `/feeds` endpoints.
    All methods from the parent class `feeds_gen.apis.feeds_api_base.BaseFeedsApi` should be implemented.
    If a method is left blank the associated endpoint will return a 500 HTTP response.
    """

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

    def get_feed(
            self,
            id: str,
    ) -> BasicFeed:
        """Get the specified feed from the Mobility Database."""
        feeds = DB_ENGINE.select(query=self.get_feeds_query(), conditions=[Feed.stable_id == id])
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
                DB_ENGINE.select(query=self.get_feeds_query(), limit=limit, offset=offset)]

    def get_gtfs_feed(
            self,
            id: str,
    ) -> GtfsFeed:
        """Get the specified feed from the Mobility Database."""
        return GtfsFeed(id="gtfsFeedFoo", data_type=None, status=None, external_ids=[], provider="providerFoo",
                        feed_name="feedFoo", note="note", source_info=SourceInfo(), latest_dataset=LatestDataset())

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
        return [GtfsDataset(id="datasetFoo", feed_id="feedFoo", hosted_url="http://www.abc.com", note="note",
                            download_date=date.today(), creation_date=date.today(), last_update_date=date.today(),
                            hash="123", locations=[], bounding_box=BoundingBox(), features=[])]

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
        print("In get_gtfs_feeds endpoint")
        return [self.get_gtfs_feed("foo")]

    def get_gtfs_rt_feed(
            self,
            id: str,
    ) -> GtfsRTFeed:
        """Get the specified GTFS Realtime feed from the Mobility Database."""
        return GtfsRTFeed(id="gtfsrtFoo", data_type=None, status=None, externals_ids=[], provider="providerFoo",
                          feed_name="feedFoo", note="Note", source_info=SourceInfo(), entity_types=[],
                          feed_references=[])

    def get_gtfs_rt_feeds(
            self,
            limit: int,
            offset: int,
            filter: str,
            sort: str,
    ) -> List[GtfsRTFeed]:
        """Get some (or all) GTFS feeds from the Mobility Database."""
        return [self.get_gtfs_rt_feed("foo")]
