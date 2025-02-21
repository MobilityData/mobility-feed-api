from typing import Optional, List
from pydantic import Field
from feeds_operations_gen.models.gtfs_feed import GtfsFeed
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
