import logging

from pydantic import model_validator

from feeds_operations_gen.models.base_feed import BaseFeed
from feeds_operations_gen.models.data_type import DataType
from shared.database_gen.sqlacodegen_models import Feed

logger = logging.getLogger(__name__)


class BaseFeedImpl(BaseFeed):
    """Base implementation of the feeds models."""

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object.
        """

        from_attributes = True

    @model_validator(mode="before")
    def validate_feed_type(cls, values: dict | object) -> dict | object:
        """Validate data type matches the model class."""
        if not isinstance(values, dict):
            return values

        data_type = values.get("data_type")
        if not data_type:
            return values

        if cls.__name__.startswith("GtfsFeed") and data_type != DataType.GTFS:
            raise ValueError(
                f"Invalid data_type '{data_type}' for GtfsFeedResponse. Must be 'gtfs'"
            )
        elif cls.__name__.startswith("GtfsRtFeed") and data_type != DataType.GTFS_RT:
            raise ValueError(
                f"Invalid data_type '{data_type}' for GtfsRtFeedResponse. Must be 'gtfs_rt'"
            )
        return values

    @classmethod
    def from_orm(cls, feed: Feed | None) -> BaseFeed | None:
        """Convert a SQLAlchemy row object to a Pydantic model."""
        if not feed:
            return None

        try:
            logger.debug(
                "Converting feed %s with fields: %s",
                feed.stable_id,
                {
                    "id": feed.id,
                    "stable_id": feed.stable_id,
                    "data_type": feed.data_type,
                    "status": feed.status,
                    "provider": feed.provider,
                    "operational_status": feed.operational_status,
                },
            )

            if not feed.stable_id:
                logger.error("Feed %s missing stable_id", feed.id)
                return None
            if not feed.data_type:
                logger.error("Feed %s missing data_type", feed.stable_id)
                return None
            if not feed.status:
                logger.error("Feed %s missing status", feed.stable_id)
                return None

            if feed.data_type not in ["gtfs", "gtfs_rt", "gbfs"]:
                logger.error(
                    "Feed %s has invalid data_type: %s", feed.stable_id, feed.data_type
                )
                return None

            if feed.operational_status and feed.operational_status not in [
                "wip",
                "published",
            ]:
                logger.error(
                    "Feed %s has invalid operational_status: %s",
                    feed.stable_id,
                    feed.operational_status,
                )
                return None

            return super().model_validate(feed)
        except Exception as e:
            logger.error(
                "Failed to convert feed %s: %s",
                feed.stable_id if feed else "None",
                str(e),
            )
            return None
