from typing import List

from pydantic import Field

from feeds_operations_gen.models.gtfs_rt_feed_response import (
    GtfsRtFeedResponse as GtfsRtFeed,
)
from .basic_feed_impl import BaseFeedImpl


class GtfsRtFeedImpl(BaseFeedImpl, GtfsRtFeed):
    """Implementation of the GTFS-RT feed model."""

    entity_types: List[str] = Field(
        default_factory=list, description="Types of GTFS-RT entities"
    )
    feed_references: List[str] = Field(
        default_factory=list, description="References to related GTFS feeds"
    )

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object.
        """

        from_attributes = True
