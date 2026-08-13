import logging
import os
import uuid
from datetime import datetime
from typing import Tuple, Type, TypeVar, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.common.gcp_utils import create_web_revalidation_task
from shared.database_gen.sqlacodegen_models import (
    Feed,
    Officialstatushistory,
    Entitytype,
    License,
)
from shared.helpers.pub_sub import trigger_dataset_download

logger = logging.getLogger(__name__)
T = TypeVar("T", bound="Feed")


def get_or_create_entity_type(session: Session, entity_type_name: str) -> Entitytype:
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


def get_license(session: Session, license_id: str) -> Optional[License]:
    """Get a License by ID."""
    logger.debug("Lookup License id=%s", license_id)
    if not license_id:
        logger.debug("No License ID provided")
        return None
    license = session.get(License, license_id)
    if license:
        logger.debug("Found existing License id=%s", license_id)
        return license
    logger.debug("No License found with id=%s", license_id)
    return None


def get_or_create_feed(
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
        official=is_official,
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


def commit_changes(
    db_session: Session,
    feeds_to_publish: list[Feed],
    total_processed: int,
    changed_feed_stable_ids: list[str] | None = None,
):
    """
    Commit DB changes, trigger dataset downloads for new feeds,
    and trigger website cache revalidation for changed feeds.

    Shared by the JBDA, ODPT and TDG import tasks -- all three call this the
    same way: commit_changes(db_session, feeds_to_publish, total_processed,
    changed_feed_stable_ids).

    When ENVIRONMENT=local, the commit still happens but the Pub/Sub dataset
    download trigger and the web revalidation Cloud Task are both skipped, so
    local runs never fire real external side effects.
    """
    try:
        logger.info("Commit after processing items (count=%d)", total_processed)
        db_session.commit()
        if os.getenv("ENVIRONMENT", "").lower() == "local":
            logger.info(
                "ENVIRONMENT=local; skipping dataset download trigger and web revalidation."
            )
            return
        execution_id = str(uuid.uuid4())
        for feed in feeds_to_publish:
            trigger_dataset_download(feed, execution_id)
        if changed_feed_stable_ids:
            try:
                create_web_revalidation_task(changed_feed_stable_ids)
            except Exception as e:
                logger.warning("Failed to enqueue revalidation tasks: %s", e)
    except IntegrityError:
        db_session.rollback()
        logger.exception("Commit failed with IntegrityError; rolled back")
