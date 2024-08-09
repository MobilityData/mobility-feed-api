from typing import Dict

from database_gen.sqlacodegen_models import Gtfsrealtimefeed as GtfsRTFeedOrm
from feeds.impl.models.basic_feed_impl import BaseFeedImpl
from feeds.impl.models.location_impl import LocationImpl
from feeds_gen.models.gtfs_rt_feed import GtfsRTFeed
from utils.location_translation import LocationTranslation, translate_feed_locations


class GtfsRTFeedImpl(BaseFeedImpl, GtfsRTFeed):
    """Implementation of the 'Gtfsrealtimefeed' model."""

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(
        cls, feed: GtfsRTFeedOrm | None, location_translations: Dict[str, LocationTranslation] = None
    ) -> GtfsRTFeed | None:
        if location_translations is not None:
            translate_feed_locations(feed, location_translations)
        gtfs_rt_feed: GtfsRTFeed = super().from_orm(feed)
        if not gtfs_rt_feed:
            return None
        gtfs_rt_feed.locations = [LocationImpl.from_orm(item) for item in feed.locations]
        gtfs_rt_feed.entity_types = [item.name for item in feed.entitytypes]
        gtfs_rt_feed.feed_references = [item.stable_id for item in feed.gtfs_feeds]
        return gtfs_rt_feed
