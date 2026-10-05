#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""Deletes generated Parquet sets past the retention their build was given.

Each build records how long its output should live, and the clock runs from when it was
built rather than from when it was last read - a dataset nobody wants is not kept alive
by a passing visit, and one that is still wanted rebuilds on the next request in
seconds.

The objects and the tracking row must go together, and that is the whole difficulty
here. The API decides a dataset is `ready` purely from the row, so removing the files
while leaving it behind would leave the endpoint advertising a `base_url` whose contents
have been deleted - the same failure the publish path was fixed for. Deleting the row is
also what makes the dataset report `absent`, which is what lets it be rebuilt.
"""

from __future__ import annotations

import logging
import os

from sqlalchemy import text
from sqlalchemy.orm import Session

from shared.database.database import with_db_session

logger = logging.getLogger(__name__)

TASK_NAME = "parquet_generation"
PARQUET_PREFIX = "parquet"
DEFAULT_RETENTION_DAYS = 30

# The cutoff is per row: each build stored the retention it was asked for, so a set
# built with `retention_days: 7` expires long before one left on the default. Rows
# written before the field existed fall back to the default rather than living forever.
_EXPIRED_SQL = text("""
    SELECT entity_id,
           completed_at,
           COALESCE((metadata ->> 'retention_days')::int, :default_days) AS retention_days
      FROM task_execution_log
     WHERE task_name = :task_name
       AND status = 'completed'
       AND completed_at
           < now() - make_interval(days => COALESCE(
                 (metadata ->> 'retention_days')::int, :default_days))
     ORDER BY completed_at
    """)

_DELETE_ROW_SQL = text("""
    DELETE FROM task_execution_log
     WHERE task_name = :task_name
       AND entity_id = :entity_id
       AND status = 'completed'
    """)


def purge_expired_parquet_handler(payload: dict) -> dict:
    """Entry point for the purge_expired_parquet task.

    Payload:
        dry_run (bool):  report what would be deleted without deleting. Default True.
        limit (int):     stop after this many datasets. Default None (no limit).
    """
    return purge_expired_parquet(
        dry_run=payload.get("dry_run", True),
        limit=payload.get("limit"),
    )


@with_db_session
def purge_expired_parquet(
    dry_run: bool = True,
    limit: int | None = None,
    db_session: Session | None = None,
) -> dict:
    """Delete expired Parquet sets and the rows that advertise them."""
    bucket_name = os.getenv("DATASETS_BUCKET_NAME")
    if not bucket_name:
        raise ValueError("DATASETS_BUCKET_NAME is not set")

    expired = db_session.execute(
        _EXPIRED_SQL,
        {"task_name": TASK_NAME, "default_days": DEFAULT_RETENTION_DAYS},
    ).all()
    if limit:
        expired = expired[:limit]

    datasets = [row.entity_id for row in expired]
    logger.info("Found %s expired Parquet sets", len(datasets))

    if dry_run:
        return {
            "message": "Dry run: nothing deleted.",
            "total_expired": len(datasets),
            "datasets": datasets,
            "params": {"dry_run": True, "limit": limit},
        }

    from google.cloud import storage

    bucket = storage.Client().get_bucket(bucket_name)
    deleted_objects = 0
    purged = []
    for dataset_stable_id in datasets:
        try:
            deleted_objects += _delete_prefix(bucket, dataset_stable_id)
            db_session.execute(
                _DELETE_ROW_SQL,
                {"task_name": TASK_NAME, "entity_id": dataset_stable_id},
            )
            # Committed per dataset: a failure part way through leaves the datasets
            # already handled consistent, rather than rolling back row deletions whose
            # objects are already gone.
            db_session.commit()
            purged.append(dataset_stable_id)
        except Exception as error:
            db_session.rollback()
            logger.error("Could not purge %s: %s", dataset_stable_id, error)

    logger.info("Purged %s datasets, %s objects", len(purged), deleted_objects)
    return {
        "message": "Expired Parquet sets purged.",
        "total_expired": len(datasets),
        "total_purged": len(purged),
        "total_objects_deleted": deleted_objects,
        "datasets": purged,
        "params": {"dry_run": False, "limit": limit},
    }


def _delete_prefix(bucket, dataset_stable_id: str) -> int:
    """Remove a dataset's Parquet objects.

    The feed id is the dataset id minus its trailing timestamp, which is how every
    other path in the pipeline addresses this prefix.
    """
    feed_stable_id = dataset_stable_id.rsplit("-", 1)[0]
    prefix = f"{feed_stable_id}/{dataset_stable_id}/{PARQUET_PREFIX}/"
    count = 0
    for blob in bucket.list_blobs(prefix=prefix):
        blob.delete()
        count += 1
    return count
