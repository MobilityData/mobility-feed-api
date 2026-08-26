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

"""Cloud Tasks producer: fan the nightly Seal of Reliability evaluation out to
per-batch workers (issue #1800).

`update_seal_of_reliability` only evaluates an explicit `stable_feed_ids` list, and one
invocation over the whole catalog would eventually hit `tasks_executor`'s timeout. This
enumerates the catalog and chunks it; the mechanism itself lives in `fanout.plan_fanout`,
shared with the backfill producer (#1763).

Batches, not feeds, are the tracked unit: seal evaluation is pure DB work with no per-feed
side effect requiring isolation, so one Cloud Task per ~250 feeds keeps the daily invocation
count low while removing the single-invocation timeout ceiling.

Payload (all optional)::

    {
        "dry_run": bool,               # default True
        "batch_size": int,             # default 250
        "criteria": [str] | None,      # default None (every implemented criterion)
        "now": str | None,             # ISO timestamp, default current UTC time
        "limit": int | None,           # cap total eligible feeds considered, default None
        "stable_feed_ids": [str] | None,  # restrict eligibility to these ids, default None
        "deadline_seconds": int,       # default 3600 (1h)
        "monitor_delay_seconds": int,  # default 60
    }
"""

import logging
from typing import Any, Dict, List, Optional

from shared.database.database import with_db_session

from tasks.seal_of_reliability.context import (
    count_eligible_feeds,
    iter_eligible_stable_ids,
)
from tasks.seal_of_reliability.fanout import FanoutSpec, plan_fanout

logger = logging.getLogger(__name__)

# TaskExecutionTracker task_name for a seal orchestrator run (fan-out workers + monitor
# all key off this plus a per-run run_id).
SEAL_ORCHESTRATOR_TASK_NAME = "seal_orchestrator_run"

DEFAULT_BATCH_SIZE = 250
DEFAULT_DEADLINE_SECONDS = 60 * 60  # 1h wall-clock cap for a run
DEFAULT_MONITOR_DELAY_SECONDS = 60

SPEC = FanoutSpec(
    task_name=SEAL_ORCHESTRATOR_TASK_NAME,
    worker_task="seal_orchestrator_worker",
    run_id_prefix="seal",
    task_prefix="seal-orchestrator",
    log_name="seal_orchestrator",
)


def seal_orchestrator_handler(payload: dict) -> dict:
    """Entry point for the `seal_orchestrator` task."""
    payload = payload or {}
    return _plan_run(
        dry_run=bool(payload.get("dry_run", True)),
        batch_size=int(payload.get("batch_size", DEFAULT_BATCH_SIZE)),
        criteria=payload.get("criteria"),
        now=payload.get("now"),
        limit=payload.get("limit"),
        stable_feed_ids=payload.get("stable_feed_ids"),
        deadline_seconds=int(payload.get("deadline_seconds", DEFAULT_DEADLINE_SECONDS)),
        monitor_delay_seconds=int(
            payload.get("monitor_delay_seconds", DEFAULT_MONITOR_DELAY_SECONDS)
        ),
    )


@with_db_session
def _plan_run(
    dry_run: bool,
    batch_size: int,
    criteria: Optional[List[str]],
    now: Optional[str],
    limit: Optional[int],
    stable_feed_ids: Optional[List[str]],
    deadline_seconds: int,
    monitor_delay_seconds: int,
    db_session=None,
) -> Dict[str, Any]:
    """Resolve eligible feeds, chunk them, and (unless dry_run) fan the run out."""
    return plan_fanout(
        db_session,
        SPEC,
        count_feeds=lambda session: count_eligible_feeds(
            session, stable_feed_ids=stable_feed_ids, limit=limit
        ),
        iter_batches=lambda session, size: iter_eligible_stable_ids(
            session, size, stable_feed_ids=stable_feed_ids, limit=limit
        ),
        build_worker_payload=lambda run_id, batch_id, ids: {
            "run_id": run_id,
            "batch_id": batch_id,
            "stable_feed_ids": ids,
            "criteria": criteria,
            "now": now,
        },
        run_params=lambda run_started_at: {
            "dry_run": False,
            "batch_size": batch_size,
            "criteria": criteria,
            "now": now,
            "run_started_at": run_started_at,
            "deadline_seconds": deadline_seconds,
        },
        batch_size=batch_size,
        dry_run=dry_run,
        monitor_delay_seconds=monitor_delay_seconds,
    )
