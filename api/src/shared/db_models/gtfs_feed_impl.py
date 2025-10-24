from shared.db_models.bounding_box_impl import BoundingBoxImpl
from shared.db_models.feed_impl import FeedImpl
from shared.database_gen.sqlacodegen_models import Gtfsfeed as GtfsfeedOrm
from shared.db_models.latest_dataset_impl import LatestDatasetImpl
from shared.db_models.location_impl import LocationImpl
from feeds_gen.models.gtfs_feed import GtfsFeed


class GtfsFeedImpl(FeedImpl, GtfsFeed):
    """Implementation of the `GtfsFeed` model.
    This class converts a SQLAlchemy row DB object to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(cls, feed: GtfsfeedOrm | None) -> GtfsFeed | None:
        gtfs_feed: GtfsFeed = super().from_orm(feed)
        if not gtfs_feed:
            return None
        gtfs_feed.locations = [LocationImpl.from_orm(item) for item in feed.locations]
        gtfs_feed.latest_dataset = LatestDatasetImpl.from_orm(feed.latest_dataset)
        gtfs_feed.bounding_box = BoundingBoxImpl.from_orm(feed.bounding_box)
        gtfs_feed.visualization_dataset_id = (
            feed.visualization_dataset.stable_id if feed.visualization_dataset else None
        )
        return gtfs_feed
