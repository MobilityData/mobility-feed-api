from feeds_gen.models.operation_create_request_gtfs_rt_feed import (
    OperationCreateRequestGtfsRtFeed,
)
from feeds_operations.impl.models.operation_models_common import get_feed_dict
from shared.database_gen.sqlacodegen_models import Gtfsrealtimefeed
from shared.db_models.gtfs_rt_feed_impl import GtfsRTFeedImpl
from shared.helpers.transform import sanitize_value


class OperationCreateRequestGtfsRtFeedImpl(
    GtfsRTFeedImpl, OperationCreateRequestGtfsRtFeed
):
    """Base implementation of the feeds models."""

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object.
        """

        from_attributes = True

    @classmethod
    def to_orm(
        cls, operation_request_gtfs_rt_feed: OperationCreateRequestGtfsRtFeed | None
    ) -> Gtfsrealtimefeed | None:
        if not operation_request_gtfs_rt_feed:
            return None
        # This transforms the Pydantic model into a dict representation and works for all fields with the same name
        gtfs_feed_dict = get_feed_dict(operation_request_gtfs_rt_feed)

        gtfs_feed_dict = sanitize_value(gtfs_feed_dict)
        result: Gtfsrealtimefeed = GtfsRTFeedImpl.to_orm_from_dict(gtfs_feed_dict)
        result.operational_status = (
            (sanitize_value(operation_request_gtfs_rt_feed.operational_status))
            if operation_request_gtfs_rt_feed.operational_status
            else "wip"
        )
        return result
