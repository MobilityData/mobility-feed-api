import os
from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.helpers.query_helper import get_feeds_with_missing_bounding_boxes_query
from shared.database_gen.sqlacodegen_models import Gtfsfeed, Gtfsdataset


def rebuild_missing_bounding_boxes_handler(payload) -> dict:
    (
        dry_run,
        prod_env,
    ) = get_parameters(payload)

    return rebuild_missing_bounding_boxes(
        dry_run=dry_run,
        prod_env=prod_env,
    )


@with_db_session
def rebuild_missing_bounding_boxes(
    dry_run: bool = True,
    prod_env: bool = False,
    db_session: Session | None = None,
) -> dict:
    query = get_feeds_with_missing_bounding_boxes_query(db_session)
    feeds = query.all()

    if dry_run:
        total_processed = len(feeds)
        return {
            "message": f"Dry run: {total_processed} feeds with missing bounding boxes found.",
            "total_processed": total_processed,
        }
    else:
        


def get_parameters(payload):
    """
    Get parameters from the payload and environment variables.

    Args:
        payload (dict): dictionary containing the payload data.
    Returns:
        dict: dict with: dry_run, prod_env parameters
    """
    prod_env = os.getenv("ENV", "").lower() == "prod"
    dry_run = payload.get("dry_run", True)
    dry_run = dry_run if isinstance(dry_run, bool) else str(dry_run).lower() == "true"
    return dry_run, prod_env
