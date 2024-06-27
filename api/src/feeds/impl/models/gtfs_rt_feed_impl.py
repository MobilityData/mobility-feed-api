from database_gen.sqlacodegen_models import Gtfsrealtimefeed as GtfsRTFeedOrm
from feeds.impl.models.basic_feed_impl import BaseFeedImpl
from feeds.impl.models.location_impl import LocationImpl
from feeds_gen.models.gtfs_rt_feed import GtfsRTFeed
from feeds.impl.models.entity_type_impl import EntitytypeImpl


class GtfsRTFeedImpl(BaseFeedImpl, GtfsRTFeed):
    """Implementation of the 'Gtfsrealtimefeed' model."""

    class Config:
        """Pydantic configuration.
        Enabling 'from_orm' method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True
        orm_mode = True

    @classmethod
    def from_orm(cls, feed: GtfsRTFeedOrm | None) -> GtfsRTFeed | None:
        gtfs_rt_feed = super().from_orm(feed)
        if not gtfs_rt_feed:
            return None
        gtfs_rt_feed.locations = [LocationImpl.from_orm(item) for item in feed.locations]
        gtfs_rt_feed.entity_types = [EntitytypeImpl.from_orm(item) for item in feed.entitytypes]
        gtfs_rt_feed.feed_references = [item.stable_id for item in feed.gtfs_feeds]
        return gtfs_rt_feed
