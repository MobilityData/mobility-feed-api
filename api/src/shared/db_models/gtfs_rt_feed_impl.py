from shared.db_models.feed_impl import FeedImpl
from shared.database_gen.sqlacodegen_models import Gtfsrealtimefeed as GtfsRTFeedOrm
from shared.db_models.location_impl import LocationImpl
from feeds_gen.models.gtfs_rt_feed import GtfsRTFeed


class GtfsRTFeedImpl(FeedImpl, GtfsRTFeed):
    """Implementation of the 'Gtfsrealtimefeed' model."""

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(cls, feed: GtfsRTFeedOrm | None) -> GtfsRTFeed | None:
        gtfs_rt_feed: GtfsRTFeed = super().from_orm(feed)
        if not gtfs_rt_feed:
            return None
        gtfs_rt_feed.locations = [LocationImpl.from_orm(item) for item in feed.locations] if feed.locations else []
        gtfs_rt_feed.entity_types = [item.name for item in feed.entitytypes] if feed.entitytypes else []
        gtfs_rt_feed.feed_references = [item.stable_id for item in feed.gtfs_feeds] if feed.gtfs_feeds else []
        return gtfs_rt_feed
