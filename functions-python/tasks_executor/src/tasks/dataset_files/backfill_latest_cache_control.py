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
"""
One-off: set the CDN Cache-Control on every `<feed>/latest.zip` uploaded before the batch
process started setting it.

Without it those objects keep GCS's public default (max-age=3600), so the CDN holds them
for an hour only, and a feed that rarely publishes a new dataset would not get the longer
CDN lifetime for months. The feeds come from the database (those with a latest dataset),
and only the object metadata is patched; no object is listed, read or rewritten. Cached
copies with the old header expire within the hour, so no CDN invalidation is needed.
Re-running is harmless: patching an object that already has the header changes nothing.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsdataset, Gtfsfeed
from shared.helpers.cdn_cache import (
    LATEST_DATASET_CACHE_CONTROL,
    latest_dataset_object_name,
)


def query_latest_feed_stable_ids(
    db_session: Session, uploaded_before: Optional[datetime], limit: Optional[int]
) -> List[str]:
    """Stable ids of the feeds that have a latest dataset, optionally only those whose
    latest dataset was downloaded before `uploaded_before`."""
    query = db_session.query(Gtfsfeed.stable_id).join(
        Gtfsdataset, Gtfsfeed.latest_dataset_id == Gtfsdataset.id
    )
    if uploaded_before is not None:
        query = query.filter(Gtfsdataset.downloaded_at < uploaded_before)
    query = query.order_by(Gtfsfeed.stable_id)
    if limit is not None:
        query = query.limit(limit)
    return [stable_id for (stable_id,) in query.all()]


@with_db_session
def backfill_latest_cache_control_handler(
    payload: Dict[str, Any], db_session: Session
) -> Dict[str, Any]:
    """
    Set Cache-Control on the latest.zip of every feed with a latest dataset.

    Payload keys:
      - dry_run (bool) default True: count the feeds without patching anything
      - uploaded_before (str, ISO 8601) optional: only feeds whose latest dataset was
        downloaded before this time, e.g. the deploy of the batch process that sets the
        header; later uploads already carry it
      - limit (int) default None: maximum number of feeds to process
      - bucket_name (str) optional, defaults to env var DATASETS_BUCKET_NAME
    """
    # Import GCS client at runtime to avoid dev environment import issues
    from google.cloud import storage
    from google.cloud.exceptions import NotFound

    dry_run = payload.get("dry_run", True)
    limit = payload.get("limit")
    limit = int(limit) if limit is not None else None
    uploaded_before = payload.get("uploaded_before")
    uploaded_before = (
        datetime.fromisoformat(uploaded_before) if uploaded_before else None
    )
    bucket_name = payload.get("bucket_name") or os.getenv("DATASETS_BUCKET_NAME")
    if not bucket_name:
        raise ValueError(
            "bucket_name must be provided in payload or set in DATASETS_BUCKET_NAME env"
        )

    stable_ids = query_latest_feed_stable_ids(db_session, uploaded_before, limit)
    logging.info("Found %s feeds with a latest dataset", len(stable_ids))

    updated = 0
    not_found: List[str] = []
    errors: List[str] = []
    if not dry_run:
        bucket = storage.Client().bucket(bucket_name)
        for stable_id in stable_ids:
            blob = bucket.blob(latest_dataset_object_name(stable_id))
            blob.cache_control = LATEST_DATASET_CACHE_CONTROL
            try:
                # Sends only the changed metadata field.
                blob.patch()
            except NotFound:
                not_found.append(stable_id)
                continue
            except Exception as e:
                logging.exception("Error patching %s: %s", blob.name, e)
                errors.append(stable_id)
                continue
            updated += 1
            if updated % 500 == 0:
                logging.info("Updated %s/%s", updated, len(stable_ids))

    summary = {
        "total_feeds": len(stable_ids),
        "updated": updated,
        "not_found": not_found,
        "errors": errors,
        "params": {
            "dry_run": dry_run,
            "uploaded_before": uploaded_before.isoformat() if uploaded_before else None,
            "limit": limit,
            "bucket_name": bucket_name,
        },
    }
    logging.info("backfill_latest_cache_control result: %s", summary)
    return summary
