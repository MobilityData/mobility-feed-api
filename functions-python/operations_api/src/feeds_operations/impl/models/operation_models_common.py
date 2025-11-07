from feeds_gen.models.operation_create_request_gtfs_feed import (
    OperationCreateRequestGtfsFeed,
)
from feeds_gen.models.operation_create_request_gtfs_rt_feed import (
    OperationCreateRequestGtfsRtFeed,
)
from shared.database_gen.sqlacodegen_models import Feed


def get_feed_dict(
    operation_request: OperationCreateRequestGtfsRtFeed
    | OperationCreateRequestGtfsFeed,
):
    """Get a dict representation of the feed from the operation request model."""
    feed_dict = operation_request.model_dump()
    # Fix enum fields that have different names in the DB model
    if operation_request.status:
        feed_dict["status"] = operation_request.status.value
    # Add to the dict any fields that are in the source info model
    feed_dict.update(operation_request.source_info.model_dump())
    if operation_request.external_ids:
        feed_dict.update(
            {
                Feed.externalids.key: [
                    ext_id.model_dump() for ext_id in operation_request.external_ids
                ]
            }
        )
    if operation_request.redirects:
        feed_dict.update(
            {
                Feed.redirectingids.key: [
                    redir.model_dump() for redir in operation_request.redirects
                ]
            }
        )
    if operation_request.related_links:
        feed_dict.update(
            {
                Feed.feedrelatedlinks.key: [
                    rel_link.model_dump()
                    for rel_link in operation_request.related_links
                ]
            }
        )
    return feed_dict
