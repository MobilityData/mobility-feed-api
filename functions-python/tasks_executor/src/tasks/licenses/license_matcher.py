import csv
import io
import logging

from sqlalchemy import asc
from sqlalchemy.orm import Session

from shared.common.license_utils import resolve_license
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Feed
from shared.helpers.runtime_metrics import track_metrics

CONTENT_TYPE_JSON = "application/json"
CONTENT_TYPE_CSV = "text/csv"


def get_parameters(payload):
    dry_run = payload.get("dry_run", False)
    only_unmatched = payload.get("only_unmatched", True)
    feed_stable_id = payload.get("feed_stable_id", None)
    content_type = payload.get("content_type", "application/json")
    return dry_run, only_unmatched, feed_stable_id, content_type


def get_csv_response(matches):
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(
        [
            "feed_id",
            "feed_stable_id",
            "feed_data_type",
            "md_url" "feed_license_url",
            "matched_license_id",
            "matched_spdx_id",
            "confidence",
            "match_type",
            "matched_name",
            "matched_catalog_url",
            "matched_source",
        ]
    )
    for entry in matches:
        writer.writerow(
            [
                entry["feed_id"],
                entry["feed_stable_id"],
                entry["feed_data_type"],
                f'https://mobilitydatabase.org/feeds/{entry["feed_stable_id"]}',
                entry["feed_license_url"],
                entry.get("matched_license_id", ""),
                entry.get("matched_spdx_id", ""),
                entry.get("confidence", 1),
                entry.get("match_type", ""),
                entry.get("matched_name", ""),
                entry.get("matched_catalog_url", ""),
                entry.get("matched_source", ""),
            ]
        )
    return csv_buffer.getvalue()


def match_license_handler(payload):
    """
    Handler for populating license rules.

    Args:
        payload (dict): Incoming payload data.

    """
    (dry_run, only_unmatched, feed_stable_id, content_type) = get_parameters(payload)
    matches = match_licenses_task(dry_run, only_unmatched, feed_stable_id)
    if content_type not in [CONTENT_TYPE_JSON, CONTENT_TYPE_CSV]:
        logging.error("Unsupported content type: %s", content_type)
        raise ValueError("Unsupported content type: %s", content_type)
    if content_type == CONTENT_TYPE_JSON:
        return matches
    return get_csv_response(matches)


def process_feed(feed, dry_run, db_session):
    """`Process a single feed to match its license."""
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
        }
        if not dry_run:
            feed.license_id = license_first_match.license_id
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
            raise ValueError("Feed with stable_id %s not found.", feed_stable_id)
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
        batch_query = db_session.query(Feed)
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
