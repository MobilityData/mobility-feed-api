from feeds_gen.models.operation_gtfs_rt_feed import OperationGtfsRtFeed
from shared.database_gen.sqlacodegen_models import Gtfsrealtimefeed
from shared.db_models.gtfs_rt_feed_impl import GtfsRTFeedImpl


class OperationGtfsRtFeedImpl(GtfsRTFeedImpl, OperationGtfsRtFeed):
    """Base implementation of the feeds models."""

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object.
        """

        from_attributes = True

    def __init__(self, **data):
        super().__init__(**data)
        self.entity_types = self.entity_types or []
        self.locations = self.locations or []
        self.redirects = self.redirects or []
        self.feed_references = self.feed_references or []

    @classmethod
    def from_orm(cls, feed: Gtfsrealtimefeed | None) -> OperationGtfsRtFeed | None:
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
