from feeds_gen.models.operation_gtfs_feed import OperationGtfsFeed
from shared.database_gen.sqlacodegen_models import Gtfsfeed
from shared.db_models.gtfs_feed_impl import GtfsFeedImpl


class OperationGtfsFeedImpl(GtfsFeedImpl, OperationGtfsFeed):
    """Base implementation of the feeds models."""

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object.
        """

        from_attributes = True

    def __init__(self, **data):
        super().__init__(**data)
        self.locations = self.locations or []
        self.redirects = self.redirects or []

    @classmethod
    def from_orm(cls, feed: Gtfsfeed | None) -> OperationGtfsFeed | None:
        """Convert a SQLAlchemy row object to a Pydantic model."""
        if not feed:
            return None
        operation_gtfs_feed = super().from_orm(feed)
        if not operation_gtfs_feed:
            return None

        data = dict(operation_gtfs_feed.__dict__)
        # Override id and add stable_id
        data["id"] = feed.id
        data["stable_id"] = feed.stable_id
        # Add missing fields from public API model
        data["operational_status"] = feed.operational_status

        return cls.model_construct(**data)
