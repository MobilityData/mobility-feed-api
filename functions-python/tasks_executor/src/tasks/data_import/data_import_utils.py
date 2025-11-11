import os
import uuid
from datetime import datetime
from typing import Tuple, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.database_gen.sqlacodegen_models import Feed, Officialstatushistory, Entitytype, Gtfsfeed
import logging
import json
from google.cloud import pubsub_v1


PROJECT_ID = os.getenv("PROJECT_ID")
DATASET_BATCH_TOPIC = os.getenv("DATASET_PROCESSING_TOPIC_NAME")

logger = logging.getLogger(__name__)
T = TypeVar("T", bound="Feed")


def trigger_dataset_download(
    feed: Feed, execution_id: str, publisher: pubsub_v1.PublisherClient
) -> None:
    """Publishes the feed to the configured Pub/Sub topic."""
    topic_path = publisher.topic_path(PROJECT_ID, DATASET_BATCH_TOPIC)
    logging.debug("Publishing to Pub/Sub topic: %s", topic_path)

    message_data = {
        "execution_id": execution_id,
        "producer_url": feed.producer_url,
        "feed_stable_id": feed.stable_id,
        "feed_id": feed.id,
        "dataset_id": None,
        "dataset_hash": None,
        "authentication_type": feed.authentication_type,
        "authentication_info_url": feed.authentication_info_url,
        "api_key_parameter_name": feed.api_key_parameter_name,
    }

    try:
        # Convert to JSON string
        json_message = json.dumps(message_data)
        future = publisher.publish(topic_path, data=json_message.encode("utf-8"))
        future.add_done_callback(
            lambda _: logging.info(
                "Published feed %s to dataset batch topic", feed.stable_id
            )
        )
        future.result()
        logging.info("Message published for feed %s", feed.stable_id)
    except Exception as e:
        logging.error("Error publishing to dataset batch topic: %s", str(e))
        raise


def _get_or_create_entity_type(session: Session, entity_type_name: str) -> Entitytype:
    """Get or create an Entitytype by name."""
    logger.debug("Looking up Entitytype name=%s", entity_type_name)
    et = session.scalar(select(Entitytype).where(Entitytype.name == entity_type_name))
    if et:
        logger.debug("Found existing Entitytype name=%s", entity_type_name)
        return et
    et = Entitytype(name=entity_type_name)
    session.add(et)
    session.flush()
    logger.info("Created Entitytype name=%s", entity_type_name)
    return et

def get_feed(
        session: Session,
        stable_id: str,
        model: Type[T] = Feed,
) -> T | None:
    """Get a Feed by stable_id."""
    logger.debug("Lookup feed stable_id=%s", stable_id)
    feed = session.scalar(select(model).where(model.stable_id == stable_id))
    if feed:
        logger.debug("Found existing feed stable_id=%s id=%s", stable_id, feed.id)
    else:
        logger.debug("No Feed found with stable_id=%s", stable_id)
    return feed


def _get_or_create_feed(
        session: Session,
        model: Type[T],
        stable_id: str,
        data_type: str,
        is_official: bool = True,
        official_notes: str = "Imported from JBDA as official feed.",
        reviewer_email: str = "emma@mobilitydata.org",
) -> Tuple[T, bool]:
    """Generic helper to get or create a Feed subclass (Gtfsfeed, Gtfsrealtimefeed) by stable_id."""
    logger.debug(
        "Lookup feed model=%s stable_id=%s",
        getattr(model, "__name__", str(model)),
        stable_id,
    )
    feed = session.scalar(select(model).where(model.stable_id == stable_id))
    if feed:
        logger.info(
            "Found existing %s stable_id=%s id=%s",
            getattr(model, "__name__", str(model)),
            stable_id,
            feed.id,
        )
        return feed, False

    new_id = str(uuid.uuid4())
    feed = model(
        id=new_id,
        data_type=data_type,
        stable_id=stable_id,
        official=True,
        official_updated_at=datetime.now(),
    )
    if is_official:
        feed.officialstatushistories = [
            Officialstatushistory(
                is_official=True,
                reviewer_email=reviewer_email,
                timestamp=datetime.now(),
                notes=official_notes,
            )
        ]
    session.add(feed)
    session.flush()
    logger.info(
        "Created %s stable_id=%s id=%s data_type=%s",
        getattr(model, "__name__", str(model)),
        stable_id,
        new_id,
        data_type,
    )
    return feed, True
