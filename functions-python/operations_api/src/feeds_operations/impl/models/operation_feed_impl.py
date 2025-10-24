from feeds_gen.models.operation_feed import OperationFeed
from shared.database_gen.sqlacodegen_models import Feed
from shared.db_models.basic_feed_impl import BaseFeedImpl


class OperationFeedImpl(BaseFeedImpl, OperationFeed):
    """Base implementation of the feeds models."""

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object.
        """

        from_attributes = True

    @classmethod
    def from_orm(cls, feed: Feed | None) -> OperationFeed | None:
        """Convert a SQLAlchemy row object to a Pydantic model."""
        if not feed:
            return None
        operation_feed = super().from_orm(feed)
        if not operation_feed:
            return None

        data = dict(operation_feed.__dict__)
        # Override id and add stable_id
        data["id"] = feed.id
        data["stable_id"] = feed.stable_id
        # Add missing fields from public API model
        data["status"] = feed.status
        data["operational_status"] = feed.operational_status

        return cls.model_construct(**data)
