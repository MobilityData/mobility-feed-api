#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""Task: task_execution_stats

What a task's attempts actually look like, aggregated from `task_execution_attempt`.

This exists because worker sizing was set twice from a single observed build and was
wrong both times. The numbers that matter are distributions: peak address space per
worker against what that worker allows, how often each one runs out, and whether a run of
feeds is escalating off the same band. One build cannot show any of that.

Read-only, and deliberately a report rather than an autotuner. Memory and volume live in
terraform; this says what they should be, a person decides.

Unlike `get_summary`, which pulls every row for a run into Python and counts there, this
aggregates in the database - the table it reads grows without bound by design.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from shared.database.database import with_db_session

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_DAYS = 30

# Percentiles rather than a mean: durations here are bimodal, a few very long builds
# among many trivial ones, and a mean describes neither.
_BY_VARIANT_SQL = text("""
    SELECT variant,
           count(*)                                              AS attempts,
           count(*) FILTER (WHERE status = 'completed')           AS completed,
           count(*) FILTER (WHERE status = 'failed')              AS failed,
           count(*) FILTER (WHERE escalated_to IS NOT NULL)       AS escalated,
           count(*) FILTER (WHERE variant_basis = 'floor')        AS on_floor,
           max(peak_vms_bytes)                                    AS peak_vms_bytes,
           max(peak_rss_bytes)                                    AS peak_rss_bytes,
           percentile_disc(0.5) WITHIN GROUP (ORDER BY duration_ms)  AS p50_ms,
           percentile_disc(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_ms,
           max(duration_ms)                                       AS max_ms
      FROM task_execution_attempt
     WHERE task_name = :task_name
       AND finished_at >= :since
     GROUP BY variant
     ORDER BY variant
    """)

_BY_FAILURE_SQL = text("""
    SELECT failure_kind, error_type, count(*) AS attempts
      FROM task_execution_attempt
     WHERE task_name = :task_name
       AND finished_at >= :since
       AND status = 'failed'
     GROUP BY failure_kind, error_type
     ORDER BY count(*) DESC
    """)

# Entities that needed more than one go. The retry cap means this is bounded, so a long
# list is a sign the bands are wrong rather than that one feed is unusual.
_REPEAT_OFFENDERS_SQL = text("""
    SELECT entity_id,
           count(*) AS attempts,
           max(escalated_to) AS escalated_to
      FROM task_execution_attempt
     WHERE task_name = :task_name
       AND finished_at >= :since
     GROUP BY entity_id
    HAVING count(*) > 1
     ORDER BY count(*) DESC
     LIMIT :limit
    """)


def task_execution_stats_handler(payload: dict) -> dict:
    """Entry point.

    Payload:
        task_name (str):   required, e.g. "parquet_generation".
        window_days (int): how far back to look. Default 30.
        limit (int):       how many repeat offenders to list. Default 20.
    """
    task_name = payload.get("task_name")
    if not task_name:
        raise ValueError("task_name is required")
    return task_execution_stats(
        task_name=task_name,
        window_days=int(payload.get("window_days", DEFAULT_WINDOW_DAYS)),
        limit=int(payload.get("limit", 20)),
    )


@with_db_session
def task_execution_stats(
    task_name: str,
    window_days: int = DEFAULT_WINDOW_DAYS,
    limit: int = 20,
    db_session: Session | None = None,
) -> dict:
    """Aggregate one task's attempts over a window."""
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    params = {"task_name": task_name, "since": since}

    by_variant = [
        {
            "variant": row.variant,
            "attempts": row.attempts,
            "completed": row.completed,
            "failed": row.failed,
            "escalated": row.escalated,
            "on_floor": row.on_floor,
            "peak_vms_mib": _mib(row.peak_vms_bytes),
            "peak_rss_mib": _mib(row.peak_rss_bytes),
            "p50_ms": row.p50_ms,
            "p95_ms": row.p95_ms,
            "max_ms": row.max_ms,
        }
        for row in db_session.execute(_BY_VARIANT_SQL, params).all()
    ]

    failures = [
        {
            "failure_kind": row.failure_kind,
            "error_type": row.error_type,
            "attempts": row.attempts,
        }
        for row in db_session.execute(_BY_FAILURE_SQL, params).all()
    ]

    repeats = [
        {
            "entity_id": row.entity_id,
            "attempts": row.attempts,
            "escalated_to": row.escalated_to,
        }
        for row in db_session.execute(
            _REPEAT_OFFENDERS_SQL, {**params, "limit": limit}
        ).all()
    ]

    totals = {
        "attempts": sum(v["attempts"] for v in by_variant),
        "completed": sum(v["completed"] for v in by_variant),
        "failed": sum(v["failed"] for v in by_variant),
        "escalated": sum(v["escalated"] for v in by_variant),
    }
    logger.info(
        "%s over %s days: %s attempts, %s failed, %s escalated",
        task_name,
        window_days,
        totals["attempts"],
        totals["failed"],
        totals["escalated"],
    )

    return {
        "task_name": task_name,
        "window_days": window_days,
        "since": since.isoformat(),
        "totals": totals,
        "by_variant": by_variant,
        "failures": failures,
        "repeat_entities": repeats,
    }


def _mib(value) -> float | None:
    """Bytes as MiB, which is the unit the worker limits are expressed in."""
    return round(value / (1024**2), 1) if value else None
