from feeds_gen.models.operation_create_request_gtfs_feed import (
    OperationCreateRequestGtfsFeed,
)
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
        gtfs_feed_dict = operation_request_gtfs_feed.model_dump()
        # Fix enum fields that have different names in the DB model
        if operation_request_gtfs_feed.status:
            gtfs_feed_dict["status"] = operation_request_gtfs_feed.status.value
        # Add to the dict any fields that are in the source info model
        gtfs_feed_dict.update(operation_request_gtfs_feed.source_info.model_dump())
        if operation_request_gtfs_feed.external_ids:
            gtfs_feed_dict.update(
                {
                    Feed.externalids.key: [
                        ext_id.model_dump()
                        for ext_id in operation_request_gtfs_feed.external_ids
                    ]
                }
            )
        if operation_request_gtfs_feed.redirects:
            gtfs_feed_dict.update(
                {
                    Feed.redirectingids.key: [
                        redir.model_dump()
                        for redir in operation_request_gtfs_feed.redirects
                    ]
                }
            )
        if operation_request_gtfs_feed.related_links:
            gtfs_feed_dict.update(
                {
                    Feed.feedrelatedlinks.key: [
                        rel_link.model_dump()
                        for rel_link in operation_request_gtfs_feed.related_links
                    ]
                }
            )

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
