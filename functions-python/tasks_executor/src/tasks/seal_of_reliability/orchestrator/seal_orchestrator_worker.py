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

"""Cloud Tasks worker: evaluate one batch of the seal orchestrator run (issue #1800).

One `seal_orchestrator_worker` task is enqueued per batch by the `seal_orchestrator`
producer. The worker calls `update_seals` for its slice of stable_ids and reports the
outcome to the shared `TaskExecutionTracker` so the monitor knows when the run has
drained. `update_seals` writes via upsert, so a Cloud Tasks redelivery of the same
batch (e.g. a timeout on the response after the write already committed) is safe to
reprocess.

Payload::

    {
        "run_id": str,             # required — TaskExecutionTracker run id
        "batch_id": str,           # required — e.g. "batch-0003"
        "stable_feed_ids": [str],  # required, non-empty
        "criteria": [str] | None,  # optional, default None (every implemented criterion)
        "now": str | None          # optional ISO timestamp, default current UTC time
    }
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from shared.database.database import with_db_session
from shared.helpers.task_execution.task_execution_tracker import TaskExecutionTracker

from tasks.seal_of_reliability.orchestrator.seal_orchestrator import (
    SEAL_ORCHESTRATOR_TASK_NAME,
)
from tasks.seal_of_reliability.seal_updater import update_seals

logger = logging.getLogger(__name__)


def _parse_now(now: str) -> datetime:
    """Parse an ISO timestamp to UTC-aware, defaulting to UTC when no offset is given."""
    parsed = datetime.fromisoformat(now)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def seal_orchestrator_worker_handler(payload: dict) -> dict:
    """Entry point for the `seal_orchestrator_worker` task."""
    payload = payload or {}
    run_id = payload.get("run_id")
    batch_id = payload.get("batch_id")
    stable_feed_ids = payload.get("stable_feed_ids")
    if not run_id or not batch_id:
        raise ValueError("run_id and batch_id are required")
    if not stable_feed_ids:
        raise ValueError("stable_feed_ids is required and must be non-empty")

    criteria = payload.get("criteria")
    now = payload.get("now")

    try:
        result = update_seals(
            stable_feed_ids=stable_feed_ids,
            dry_run=False,
            criteria=criteria,
            now=_parse_now(now) if now else None,
        )
    except Exception as error:  # infra failure or the rare all-ineligible edge case
        logger.exception(
            "seal_orchestrator_worker failed for run=%s batch=%s", run_id, batch_id
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
    """Record this batch's completion in the run's TaskExecutionTracker."""
    tracker = TaskExecutionTracker(
        task_name=SEAL_ORCHESTRATOR_TASK_NAME,
        run_id=run_id,
        db_session=db_session,
    )
    if error is None:
        tracker.mark_completed(batch_id, metadata=result)
    else:
        tracker.mark_failed(batch_id, error_message=error)
    db_session.commit()
