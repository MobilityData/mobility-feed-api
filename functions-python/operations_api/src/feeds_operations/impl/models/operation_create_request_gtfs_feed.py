from feeds_gen.models.operation_create_request_gtfs_feed import (
    OperationCreateRequestGtfsFeed,
)
from feeds_operations.impl.models.operation_models_common import get_feed_dict
from shared.database_gen.sqlacodegen_models import Feed, Gtfsfeed
from shared.db_models.feed_impl import FeedImpl
from shared.db_models.gtfs_feed_impl import GtfsFeedImpl
from shared.helpers.transform import sanitize_value


class OperationCreateRequestGtfsFeedImpl(GtfsFeedImpl, OperationCreateRequestGtfsFeed):
    """Base implementation of the feeds models."""

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object.
        """

        from_attributes = True

    @classmethod
    def to_orm(
        cls, operation_request_gtfs_feed: OperationCreateRequestGtfsFeed | None
    ) -> Gtfsfeed | None:
        if not operation_request_gtfs_feed:
            return None
        # This transforms the Pydantic model into a dict representation and works for all fields with the same name
        gtfs_feed_dict = get_feed_dict(operation_request_gtfs_feed)
        gtfs_feed_dict = sanitize_value(gtfs_feed_dict)
        feed: Feed = FeedImpl.to_orm_from_dict(gtfs_feed_dict)

        allowed = {col.name for col in Gtfsfeed.__mapper__.columns} | {
            rel.key for rel in Gtfsfeed.__mapper__.relationships
        }
        data = {k: v for k, v in feed.__dict__.items() if k in allowed}

        result = Gtfsfeed(**data)
        result.operational_status = (
            (sanitize_value(operation_request_gtfs_feed.operational_status))
            if operation_request_gtfs_feed.operational_status
            else "wip"
        )
        return result
