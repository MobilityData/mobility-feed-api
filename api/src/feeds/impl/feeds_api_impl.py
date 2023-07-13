from datetime import date
from typing import List

from feeds_gen.apis.feeds_api_base import BaseFeedsApi
from feeds_gen.models.basic_feed import BasicFeed
from feeds_gen.models.bounding_box import BoundingBox
from feeds_gen.models.gtfs_dataset import GtfsDataset
from feeds_gen.models.gtfs_feed import GtfsFeed
from feeds_gen.models.gtfs_rt_feed import GtfsRTFeed
from feeds_gen.models.latest_dataset import LatestDataset
from feeds_gen.models.source_info import SourceInfo


class FeedsApiImpl(BaseFeedsApi):
    """This class implements the methods from :class:`feeds_gen.apis.datasets_api_base.BaseFeedsApi`"""

    def feeds_get(
            self,
            limit: int,
            offset: int,
            filter: str,
            sort: str,
    ) -> List[BasicFeed]:
        """Get some (or all) feeds from the Mobility Database."""
        return [self.feeds_id_get("gtfsFeedFoo")]

    def feeds_gtfs_get(
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
        return [self.feeds_id_get("foo")]

    def feeds_gtfs_rt_get(
            self,
            limit: int,
            offset: int,
            filter: str,
            sort: str,
    ) -> List[GtfsRTFeed]:
        """Get some (or all) GTFS feeds from the Mobility Database."""
        return [self.feeds_id_gtfs_rt_get("foo")]

    def feeds_id_datasets_gtfs_get(
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

    def feeds_id_get(
            self,
            id: str,
    ) -> BasicFeed:
        """Get the specified feed from the Mobility Database."""
        return GtfsFeed(id="gtfsFeedFoo", data_type=None, status=None, external_ids=[], provider="providerFoo",
                        feed_name="feedFoo", note="note", source_info=SourceInfo())

    def feeds_id_gtfs_get(
            self,
            id: str,
    ) -> GtfsFeed:
        """Get the specified feed from the Mobility Database."""
        return GtfsFeed(id="gtfsFeedFoo", data_type=None, status=None, external_ids=[], provider="providerFoo",
                        feed_name="feedFoo", note="note", source_info=SourceInfo(), latest_dataset=LatestDataset())

    def feeds_id_gtfs_rt_get(
            self,
            id: str,
    ) -> GtfsRTFeed:
        """Get the specified GTFS Realtime feed from the Mobility Database."""
        return GtfsRTFeed(id="gtfsrtFoo", data_type=None, status=None, externals_ids=[], provider="providerFoo",
                          feed_name="feedFoo", note="Note", source_info=SourceInfo(), entity_type=[],
                          feed_references=[])
