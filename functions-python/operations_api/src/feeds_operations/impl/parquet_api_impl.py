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
from typing import Optional

from fastapi import HTTPException
from pydantic import StrictStr
from sqlalchemy.orm import Session

from feeds_gen.apis.parquet_api_base import BaseParquetApi
from feeds_gen.models.parquet_dataset_state import ParquetDatasetState
from feeds_gen.models.parquet_generate_request import ParquetGenerateRequest
from feeds_gen.models.parquet_table import ParquetTable
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsdataset, Gtfsfeed
from shared.helpers.task_execution.task_execution_tracker import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    TaskExecutionTracker,
)
from shared.helpers.utils import create_http_parquet_builder_task

# Must match functions-python/parquet_builder/src/converter.py. Bumping the converter
# invalidates previously written artifacts by moving them to a different run.
TASK_NAME = "parquet_generation"
PARQUET_CONVERTER_VERSION = "1"

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
            feed_stable_id=id, force=_force(parquet_generate_request)
        )

    def generate_gtfs_dataset_parquet(
        self,
        id: StrictStr,
        parquet_generate_request: Optional[ParquetGenerateRequest] = None,
    ) -> ParquetDatasetState:
        return self.handle_generate(
            dataset_stable_id=id, force=_force(parquet_generate_request)
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

        try:
            create_http_parquet_builder_task(
                feed.stable_id, dataset.stable_id, force=force
            )
        except Exception as error:
            logging.error(
                "Failed to enqueue Parquet build for %s: %s", dataset.stable_id, error
            )
            raise HTTPException(
                status_code=500, detail=f"Could not start the conversion: {error}"
            )

        # Record the enqueue so the very next poll reads `preparing` rather than
        # `absent` again. The worker still has to claim the dataset itself before doing
        # anything - `try_acquire` takes over from a merely triggered row - so this is
        # a status marker, not a lock.
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


def _state_of(db_session: Session, feed, dataset) -> ParquetDatasetState:
    """Turn the tracking row into the state a viewer can act on."""
    tracker = TaskExecutionTracker(
        task_name=TASK_NAME,
        run_id=PARQUET_CONVERTER_VERSION,
        db_session=db_session,
    )
    # Read the row rather than `is_triggered`, which counts only triggered and
    # completed - an entity actively in progress reads as untracked through it.
    row = tracker.get_entity(dataset.stable_id)

    base = {
        "feed_stable_id": feed.stable_id,
        "dataset_stable_id": dataset.stable_id,
    }

    if row is None:
        return ParquetDatasetState(status=STATUS_ABSENT, **base)

    metadata = row.metadata_ or {}

    if row.status == STATUS_COMPLETED:
        return ParquetDatasetState(
            status=STATUS_READY,
            base_url=metadata.get("base_url"),
            tables=[
                ParquetTable(
                    name=table.get("name"),
                    rows=table.get("rows"),
                    bytes=table.get("bytes"),
                )
                for table in metadata.get("tables", [])
            ],
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
