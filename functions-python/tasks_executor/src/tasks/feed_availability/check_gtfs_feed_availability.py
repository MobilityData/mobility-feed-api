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
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Feed,
    Gtfsfeed,
    GtfsFeedAvailabilityCheck,
)
from shared.helpers.utils import perform_request

DEFAULT_CONCURRENCY: int = 15
DEFAULT_TIMEOUT_SECONDS: int = 20
DEFAULT_BATCH_SIZE: int = 50
DEFAULT_FALLBACK_TO_GET: bool = True


def get_feed_credentials(stable_id: str) -> Optional[str]:
    """Return the API credential for a feed from the FEEDS_CREDENTIALS env var, or None."""
    try:
        import json

        feeds_credentials = json.loads(os.getenv("FEEDS_CREDENTIALS", "{}"))
        return feeds_credentials.get(stable_id, None)
    except Exception as exc:
        logging.warning("Could not parse FEEDS_CREDENTIALS: %s", exc)
        return None


def get_parameters(payload: dict):
    dry_run = payload.get("dry_run", True)
    skip_db_update = payload.get("skip_db_update", False)
    limit = payload.get("limit", None)
    concurrency = payload.get("concurrency", DEFAULT_CONCURRENCY)
    timeout_seconds = payload.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    batch_size = payload.get("batch_size", DEFAULT_BATCH_SIZE)
    feed_ids = payload.get("feed_ids", None)
    verbose = payload.get("verbose", False)
    fallback_to_get = payload.get("fallback_to_get", DEFAULT_FALLBACK_TO_GET)
    return (
        dry_run,
        skip_db_update,
        limit,
        concurrency,
        timeout_seconds,
        batch_size,
        feed_ids,
        verbose,
        fallback_to_get,
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
        verbose (bool): If True, include a 'failures' list in the response with stable_id and
                        reason for each failed check. Default: False.
        fallback_to_get (bool): If True, retry failed HEAD requests with a lightweight GET
                                (reads only 4 bytes to verify ZIP magic bytes). Default: True.
    """
    (
        dry_run,
        skip_db_update,
        limit,
        concurrency,
        timeout_seconds,
        batch_size,
        feed_ids,
        verbose,
        fallback_to_get,
    ) = get_parameters(payload)
    return check_gtfs_feed_availability(
        dry_run=dry_run,
        skip_db_update=skip_db_update,
        limit=limit,
        concurrency=concurrency,
        timeout_seconds=timeout_seconds,
        batch_size=batch_size,
        feed_ids=feed_ids,
        verbose=verbose,
        fallback_to_get=fallback_to_get,
    )


def get_feeds_query(db_session: Session, feed_ids: Optional[list[str]] = None):
    """Return a query for non-deprecated, published GTFS feeds that have a producer_url.

    If feed_ids is provided, restrict results to those specific feed IDs.
    """
    query = db_session.query(Gtfsfeed).filter(
        Feed.data_type == "gtfs",
        Feed.status != "deprecated",
        Feed.operational_status == "published",
        Feed.producer_url.isnot(None),
    )
    if feed_ids is not None:
        query = query.filter(Feed.id.in_(feed_ids))
    return query


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
        for check in batch:
            logging.info(
                "skip_db_update check — feed_id=%s url=%s success=%s "
                "status_code=%s latency_ms=%s error_type=%s error_message=%s",
                check.feed_id,
                check.request_url,
                check.success,
                check.status_code,
                check.latency_ms,
                check.error_type,
                check.error_message,
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
    verbose: bool = False,
    fallback_to_get: bool = DEFAULT_FALLBACK_TO_GET,
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
        verbose: If True, include a 'failures' list in the response with stable_id,
                 reason, content_type, and is_zip for each failed check.
        fallback_to_get: If True, retry failed HEAD requests with a lightweight GET
                         (reads only 4 bytes to verify ZIP magic bytes).

    Returns:
        dict: Summary with counts of total, successful, and failed checks.
              When verbose=True, also includes a 'failures' list.
    """
    query = get_feeds_query(db_session, feed_ids=feed_ids)
    if limit is not None:
        query = query.limit(limit)

    if dry_run:
        start_time = time.monotonic()
        total = query.count()
        elapsed = round(time.monotonic() - start_time, 2)
        logging.info("Dry run: %d active/published GTFS feeds found.", total)
        result = {
            "message": f"Dry run: {total} active/published GTFS feeds found.",
            "total_feeds": total,
            "elapsed_seconds": elapsed,
        }
        logging.info("Task completed: %s", result)
        return result

    feeds = query.all()
    total = len(feeds)
    stable_id_map = {feed.id: feed.stable_id for feed in feeds}
    start_time = time.monotonic()
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
                perform_request,
                feed.id,
                feed.stable_id,
                feed.producer_url,
                feed.authentication_type or "0",
                feed.api_key_parameter_name,
                get_feed_credentials(feed.stable_id),
                timeout_seconds,
                fallback_to_get,
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
                    feed.stable_id,
                    feed.producer_url,
                    exc,
                )
                check = GtfsFeedAvailabilityCheck(
                    feed_id=feed.id,
                    checked_at=datetime.now(timezone.utc),
                    request_url=feed.producer_url,
                    request_type="http_head",
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
    elapsed = round(time.monotonic() - start_time, 2)

    result = {
        "message": f"Checked {total} feed(s): {total_succeeded} succeeded, {total_failed} failed.",
        "total_feeds": total,
        "succeeded": total_succeeded,
        "failed": total_failed,
        "skip_db_update": skip_db_update,
        "elapsed_seconds": elapsed,
    }
    if verbose:
        result["failures"] = [
            {
                "stable_id": stable_id_map.get(r.feed_id, r.feed_id),
                "error_type": r.error_type,
                "reason": (
                    r.error_message if r.error_message else f"HTTP {r.status_code}"
                ),
                "content_type": r.content_type,
                "is_zip": r.is_zip,
            }
            for r in results
            if not r.success
        ]
    logging.info("Task completed: %s", result)
    return result
