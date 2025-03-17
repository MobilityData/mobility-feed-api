from typing import List

from pydantic import Field

from feeds_operations_gen.models.gtfs_rt_feed_response import (
    GtfsRtFeedResponse as GtfsRtFeed,
)
from shared.database_gen.sqlacodegen_models import Gtfsrealtimefeed as GtfsRTFeedOrm
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

    @classmethod
    def from_orm(cls, feed: GtfsRTFeedOrm | None) -> GtfsRtFeed | None:
        """Convert ORM object to Pydantic model without validation."""
        if not feed:
            return None

        gtfs_rt_feed = super().from_orm(feed)
        if not gtfs_rt_feed:
            return None

        gtfs_rt_feed_dict = gtfs_rt_feed.model_dump()

        gtfs_rt_feed_dict["entity_types"] = []
        gtfs_rt_feed_dict["feed_references"] = []

        if hasattr(feed, "entitytypes"):
            entity_types = [item.name for item in (feed.entitytypes or [])]
            gtfs_rt_feed_dict["entity_types"] = (
                sorted(entity_types) if entity_types else []
            )

        if hasattr(feed, "gtfs_feeds"):
            feed_references = [item.stable_id for item in (feed.gtfs_feeds or [])]
            gtfs_rt_feed_dict["feed_references"] = (
                sorted(feed_references) if feed_references else []
            )

        return cls.model_construct(**gtfs_rt_feed_dict)
