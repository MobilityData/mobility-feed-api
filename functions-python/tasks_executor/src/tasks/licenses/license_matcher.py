import logging

from sqlalchemy import asc, func
from sqlalchemy.orm import Session

from shared.common.license_utils import resolve_license, MatchingLicense
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Feed, FeedLicenseChange
from shared.helpers.runtime_metrics import track_metrics


def get_parameters(payload):
    dry_run = payload.get("dry_run", False)
    only_unmatched = payload.get("only_unmatched", True)
    feed_stable_id = payload.get("feed_stable_id", None)
    return dry_run, only_unmatched, feed_stable_id


def match_license_handler(payload):
    """
    Handler for matching licenses with feeds.

    Args:
        payload (dict): Incoming payload data.

    """
    (dry_run, only_unmatched, feed_stable_id) = get_parameters(payload)
    return match_licenses_task(dry_run, only_unmatched, feed_stable_id)


def assign_feed_license(feed: Feed, license_match: MatchingLicense):
    """Assign the matched license to the feed and log the change if license is different."""
    if license_match.license_id != feed.license_id:
        logging.info(
            "New license match for feed %s: %s",
            feed.stable_id,
            license_match.license_id,
        )
        feed.license_id = license_match.license_id
        feed.license_notes = license_match.notes
        feed_license_change: FeedLicenseChange = FeedLicenseChange(
            feed_id=feed.id,
            changed_at=None,  # will be set by DB default
            feed_license_url=feed.license_url,
            matched_license_id=license_match.license_id,
            confidence=license_match.confidence,
            match_type=license_match.match_type,
            matched_name=license_match.matched_name,
            matched_catalog_url=license_match.matched_catalog_url,
            matched_source=license_match.matched_source,
            notes=license_match.notes,
            regional_id=license_match.regional_id,
        )
        feed.feed_license_changes.append(feed_license_change)
    else:
        logging.info("Feed %s license unchanged: %s", feed.stable_id, feed.license_id)


def process_feed(feed, dry_run, db_session):
    """Process a single feed to match its license."""
    result = None
    license_matches = resolve_license(feed.license_url, db_session=db_session)
    if license_matches:
        license_first_match = sorted(
            license_matches, key=lambda x: x.confidence, reverse=True
        )[0]
        result = {
            "feed_id": feed.id,
            "feed_stable_id": feed.stable_id,
            "feed_data_type": feed.data_type,
            "feed_license_url": feed.license_url,
            "matched_license_id": license_first_match.license_id,
            "matched_spdx_id": license_first_match.spdx_id,
            "confidence": license_first_match.confidence,
            "match_type": license_first_match.match_type,
            "matched_name": license_first_match.matched_name,
            "matched_catalog_url": license_first_match.matched_catalog_url,
            "matched_source": license_first_match.matched_source,
            "notes": license_first_match.notes,
            "regional_id": license_first_match.regional_id,
        }
        if not dry_run:
            assign_feed_license(feed, license_first_match)
    return result


@track_metrics(metrics=("time", "memory", "cpu"))
@with_db_session
def match_licenses_task(
    dry_run: bool,
    only_unmatched: bool,
    feed_stable_id: str = None,
    db_session: Session = None,
):
    result = []
    if feed_stable_id:
        feed = db_session.query(Feed).filter(Feed.stable_id == feed_stable_id).first()
        if not feed:
            logging.error("Feed with stable_id %s not found.", feed_stable_id)
            raise ValueError(f"Feed with stable_id {feed_stable_id} not found.")
        result.append(process_feed(feed, dry_run, db_session))
    else:
        result = process_all_feeds(dry_run, only_unmatched, db_session)
    return result


def process_all_feeds(dry_run: bool, only_unmatched: bool, db_session: Session | None):
    result = []
    batch_size = 500
    last_id = None
    i = 0
    total_processed = 0
    while True:
        logging.info("Processing batch %d", i)
        batch_query = db_session.query(Feed).filter(
            "" != func.coalesce(Feed.license_url, "")
        )
        if last_id is not None:
            batch_query = batch_query.filter(Feed.id > last_id)
        if only_unmatched:
            batch_query = batch_query.filter(Feed.license_id.is_(None))
        batch = batch_query.order_by(asc(Feed.id)).limit(batch_size).all()
        if not batch:
            break
        total_processed += len(batch)
        for feed in batch:
            feed_match = process_feed(feed, dry_run, db_session)
            if feed_match:
                result.append(feed_match)
        if not dry_run:
            # Flush the batch updates to the database
            db_session.flush()

        last_id = batch[-1].id
        db_session.expunge_all()
        logging.info(
            "Processed batch %d. Total processed %d, so far matched licenses: %d",
            i,
            total_processed,
            len(result),
        )
        i += 1
    logging.info(
        "Total processed feeds %d. Total matched licenses: %d",
        total_processed,
        len(result),
    )
    return result
