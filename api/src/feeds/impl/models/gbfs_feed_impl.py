from feeds.impl.models.bounding_box_impl import BoundingBoxImpl
from feeds.impl.models.feed_impl import FeedImpl
from feeds.impl.models.gbfs_version_impl import GbfsVersionImpl
from shared.database_gen.sqlacodegen_models import Gbfsfeed as GbfsFeedOrm
from feeds.impl.models.location_impl import LocationImpl
from feeds_gen.models.gbfs_feed import GbfsFeed


class GbfsFeedImpl(FeedImpl, GbfsFeed):
    """Implementation of the `GtfsFeed` model.
    This class converts a SQLAlchemy row DB object to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(cls, feed: GbfsFeedOrm | None) -> GbfsFeed | None:
        gbfs_feed: GbfsFeed = super().from_orm(feed)
        if not gbfs_feed:
            return None
        gbfs_feed.locations = [LocationImpl.from_orm(item) for item in feed.locations] if feed.locations else []
        gbfs_feed.system_id = feed.system_id
        gbfs_feed.provider_url = feed.operator_url
        gbfs_feed.versions = (
            [GbfsVersionImpl.from_orm(item) for item in feed.gbfsversions if item is not None]
            if feed.gbfsversions
            else []
        )
        gbfs_feed.bounding_box = BoundingBoxImpl.from_orm(feed.bounding_box)
        gbfs_feed.bounding_box_generated_at = feed.bounding_box_generated_at
        return gbfs_feed
