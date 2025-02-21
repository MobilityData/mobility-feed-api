from typing import List, Optional

from feeds_operations_gen.models.gtfs_rt_feed import GtfsRtFeed
from pydantic import Field
from .basic_feed_impl import BaseFeedImpl


class GtfsRtFeedImpl(BaseFeedImpl, GtfsRtFeed):
    """Implementation of the GTFS-RT feed model."""

    entity_types: Optional[List[str]] = Field(
        default=None, description="Types of GTFS-RT entities"
    )
    feed_references: Optional[List[str]] = Field(
        default=None, description="References to related GTFS feeds"
    )

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object.
        """

        from_attributes = True
