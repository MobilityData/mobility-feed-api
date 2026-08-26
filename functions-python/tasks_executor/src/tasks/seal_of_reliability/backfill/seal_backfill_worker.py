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
"""Cloud Tasks worker: march one batch of the Seal of Reliability backfill (#1763).

One `seal_backfill_worker` task is enqueued per batch by `seal_backfill_orchestrator`. It
calls `backfill_seals` for its slice of stable_ids and reports the outcome to the shared
`TaskExecutionTracker` so the monitor knows when the run has drained.

`backfill_seals` writes via upsert, so a Cloud Tasks redelivery of the same batch — a
timeout on the response after the write already committed, say — is safe to reprocess: the
same window over the same source data produces the same final state. `created_at` on
`feed_reliability_seal` is insert-only, so even a redelivery cannot move a feed's tracking
start.

`start_date` and `end_date` both arrive explicit. A worker never defaults them: the run's
window belongs to the run, not to the moment a particular batch happened to execute.

Payload::

    {
        "run_id": str,                 # required — TaskExecutionTracker run id
        "batch_id": str,               # required — e.g. "batch-0003"
        "stable_feed_ids": [str],      # required, non-empty
        "start_date": str,             # required, ISO date
        "end_date": str,               # required, ISO date
        "criteria": [str] | None,      # optional
        "only_missing": bool,          # optional, default True
        "snapshot_mode": str,          # optional, default final
        "resume_from_snapshot": bool   # optional, default False
    }
"""

import logging
from typing import Optional

from shared.database.database import with_db_session
from shared.helpers.task_execution.task_execution_tracker import TaskExecutionTracker

from tasks.seal_of_reliability.backfill.backfill_seal_of_reliability import _parse_day
from tasks.seal_of_reliability.backfill.seal_backfill import (
    DEFAULT_SNAPSHOT_MODE,
    backfill_seals,
)
from tasks.seal_of_reliability.backfill.seal_backfill_orchestrator import (
    SEAL_BACKFILL_TASK_NAME,
)

logger = logging.getLogger(__name__)


def seal_backfill_worker_handler(payload: dict) -> dict:
    """Entry point for the `seal_backfill_worker` task."""
    payload = payload or {}
    run_id = payload.get("run_id")
    batch_id = payload.get("batch_id")
    stable_feed_ids = payload.get("stable_feed_ids")
    if not run_id or not batch_id:
        raise ValueError("run_id and batch_id are required")
    if not stable_feed_ids:
        raise ValueError("stable_feed_ids is required and must be non-empty")

    start_date = _parse_day(payload.get("start_date"), "start_date")
    end_date = _parse_day(payload.get("end_date"), "end_date")
    if start_date is None or end_date is None:
        # The producer resolves the window for the whole run. A worker that defaulted it
        # could march to a different final day than its siblings.
        raise ValueError("start_date and end_date are required")

    try:
        result = backfill_seals(
            stable_feed_ids=stable_feed_ids,
            start_date=start_date,
            end_date=end_date,
            dry_run=False,
            criteria=payload.get("criteria"),
            only_missing=bool(payload.get("only_missing", True)),
            snapshot_mode=payload.get("snapshot_mode", DEFAULT_SNAPSHOT_MODE),
            resume_from_snapshot=bool(payload.get("resume_from_snapshot", False)),
        )
    except (
        Exception
    ) as error:  # infra failure, or every id in the batch turned ineligible
        logger.exception(
            "seal_backfill_worker failed for run=%s batch=%s", run_id, batch_id
        )
        _mark_entry(run_id, batch_id, error=str(error))
        raise

    _mark_entry(run_id, batch_id, result=result)
    return {"status": "ok", "batch_id": batch_id, **result}


@with_db_session
def _mark_entry(
    run_id: str,
    batch_id: str,
    result: Optional[dict] = None,
    error: Optional[str] = None,
    db_session=None,
) -> None:
    """Record this batch's completion in the run's TaskExecutionTracker.

    The stored metadata is what `seal_orchestrator_monitor` aggregates into the run-level
    report, so the keys it reads — total_feeds, criterion_rows_written, seals_granted /
    seals_revoked and their stable_id lists — must survive here.
    """
    tracker = TaskExecutionTracker(
        task_name=SEAL_BACKFILL_TASK_NAME,
        run_id=run_id,
        db_session=db_session,
    )
    if error is None:
        tracker.mark_completed(batch_id, metadata=result)
    else:
        tracker.mark_failed(batch_id, error_message=error)
    db_session.commit()
