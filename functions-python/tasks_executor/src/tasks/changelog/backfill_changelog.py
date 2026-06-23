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
"""Backfill GTFS dataset changelog records for the existing dataset history.

The live pipeline (batch_process_dataset -> gtfs-datasets-comparer) only produces
changelog records for *new* datasets going forward. This task walks the already
stored dataset history and, for each consecutive (previous, current) pair that has
no gtfs_dataset_changelog row yet, dispatches a Cloud Task to the same
gtfs-datasets-comparer function that the live pipeline uses.

The task is:
  * idempotent / restartable — pairs that already have a changelog row are skipped,
    and the dispatched Cloud Task itself runs with disallow_overwrite=True.
  * rate-limited — `limit` caps how many feeds are processed per invocation, and the
    dedicated Cloud Tasks queue throttles the actual comparer invocations.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Feed,
    GtfsDatasetChangelog,
    Gtfsdataset,
    Gtfsfeed,
)
from shared.helpers.utils import create_http_gtfs_datasets_comparer_task

# Default number of most recent datasets to consider per feed. With 3 datasets we
# compute 2 diffs: (latest, previous) and (previous, the one before) — matching the
# issue's request to backfill the last three datasets.
DEFAULT_DATASETS_PER_FEED: int = 3
DEFAULT_LIMIT: int = 100


def get_parameters(payload: dict):
    dry_run = payload.get("dry_run", True)
    limit = payload.get("limit", DEFAULT_LIMIT)
    datasets_per_feed = payload.get("datasets_per_feed", DEFAULT_DATASETS_PER_FEED)
    stable_feed_ids = payload.get("stable_feed_ids", None)
    feeds_not_updated_days = payload.get("feeds_not_updated_days", None)
    return dry_run, limit, datasets_per_feed, stable_feed_ids, feeds_not_updated_days


def backfill_changelog_handler(payload: dict) -> dict:
    """
    Handler for backfilling GTFS dataset changelog records from existing datasets.

    Payload parameters:
        dry_run (bool): If True, only enumerate the dataset pairs that would be
                        dispatched — no Cloud Tasks are created. Default: True.
        limit (int | None): Maximum number of feeds processed per invocation.
                            Call repeatedly to walk through every feed. Default: 100.
        datasets_per_feed (int): Number of most recent datasets to consider per feed.
                                 N datasets produce up to N-1 consecutive pairs. Default: 3.
        stable_feed_ids (list[str] | None): If provided, only process these feeds. Default: None.
        feeds_not_updated_days (int | None): If provided, only process feeds whose most recent
                                 dataset was downloaded more than this many days ago. Default: None.
    """
    (
        dry_run,
        limit,
        datasets_per_feed,
        stable_feed_ids,
        feeds_not_updated_days,
    ) = get_parameters(payload)
    return backfill_changelog(
        dry_run=dry_run,
        limit=limit,
        datasets_per_feed=datasets_per_feed,
        stable_feed_ids=stable_feed_ids,
        feeds_not_updated_days=feeds_not_updated_days,
    )


def get_feeds_query(db_session: Session, stable_feed_ids: Optional[list[str]] = None):
    """Return a query for non-deprecated, published GTFS feeds.

    If stable_feed_ids is provided, restrict results to those specific stable IDs.
    """
    query = db_session.query(Gtfsfeed).filter(
        Feed.data_type == "gtfs",
        Feed.status != "deprecated",
        Feed.operational_status == "published",
    )
    if stable_feed_ids is not None:
        query = query.filter(Feed.stable_id.in_(stable_feed_ids))
    return query.order_by(Feed.stable_id)


def get_recent_datasets(
    db_session: Session, feed_id: str, datasets_per_feed: int
) -> list[Gtfsdataset]:
    """Return the `datasets_per_feed` most recent datasets for a feed, oldest first.

    Ordering oldest-first lets us build consecutive (previous, current) pairs directly.
    """
    datasets = (
        db_session.query(Gtfsdataset)
        .filter(
            Gtfsdataset.feed_id == feed_id,
            Gtfsdataset.downloaded_at.isnot(None),
        )
        .order_by(Gtfsdataset.downloaded_at.desc())
        .limit(datasets_per_feed)
        .all()
    )
    return list(reversed(datasets))


def changelog_exists(
    db_session: Session, previous_dataset_id: str, current_dataset_id: str
) -> bool:
    """Authoritative idempotency check against the gtfs_dataset_changelog table."""
    return (
        db_session.query(GtfsDatasetChangelog.id)
        .filter_by(
            previous_dataset_id=previous_dataset_id,
            current_dataset_id=current_dataset_id,
        )
        .first()
        is not None
    )


@with_db_session
def backfill_changelog(
    db_session: Session,
    dry_run: bool = True,
    limit: Optional[int] = DEFAULT_LIMIT,
    datasets_per_feed: int = DEFAULT_DATASETS_PER_FEED,
    stable_feed_ids: Optional[list[str]] = None,
    feeds_not_updated_days: Optional[int] = None,
) -> dict:
    """
    Walk the stored dataset history and dispatch comparer Cloud Tasks for missing pairs.

    For each eligible GTFS feed, take its `datasets_per_feed` most recent datasets,
    form consecutive (previous, current) pairs, and — for each pair without an existing
    changelog row — dispatch a Cloud Task to the gtfs-datasets-comparer function.

    Args:
        db_session: SQLAlchemy session (injected by @with_db_session).
        dry_run: If True, only enumerate pairs; do not dispatch Cloud Tasks.
        limit: Maximum number of feeds processed in this invocation.
        datasets_per_feed: Number of most recent datasets considered per feed.
        stable_feed_ids: If provided, only process feeds with these stable IDs.
        feeds_not_updated_days: If provided, only process feeds whose most recent dataset
                                is older than this many days.

    Returns:
        dict: Summary with feeds processed, pairs found, pairs skipped (already done),
              and pairs dispatched.
    """
    if datasets_per_feed < 2:
        raise ValueError("datasets_per_feed must be >= 2 to form at least one pair.")

    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=feeds_not_updated_days)
        if feeds_not_updated_days is not None
        else None
    )

    query = get_feeds_query(db_session, stable_feed_ids=stable_feed_ids)
    if stable_feed_ids is not None:
        found = {feed.stable_id for feed in query.all()}
        missing = sorted(set(stable_feed_ids) - found)
        if missing:
            raise ValueError(f"stable_feed_ids not found: {missing}")

    if limit is not None:
        query = query.limit(limit)
    feeds = query.all()

    feeds_processed = 0
    feeds_skipped_recent = 0
    pairs_found = 0
    pairs_already_done = 0
    pairs_dispatched = 0
    dispatched: list[dict] = []

    for feed in feeds:
        datasets = get_recent_datasets(db_session, feed.id, datasets_per_feed)
        if len(datasets) < 2:
            continue

        if cutoff is not None and datasets[-1].downloaded_at >= cutoff:
            # Most recent dataset is newer than the cutoff — feed updated recently, skip.
            feeds_skipped_recent += 1
            continue

        feeds_processed += 1

        for previous, current in zip(datasets, datasets[1:]):
            pairs_found += 1
            if changelog_exists(db_session, previous.id, current.id):
                pairs_already_done += 1
                continue
            pairs_dispatched += 1
            dispatched.append(
                {
                    "feed_stable_id": feed.stable_id,
                    "base_dataset_stable_id": previous.stable_id,
                    "new_dataset_stable_id": current.stable_id,
                }
            )
            if not dry_run:
                # ponytail: missing extracted GTFS files on the bucket for old datasets
                # surface as comparer-side errors (logged, HTTP 200), not here. If that
                # becomes common, pre-check the extracted/ prefix before dispatching.
                create_http_gtfs_datasets_comparer_task(
                    feed_stable_id=feed.stable_id,
                    base_dataset_stable_id=previous.stable_id,
                    new_dataset_stable_id=current.stable_id,
                )

    result = {
        "message": (
            f"{'Dry run: ' if dry_run else ''}"
            f"{feeds_processed} feed(s) processed, {pairs_dispatched} pair(s) "
            f"{'to dispatch' if dry_run else 'dispatched'}, "
            f"{pairs_already_done} already done."
        ),
        "dry_run": dry_run,
        "feeds_processed": feeds_processed,
        "feeds_skipped_recent": feeds_skipped_recent,
        "pairs_found": pairs_found,
        "pairs_already_done": pairs_already_done,
        "pairs_dispatched": pairs_dispatched,
    }
    if dry_run:
        result["dispatched"] = dispatched
    logging.info("Task completed: %s", result)
    return result
