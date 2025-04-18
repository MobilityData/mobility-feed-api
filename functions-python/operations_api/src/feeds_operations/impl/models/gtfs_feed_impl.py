from typing import Optional, List

from pydantic import Field

from feeds_operations_gen.models.gtfs_feed_response import GtfsFeedResponse as GtfsFeed
from shared.database_gen.sqlacodegen_models import Gtfsfeed as GtfsfeedOrm
from .basic_feed_impl import BaseFeedImpl


class GtfsFeedImpl(BaseFeedImpl, GtfsFeed):
    """Implementation of the GTFS feed model."""

    entity_types: Optional[List[str]] = Field(
        default=None, exclude=True, description="Not used in GTFS feeds"
    )
    feed_references: Optional[List[str]] = Field(
        default=None, exclude=True, description="Not used in GTFS feeds"
    )

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object.
        """

        from_attributes = True

    @classmethod
    def from_orm(cls, feed: GtfsfeedOrm | None) -> GtfsFeed | None:
        """Convert ORM object to Pydantic model."""
        if not feed:
            return None

        gtfs_feed = super().from_orm(feed)
        if not gtfs_feed:
            return None

        return cls.model_construct(**gtfs_feed.__dict__)
