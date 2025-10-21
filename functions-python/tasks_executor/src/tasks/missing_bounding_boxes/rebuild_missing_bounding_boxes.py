import logging
import os
from typing import Dict, List
from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.helpers.pub_sub import publish_messages
from shared.helpers.query_helper import (
    get_feeds_with_missing_bounding_boxes_query,
)
from shared.database_gen.sqlacodegen_models import Gtfsdataset, Gtfsfeed
from datetime import datetime


def rebuild_missing_bounding_boxes_handler(payload) -> dict:
    (dry_run, after_date) = get_parameters(payload)

    return rebuild_missing_bounding_boxes(
        dry_run=dry_run,
        after_date=after_date,
    )


@with_db_session
def rebuild_missing_bounding_boxes(
    dry_run: bool = True,
    after_date: str = None,
    db_session: Session | None = None,
) -> dict:
    """
    Find GTFS feeds/datasets missing bounding boxes and either log or publish them for processing.

    Args:
        dry_run (bool): If True, only logs the number of feeds found (no publishing).
        after_date (str, optional): ISO date string (YYYY-MM-DD). Only datasets downloaded after this date are included.
        db_session (Session, optional): SQLAlchemy session, injected by @with_db_session.

    Returns:
        dict: Summary message and count of processed feeds.
    """
    filter_after = None
    if after_date:
        try:
            filter_after = datetime.fromisoformat(after_date)
        except Exception:
            logging.warning(
                "Invalid after_date format, expected ISO format (YYYY-MM-DD)"
            )
    query = get_feeds_with_missing_bounding_boxes_query(db_session)
    if filter_after:
        query = query.filter(Gtfsdataset.downloaded_at >= filter_after)
    feeds = query.all()

    if dry_run:
        total_processed = len(feeds)
        logging.info(
            "Dry run mode: %s feeds with missing bounding boxes found, filtered after %s.",
            total_processed,
            after_date,
        )
        return {
            "message": f"Dry run: {total_processed} feeds with missing bounding boxes found."
            + (f" Filtered after: {filter_after}" if filter_after else ""),
            "total_processed": total_processed,
        }
    else:
        # publish a message to a Pub/Sub topic for each feed
        pubsub_topic_name = os.getenv("BOUNDING_BOXES_PUBSUB_TOPIC_NAME")
        project_id = os.getenv("PROJECT_ID")

        logging.info("Publishing to topic: %s", pubsub_topic_name)
        feeds_data = prepare_feeds_data(db_session)
        publish_messages(feeds_data, project_id, pubsub_topic_name)

        total_processed = len(feeds_data)
        logging.info(
            "Published %s feeds with missing bounding boxes to Pub/Sub topic: %s, filtered after %s.",
            total_processed,
            pubsub_topic_name,
            after_date,
        )
        return {
            "message": f"Successfully published {total_processed} feeds with missing bounding boxes."
            + (f" Filtered after: {filter_after}" if filter_after else ""),
            "total_processed": total_processed,
        }


def prepare_feeds_data(db_session: Session | None = None) -> List[Dict]:
    """
    Format feeds data for Pub/Sub messages.

    Args:
        feeds: List of Gtfsfeed objects

    Returns:
        List of dictionaries with feed data
    """
    data = []
    query = get_feeds_with_missing_bounding_boxes_query(db_session)
    feeds: list[Gtfsfeed] = query.all()

    for feed in feeds:
        # Get the latest dataset
        if feed.latest_dataset:
            data.append(
                {
                    "stable_id": feed.stable_id,
                    "dataset_id": feed.latest_dataset.stable_id,
                    "url": feed.latest_dataset.hosted_url,
                }
            )

    return data


def get_parameters(payload):
    """
    Get parameters from the payload and environment variables.

    Args:
        payload (dict): dictionary containing the payload data.
    Returns:
        tuple: (dry_run, after_date)
    """
    dry_run = payload.get("dry_run", True)
    dry_run = dry_run if isinstance(dry_run, bool) else str(dry_run).lower() == "true"
    after_date = payload.get("after_date", None)
    return dry_run, after_date
