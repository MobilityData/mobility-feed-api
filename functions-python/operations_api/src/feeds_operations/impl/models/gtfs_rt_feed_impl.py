import logging
from typing import List

from feeds_operations_gen.models.gtfs_rt_feed_response import (
    GtfsRtFeedResponse as GtfsRtFeed,
)
from pydantic import Field
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

    def to_dict(self) -> dict:
        """Ensure entity_types and feed_references are included in serialized output."""
        _dict = super().to_dict()

        if not _dict.get("entity_types"):
            _dict["entity_types"] = []
        if not _dict.get("feed_references"):
            _dict["feed_references"] = []

        return _dict

    @classmethod
    def from_orm(cls, feed: GtfsRTFeedOrm | None) -> GtfsRtFeed | None:
        """Convert ORM object to Pydantic model without validation.
        This is a "best-effort approach" that copies data from ORM to Pydantic model.
        """
        if not feed:
            return None

        try:
            gtfs_rt_feed = super().from_orm(feed)
            if not gtfs_rt_feed:
                return None

            return cls.model_construct(**gtfs_rt_feed.__dict__)

        except Exception as e:
            logging.error(
                f"Error converting GTFS-RT feed {feed.stable_id if feed else 'unknown'}: {e}"
            )
            return None
