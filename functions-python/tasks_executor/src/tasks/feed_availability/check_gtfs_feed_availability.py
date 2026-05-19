#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, UTC
from typing import Optional

import requests
from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Feed,
    Gtfsfeed,
    GtfsFeedAvailabilityCheck,
)

DEFAULT_CONCURRENCY: int = 10
DEFAULT_TIMEOUT_SECONDS: int = 20
DEFAULT_BATCH_SIZE: int = 50
REQUEST_TYPE: str = "http_head"


def get_parameters(payload: dict):
    dry_run = payload.get("dry_run", True)
    skip_db_update = payload.get("skip_db_update", False)
    limit = payload.get("limit", None)
    concurrency = payload.get("concurrency", DEFAULT_CONCURRENCY)
    timeout_seconds = payload.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    batch_size = payload.get("batch_size", DEFAULT_BATCH_SIZE)
    feed_ids = payload.get("feed_ids", None)
    return (
        dry_run,
        skip_db_update,
        limit,
        concurrency,
        timeout_seconds,
        batch_size,
        feed_ids,
    )


def check_gtfs_feed_availability_handler(payload: dict) -> dict:
    """
    Handler for checking GTFS feed availability via HTTP HEAD requests.

    Payload parameters:
        dry_run (bool): If True, count matching feeds only — no HTTP calls or DB writes. Default: True.
        skip_db_update (bool): If True, execute HTTP checks but do NOT write results to the DB.
                               Useful for live testing. Default: False.
        limit (int | None): Cap the number of feeds processed. Default: no limit.
        concurrency (int): Number of concurrent HTTP workers. Default: 10.
        timeout_seconds (int): Per-request HTTP timeout in seconds. Default: 20.
        batch_size (int): Number of results committed to DB at a time. Default: 50.
        feed_ids (list[str] | None): If provided, only check these specific feed IDs. Default: None.
    """
    (
        dry_run,
        skip_db_update,
        limit,
        concurrency,
        timeout_seconds,
        batch_size,
        feed_ids,
    ) = get_parameters(payload)
    return check_gtfs_feed_availability(
        dry_run=dry_run,
        skip_db_update=skip_db_update,
        limit=limit,
        concurrency=concurrency,
        timeout_seconds=timeout_seconds,
        batch_size=batch_size,
        feed_ids=feed_ids,
    )


def get_feeds_query(db_session: Session, feed_ids: Optional[list[str]] = None):
    """Return a query for active, published GTFS feeds that have a producer_url.

    If feed_ids is provided, restrict results to those specific feed IDs.
    """
    query = (
        db_session.query(Gtfsfeed)
        .join(Feed, Feed.id == Gtfsfeed.id)
        .filter(
            Feed.data_type == "gtfs",
            Feed.status == "active",
            Feed.operational_status == "published",
            Feed.producer_url.isnot(None),
        )
    )
    if feed_ids is not None:
        query = query.filter(Feed.id.in_(feed_ids))
    return query


def _perform_head_request(
    feed_id: str,
    producer_url: str,
    timeout_seconds: int,
) -> GtfsFeedAvailabilityCheck:
    """Execute an HTTP HEAD request for a single feed and return an unsaved model instance."""
    checked_at = datetime.now(UTC)
    status_code = None
    latency_ms = None
    error_message = None
    error_type = None
    success = False

    try:
        start = time.monotonic()
        response = requests.head(
            producer_url,
            timeout=timeout_seconds,
            allow_redirects=True,
        )
        latency_ms = int((time.monotonic() - start) * 1000)
        status_code = response.status_code
        success = status_code < 400
    except requests.exceptions.Timeout as exc:
        error_type = "Timeout"
        error_message = str(exc)
        logging.warning("Timeout checking feed %s (%s): %s", feed_id, producer_url, exc)
    except requests.exceptions.ConnectionError as exc:
        error_type = "ConnectionError"
        error_message = str(exc)
        logging.warning(
            "Connection error for feed %s (%s): %s", feed_id, producer_url, exc
        )
    except requests.exceptions.RequestException as exc:
        error_type = type(exc).__name__
        error_message = str(exc)
        logging.warning(
            "Request error for feed %s (%s): %s", feed_id, producer_url, exc
        )

    return GtfsFeedAvailabilityCheck(
        feed_id=feed_id,
        checked_at=checked_at,
        request_url=producer_url,
        request_type=REQUEST_TYPE,
        status_code=status_code,
        latency_ms=latency_ms,
        error_message=error_message,
        error_type=error_type,
        success=success,
    )


