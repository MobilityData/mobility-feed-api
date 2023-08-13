from datetime import date
from typing import List

from fastapi import HTTPException

from database_gen.sqlacodegen_models import Feed
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

from database.database import Database
from utils.logger import Logger


def map_feed(feed: Feed):
    return BasicFeed(id=feed.id, data_type=feed.data_type, status=feed.status,
                     feed_name=feed.feed_name, note=feed.note,
                     providers=[provider.long_name for provider in feed.provider],
                     redirects=[target.id for target in feed.target],
                     external_ids=[ExternalId(external_id=ext_id.associated_id, source=ext_id.source)
                                   for ext_id in feed.externalid],
                     source_info=SourceInfo(producer_url=feed.producer_url,
                                            authentication_type=feed.authentication_type,
                                            authentication_info_url=feed.authentication_info_url,
                                            api_key_parameter_name=feed.api_key_parameter_name,
                                            license_url=feed.license_url))


class FeedsApiImpl(BaseFeedsApi):
    """
    This class represents the implementation of the `/feeds` endpoints.
    All methods from the parent class `feeds_gen.apis.feeds_api_base.BaseFeedsApi` should be implemented.
    If a method is left blank the associated endpoint will return a 500 HTTP response.
    """

    def __init__(self):
        self.database = Database()
        self.logger = Logger("FeedsApiImpl").get_logger()

    def get_feed(
            self,
            id: str,
    ) -> BasicFeed:
        """Get the specified feed from the Mobility Database."""
        feeds = self.database.select(Feed, conditions=[Feed.id == id])
        if len(feeds) == 1:
            return map_feed(feeds[0])
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
        return [map_feed(feed) for feed in self.database.select(Feed)]

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
