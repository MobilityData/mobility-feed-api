# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from feeds_gen.models.basic_feed import BasicFeed
from feeds_gen.models.gtfs_feed import GtfsFeed
from feeds_gen.security_api import get_token_ApiKeyAuth

class BaseFeedsApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseFeedsApi.subclasses = BaseFeedsApi.subclasses + (cls,)
    def feeds_get(
        self,
        limit: int,
        offset: int,
        filter: str,
        sort: str,
    ) -> List[BasicFeed]:
        """Get some (or all) feeds from the Mobility Database."""
        ...


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
        ...


    def feeds_gtfs_id_get(
        self,
        id: str,
    ) -> GtfsFeed:
        """Get the specified feed from the Mobility Database."""
        ...


    def feeds_id_get(
        self,
        id: str,
    ) -> BasicFeed:
        """Get the specified feed from the Mobility Database."""
        ...
