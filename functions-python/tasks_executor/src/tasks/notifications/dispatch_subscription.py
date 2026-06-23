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

"""Cloud Tasks worker: process a single subscription's pending notifications.

One ``notifications_dispatch_subscription`` task is enqueued per subscription by
the ``notifications_dispatch_plan`` producer. The worker claims-then-sends each
pending event (so concurrent workers never duplicate an email — see
``process_subscription``) and reports completion to the shared
``TaskExecutionTracker`` so the monitor knows when the run has drained.

Brevo *send* failures are NOT worker failures: ``process_subscription`` records
them durably in ``notification_log`` and they are retried by later scheduled
runs. The worker only raises (→ HTTP 500 → Cloud Tasks retry) on unexpected
infrastructure errors, so a retry re-claims any stale/unfinished work.

Payload::

    {
        "subscription_id": str,   # required
        "run_id": str,            # required — TaskExecutionTracker run id
        "status_filter": str,     # optional, default "new"
        "since_dt": str | None,   # optional ISO8601 window start
        "until_dt": str | None,   # optional ISO8601 window end
        "max_retries": int,       # optional, default DEFAULT_MAX_RETRIES
        "stale_claim_seconds": int  # optional, default DEFAULT_STALE_CLAIM_SECONDS
    }
"""

import logging
from typing import Optional

from shared.database.database import with_db_session
from shared.helpers.task_execution.task_execution_tracker import TaskExecutionTracker
from tasks.notifications.dispatch_notifications import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_STALE_CLAIM_SECONDS,
    DISPATCH_TASK_NAME,
    process_subscription,
)

logger = logging.getLogger(__name__)


def notifications_dispatch_subscription_handler(payload: dict) -> dict:
    """Entry point for the ``notifications_dispatch_subscription`` task."""
    subscription_id = (payload or {}).get("subscription_id")
    run_id = (payload or {}).get("run_id")
    if not subscription_id:
        raise ValueError("subscription_id is required")

    status_filter = payload.get("status_filter", "new")
    since_dt = payload.get("since_dt")
    until_dt = payload.get("until_dt")
    max_retries = int(payload.get("max_retries", DEFAULT_MAX_RETRIES))
    stale_claim_seconds = int(
        payload.get("stale_claim_seconds", DEFAULT_STALE_CLAIM_SECONDS)
    )

    try:
        stats = process_subscription(
            subscription_id=subscription_id,
            status_filter=status_filter,
            since_dt=since_dt,
            until_dt=until_dt,
            max_retries=max_retries,
            stale_claim_seconds=stale_claim_seconds,
        )
    except Exception as error:  # infra failure — let Cloud Tasks retry
        logger.exception("dispatch_subscription failed for %s", subscription_id)
        _mark_entry(run_id, subscription_id, error=str(error))
        raise

    _mark_entry(run_id, subscription_id)
    return {"status": "ok", "subscription_id": subscription_id, **stats}


@with_db_session
def _mark_entry(
    run_id: Optional[str],
    subscription_id: str,
    error: Optional[str] = None,
    db_session=None,
) -> None:
    """Record this subscription's completion in the run's TaskExecutionTracker.

    No-op when ``run_id`` is absent (e.g. a manual single-subscription trigger).
    """
    if not run_id:
        return
    tracker = TaskExecutionTracker(
        task_name=DISPATCH_TASK_NAME,
        run_id=run_id,
        db_session=db_session,
    )
    if error is None:
        tracker.mark_completed(subscription_id)
    else:
        tracker.mark_failed(subscription_id, error_message=error)
    db_session.commit()
