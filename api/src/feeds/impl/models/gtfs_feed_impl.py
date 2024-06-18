from database_gen.sqlacodegen_models import Gtfsfeed as GtfsfeedOrm
from feeds.impl.models.basic_feed_impl import BaseFeedImpl
from feeds.impl.models.latest_dataset_impl import LatestDatasetImpl
from feeds.impl.models.location_impl import LocationImpl
from feeds_gen.models.gtfs_feed import GtfsFeed


class GtfsFeedImpl(BaseFeedImpl, GtfsFeed):
    """Implementation of the `GtfsFeed` model.
    This class converts a SQLAlchemy row DB object to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_orm` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True
        orm_mode = True

    @classmethod
    def from_orm(cls, feed: GtfsfeedOrm | None) -> GtfsFeed | None:
        gtfs_feed = super().from_orm(feed)
        if not gtfs_feed:
            return None
        gtfs_feed.locations = [LocationImpl.from_orm(item) for item in feed.locations]

        latest_dataset = next(
            (dataset for dataset in feed.gtfsdatasets if dataset is not None and dataset.latest), None
        )
        gtfs_feed.latest_dataset = LatestDatasetImpl.from_orm(latest_dataset)
        return gtfs_feed
