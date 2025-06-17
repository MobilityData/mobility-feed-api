import logging
import os
from typing import Dict, List
from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.helpers.pub_sub import publish_messages
from shared.helpers.query_helper import get_feeds_with_missing_bounding_boxes_query
from shared.database_gen.sqlacodegen_models import Gtfsfeed


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
    logging.info("Filtering for unprocessed feeds.")
    query = query.filter(~Gtfsfeed.feedlocationgrouppoints.any())
    feeds = query.all()

    if dry_run:
        total_processed = len(feeds)
        return {
            "message": f"Dry run: {total_processed} feeds with missing bounding boxes found.",
            "total_processed": total_processed,
        }
    else:
        # publish a message to a Pub/Sub topic for each feed
        pubsub_topic_name = os.getenv("PUBSUB_TOPIC_NAME", None)  # todo: set new name
        project_id = os.getenv("PROJECT_ID")

        logging.info("Publishing to topic: %s", pubsub_topic_name)
        publish_messages(prepare_feeds_data(feeds), project_id, pubsub_topic_name)

        total_processed = len(feeds)
        return {
            "message": f"Successfully published {total_processed} feeds with missing bounding boxes.",
            "total_processed": total_processed,
        }


@with_db_session
def extract_country_codes_from_feeds(
    feeds: List[Gtfsfeed], db_session: Session = None
) -> List[str]:
    """
    Extract unique country codes from a list of feeds.

    Args:
        feeds: List of Gtfsfeed objects
        db_session: SQLAlchemy database session

    Returns:
        List of unique country codes
    """
    country_codes = set()

    for feed in feeds:
        # Check if locations are already loaded, if not load them
        if not feed.locations:
            db_session.refresh(feed, ["locations"])

        # Extract country codes from the feed's locations
        for location in feed.locations:
            if location.country_code:
                country_codes.add(location.country_code)

    return list(country_codes)


def prepare_feeds_data(feeds: List[Gtfsfeed]) -> List[Dict]:
    """
    Format feeds data for Pub/Sub messages.

    Args:
        feeds: List of Gtfsfeed objects

    Returns:
        List of dictionaries with feed data
    """
    data = []

    for feed in feeds:
        # Get the latest dataset
        if feed.gtfsdatasets and any(dataset.latest for dataset in feed.gtfsdatasets):
            latest_dataset = next(
                dataset for dataset in feed.gtfsdatasets if dataset.latest
            )

            data.append(
                {
                    "stable_id": feed.stable_id,
                    "dataset_id": latest_dataset.stable_id,
                    "url": latest_dataset.hosted_url,
                }
            )

    return data


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