def _commit_batch(
    db_session: Session,
    batch: list[GtfsFeedAvailabilityCheck],
    batch_num: int,
    skip_db_update: bool,
) -> None:
    succeeded = sum(1 for r in batch if r.success)
    failed = len(batch) - succeeded
    if not skip_db_update:
        db_session.add_all(batch)
        db_session.commit()
        logging.info(
            "Batch %d committed: %d record(s) (%d succeeded, %d failed).",
            batch_num,
            len(batch),
            succeeded,
            failed,
        )
    else:
        logging.info(
            "skip_db_update=True — batch %d: %d record(s) not stored "
            "(%d succeeded, %d failed).",
            batch_num,
            len(batch),
            succeeded,
            failed,
        )


@with_db_session
def check_gtfs_feed_availability(
    db_session: Session,
    dry_run: bool = True,
    skip_db_update: bool = False,
    limit: Optional[int] = None,
    concurrency: int = DEFAULT_CONCURRENCY,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    feed_ids: Optional[list[str]] = None,
) -> dict:
    """
    Check availability of active/published GTFS feeds via HTTP HEAD and store results.

    All feeds are checked concurrently. Results are committed to the DB every
    `batch_size` completions so a failure partway through does not discard
    previously completed checks.

    Args:
        db_session: SQLAlchemy session (injected by @with_db_session).
        dry_run: Count matching feeds only — no HTTP calls or DB writes.
        skip_db_update: Run HTTP checks but skip writing results to the DB.
        limit: Maximum number of feeds to process.
        concurrency: Number of parallel HTTP workers.
        timeout_seconds: Timeout (seconds) per HTTP request.
        batch_size: Number of completed results committed to DB at a time.
        feed_ids: If provided, only check these specific feed IDs.

    Returns:
        dict: Summary with counts of total, successful, and failed checks.
    """
    query = get_feeds_query(db_session, feed_ids=feed_ids)
    if limit is not None:
        query = query.limit(limit)

    if dry_run:
        total = query.count()
        logging.info("Dry run: %d active/published GTFS feeds found.", total)
        return {
            "message": f"Dry run: {total} active/published GTFS feeds found.",
            "total_feeds": total,
        }

    feeds = query.all()
    total = len(feeds)
    logging.info(
        "Checking availability for %d GTFS feed(s) "
        "(concurrency=%d, timeout=%ds, batch_size=%d, skip_db_update=%s).",
        total,
        concurrency,
        timeout_seconds,
        batch_size,
        skip_db_update,
    )

    results: list[GtfsFeedAvailabilityCheck] = []
    batch: list[GtfsFeedAvailabilityCheck] = []
    batch_num = 0

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_to_feed = {
            executor.submit(
                _perform_head_request, feed.id, feed.producer_url, timeout_seconds
            ): feed
            for feed in feeds
        }
        for count, future in enumerate(as_completed(future_to_feed), start=1):
            feed = future_to_feed[future]
            try:
                check = future.result()
            except Exception as exc:
                logging.error(
                    "Unexpected error checking feed %s (%s): %s",
                    feed.id,
                    feed.producer_url,
                    exc,
                )
                check = GtfsFeedAvailabilityCheck(
                    feed_id=feed.id,
                    checked_at=datetime.now(UTC),
                    request_url=feed.producer_url,
                    request_type=REQUEST_TYPE,
                    status_code=None,
                    latency_ms=None,
                    error_message=str(exc),
                    error_type=type(exc).__name__,
                    success=False,
                )
            results.append(check)
            batch.append(check)
            if count % batch_size == 0:
                batch_num += 1
                _commit_batch(db_session, batch, batch_num, skip_db_update)
                batch.clear()

    if batch:
        batch_num += 1
        _commit_batch(db_session, batch, batch_num, skip_db_update)

    total_succeeded = sum(1 for r in results if r.success)
    total_failed = total - total_succeeded

    return {
        "message": f"Checked {total} feed(s): {total_succeeded} succeeded, {total_failed} failed.",
        "total_feeds": total,
        "succeeded": total_succeeded,
        "failed": total_failed,
        "skip_db_update": skip_db_update,
    }
