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
"""Reporting and starting the Parquet rendering of a GTFS dataset.

The shape of the responses here is not free: a browser viewer polls the GET roughly
twice a second and renders every state itself, so the fields are named as it names its
own load reports and `absent` is an ordinary answer rather than a 404. A 404 means the
feed or dataset does not exist, which is a different thing entirely and the interface
has to be able to tell them apart.

The GET never starts work. Starting is the POST, which a client calls once.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from pydantic import StrictStr
from sqlalchemy.orm import Session

from feeds_gen.apis.parquet_api_base import BaseParquetApi
from feeds_gen.models.parquet_dataset_state import ParquetDatasetState
from feeds_gen.models.parquet_generate_request import ParquetGenerateRequest
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsdataset, Gtfsfeed
from shared.helpers.parquet_policy import (
    COMPRESSION_RATIO,
    SIZE_CONFIG_KEY,
    SIZE_CONFIG_NAMESPACE,
    SIZE_TIERS,
)
from shared.helpers.sizing import Basis, Routing, size_for_dataset
from shared.helpers.task_execution.task_execution_tracker import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    TaskExecutionTracker,
)
from shared.helpers.utils import create_http_parquet_builder_task

# Must match functions-python/parquet_builder/src/converter.py. Bumping the converter
# invalidates previously written artifacts by moving them to a different run.
TASK_NAME = "parquet_generation"
PARQUET_CONVERTER_VERSION = "2"

STATUS_ABSENT = "absent"
STATUS_PREPARING = "preparing"
STATUS_READY = "ready"
STATUS_FAILED_STATE = "failed"


class ParquetApiImpl(BaseParquetApi):
    """Implementation of the Parquet API."""

    # ------------------------------------------------------------------
    # Generated entry points
    # ------------------------------------------------------------------

    def get_gtfs_feed_parquet(self, id: StrictStr) -> ParquetDatasetState:
        return self.handle_status(feed_stable_id=id)

    def get_gtfs_dataset_parquet(self, id: StrictStr) -> ParquetDatasetState:
        return self.handle_status(dataset_stable_id=id)

    def generate_gtfs_feed_parquet(
        self,
        id: StrictStr,
        parquet_generate_request: Optional[ParquetGenerateRequest] = None,
    ) -> ParquetDatasetState:
        return self.handle_generate(
            feed_stable_id=id,
            force=_force(parquet_generate_request),
            retention_days=_retention_days(parquet_generate_request),
        )

    def generate_gtfs_dataset_parquet(
        self,
        id: StrictStr,
        parquet_generate_request: Optional[ParquetGenerateRequest] = None,
    ) -> ParquetDatasetState:
        return self.handle_generate(
            dataset_stable_id=id,
            force=_force(parquet_generate_request),
            retention_days=_retention_days(parquet_generate_request),
        )

    # ------------------------------------------------------------------
    # Behaviour
    # ------------------------------------------------------------------

    @with_db_session
    def handle_status(
        self,
        feed_stable_id: Optional[str] = None,
        dataset_stable_id: Optional[str] = None,
        db_session: Session = None,
    ) -> ParquetDatasetState:
        feed, dataset = _resolve(db_session, feed_stable_id, dataset_stable_id)
        return _state_of(db_session, feed, dataset)

    @with_db_session
    def handle_generate(
        self,
        feed_stable_id: Optional[str] = None,
        dataset_stable_id: Optional[str] = None,
        force: bool = False,
        retention_days: Optional[int] = None,
        db_session: Session = None,
    ) -> ParquetDatasetState:
        feed, dataset = _resolve(db_session, feed_stable_id, dataset_stable_id)
        state = _state_of(db_session, feed, dataset)

        # A build already under way is reported, not duplicated - the viewer calls this
        # once on first `absent`, but nothing stops two operators clicking at once, and
        # `force` must not be able to interrupt work in flight either.
        if state.status == STATUS_PREPARING:
            logging.info(
                "Parquet build already in progress for %s; not enqueuing another",
                dataset.stable_id,
            )
            return state

        if state.status == STATUS_READY and not force:
            return state

        # Written before the dispatch, so the next poll reads `preparing` rather than
        # `absent`. It has to come first: `mark_triggered` is an unconditional upsert,
        # and Cloud Tasks can deliver before this request finishes, so writing it
        # afterwards could push a row the worker already moved to `in_progress` back to
        # the claimable `triggered`. A status marker, not a lock - the worker still
        # claims the dataset through `try_acquire`.
        tracker = TaskExecutionTracker(
            task_name=TASK_NAME,
            run_id=PARQUET_CONVERTER_VERSION,
            db_session=db_session,
        )
        tracker.start_run(params={"converter_version": PARQUET_CONVERTER_VERSION})
        tracker.mark_triggered(
            dataset.stable_id,
            metadata={"phase": "start", "done": 0, "total": 0, "detail": ""},
        )
        db_session.commit()

        try:
            create_http_parquet_builder_task(
                feed.stable_id,
                dataset.stable_id,
                force=force,
                retention_days=retention_days,
                **_enqueue_sizing(db_session, feed, dataset),
            )
        except Exception as error:
            logging.error(
                "Failed to enqueue Parquet build for %s: %s", dataset.stable_id, error
            )
            # The marker describes work that will never arrive. Left as `triggered` it
            # reports `preparing`, the one state this endpoint refuses to re-trigger.
            try:
                tracker.mark_failed(
                    dataset.stable_id,
                    error_message=f"Could not start the conversion: {error}",
                )
                db_session.commit()
            except Exception:
                logging.exception(
                    "Could not clear the trigger marker for %s", dataset.stable_id
                )
                db_session.rollback()
            raise HTTPException(
                status_code=500, detail=f"Could not start the conversion: {error}"
            )

        return ParquetDatasetState(
            status=STATUS_PREPARING,
            feed_stable_id=feed.stable_id,
            dataset_stable_id=dataset.stable_id,
            phase="start",
            done=0,
            total=0,
            detail="",
        )


def _force(request: Optional[ParquetGenerateRequest]) -> bool:
    return bool(request.force) if request and request.force is not None else False


def _retention_days(request: Optional[ParquetGenerateRequest]) -> Optional[int]:
    """None when the caller did not ask for one.

    Passed through rather than defaulted here: the schema declares the bounds but no
    default, so the builder stays the single place that decides how long a set lives.
    """
    return request.retention_days if request else None


def _resolve(
    db_session: Session,
    feed_stable_id: Optional[str],
    dataset_stable_id: Optional[str],
):
    """Find the feed and dataset a request addresses, or 404.

    A feed resolves to its latest dataset, so a caller holding only a feed id never has
    to know about datasets.
    """
    if dataset_stable_id:
        dataset = (
            db_session.query(Gtfsdataset)
            .filter(Gtfsdataset.stable_id == dataset_stable_id)
            .one_or_none()
        )
        if dataset is None:
            raise HTTPException(status_code=404, detail="GTFS dataset not found")
        return dataset.feed, dataset

    feed = (
        db_session.query(Gtfsfeed)
        .filter(Gtfsfeed.stable_id == feed_stable_id)
        .one_or_none()
    )
    if feed is None:
        raise HTTPException(status_code=404, detail="GTFS feed not found")
    if feed.latest_dataset is None:
        raise HTTPException(status_code=404, detail="GTFS feed has no dataset yet")
    return feed, feed.latest_dataset


def _enqueue_sizing(db_session: Session, feed, dataset) -> dict:
    """The sizing arguments for the enqueue, flattened."""
    routing = _size_for(db_session, feed, dataset)
    return {
        "size": routing.size,
        "variant_basis": routing.basis.value,
        "override": routing.size.value if routing.basis is not Basis.MEASURED else None,
    }


def _size_for(db_session: Session, feed, dataset) -> Routing:
    """Which worker should build this dataset, and why.

    A thin wrapper over the shared helper: everything here is the Parquet builder's own
    policy - its bands, its config namespace - and none of the mechanism.
    """
    return size_for_dataset(
        db_session,
        feed,
        dataset,
        tiers=SIZE_TIERS,
        namespace=SIZE_CONFIG_NAMESPACE,
        key=SIZE_CONFIG_KEY,
        compression_ratio=COMPRESSION_RATIO,
    )


def _is_expired(metadata: dict) -> bool:
    """True once the set has passed the expiry its build recorded.

    The objects are deleted by the bucket's lifecycle rule, on GCS's own schedule and
    with no promptness guarantee, so the row cannot be trusted to disappear with them.
    Reading the expiry here is what makes the dataset report `absent` on the date and
    rebuild on the next request. Rows written without an expiry never expire.
    """
    raw = metadata.get("expires_at")
    if not raw:
        return False
    try:
        expires_at = datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        logging.warning("Ignoring unparsable expires_at %r", raw)
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)


def _state_of(db_session: Session, feed, dataset) -> ParquetDatasetState:
    """Turn the tracking row into the state a viewer can act on."""
    tracker = TaskExecutionTracker(
        task_name=TASK_NAME,
        run_id=PARQUET_CONVERTER_VERSION,
        db_session=db_session,
    )
    # The row itself, not `is_handled`: that reduces it to a yes/no for dispatch, and
    # this has to tell `preparing` from `ready` and `failed`.
    row = tracker.get_entity(dataset.stable_id)

    base = {
        "feed_stable_id": feed.stable_id,
        "dataset_stable_id": dataset.stable_id,
    }

    if row is None:
        return ParquetDatasetState(status=STATUS_ABSENT, **base)

    metadata = row.metadata_ or {}

    if row.status == STATUS_COMPLETED:
        if _is_expired(metadata):
            # The files are gone, or about to be. `absent` is also what lets the next
            # request rebuild: `handle_generate` re-triggers it, which `try_acquire`
            # accepts, where a `completed` row would have been refused.
            return ParquetDatasetState(status=STATUS_ABSENT, **base)
        # No table list: a reader handed one skips `manifest.json`, and the manifest
        # is where the sizes and counts live. The builder still records the tables in
        # the tracking row for diagnostics; they are simply not served.
        return ParquetDatasetState(
            status=STATUS_READY,
            base_url=metadata.get("base_url"),
            generated_at=row.completed_at,
            **base,
        )

    if row.status == STATUS_FAILED:
        return ParquetDatasetState(
            status=STATUS_FAILED_STATE,
            message=row.error_message or "The conversion failed.",
            **base,
        )

    return ParquetDatasetState(
        status=STATUS_PREPARING,
        phase=metadata.get("phase", "start"),
        done=metadata.get("done", 0),
        total=metadata.get("total", 0),
        detail=metadata.get("detail", ""),
        **base,
    )
