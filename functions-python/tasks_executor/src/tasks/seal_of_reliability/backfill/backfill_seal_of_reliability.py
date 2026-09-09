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
"""Task entry point for the Seal of Reliability backfill (issue #1763)."""

from datetime import date, datetime
from typing import Optional

from tasks.seal_of_reliability.backfill.seal_backfill import (
    DEFAULT_DAYS_BACK,
    DEFAULT_SNAPSHOT_MODE,
    backfill_seals,
)
from tasks.seal_of_reliability.seal_updater import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_MAX_REPORTED_FEEDS,
)


def _parse_day(value: Optional[str], field: str) -> Optional[date]:
    """Parse a payload date string to a `date`, or None when absent.

    Accepts a full timestamp too — an operator pasting the nightly task's `now` should not
    hit a parse error. The march is day-granular, so the time is dropped either way.
    """
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        raise ValueError(
            f"{field} must be an ISO date such as 2026-01-31, got {value!r}"
        )


def get_parameters(payload: dict):
    """Read the task parameters from the payload, applying defaults."""
    payload = payload or {}
    return (
        payload.get("stable_feed_ids"),
        _parse_day(payload.get("start_date"), "start_date"),
        _parse_day(payload.get("end_date"), "end_date"),
        payload.get("days_back", DEFAULT_DAYS_BACK),
        payload.get("dry_run", True),
        payload.get("limit", None),
        payload.get("criteria", None),
        payload.get("batch_size", DEFAULT_BATCH_SIZE),
        payload.get("only_missing", True),
        payload.get("snapshot_mode", DEFAULT_SNAPSHOT_MODE),
        payload.get("resume_from_snapshot", False),
        payload.get("max_reported_feeds", DEFAULT_MAX_REPORTED_FEEDS),
        payload.get("simulate", None),
        payload.get("trace", False),
        payload.get("collapse_trace", True),
    )


def backfill_seal_of_reliability_handler(payload: dict) -> dict:
    """Handler for the Seal of Reliability backfill. A dry run returns the plan only.

    Payload, all optional but `stable_feed_ids`:
        stable_feed_ids  required, non-empty; there is no run-the-whole-catalogue mode
        start_date       ISO date, clamped up to each feed's created_at. Default: end_date
                         minus days_back
        end_date         ISO date, last day marched. Default: yesterday UTC
        days_back        window length when start_date is absent. Default: 365
        dry_run          Default: True
        limit            cap the number of feeds. Default: no limit
        criteria         restrict to these criteria. Default: every implemented one
        batch_size       Default: 200
        only_missing     skip feeds already holding every criterion of the run, which is
                         also how an interrupted run resumes. Default: True
        snapshot_mode    final | all | none. Default: final
        resume_from_snapshot  seed from the snapshot before march_start (#1803).
                         Default: False
        max_reported_feeds    cap on the `feeds` list in the response. Default: 50
        simulate         force statuses per criterion, on days counted from each feed's
                         march start: {"fresh_coverage": {"default": "pass", "fail": [3]}}.
                         see `parse_simulation` for the full shape. Requires dry_run: a
                         forced verdict must never reach the seal tables
        trace            return the march day by day: every seal_criterion field, plus where
                         it came from. Marches without writing when dry_run
        collapse_trace   fold consecutive unchanged days into one entry — its first day, its
                         last, and the count between. Default: True; pass false for every
                         day, which is what the snapshots would hold
    """
    (
        stable_feed_ids,
        start_date,
        end_date,
        days_back,
        dry_run,
        limit,
        criteria,
        batch_size,
        only_missing,
        snapshot_mode,
        resume_from_snapshot,
        max_reported_feeds,
        simulate,
        trace,
        collapse_trace,
    ) = get_parameters(payload)
    return backfill_seals(
        stable_feed_ids=stable_feed_ids,
        start_date=start_date,
        end_date=end_date,
        days_back=days_back,
        dry_run=dry_run,
        limit=limit,
        criteria=criteria,
        batch_size=batch_size,
        only_missing=only_missing,
        snapshot_mode=snapshot_mode,
        resume_from_snapshot=resume_from_snapshot,
        max_reported_feeds=max_reported_feeds,
        simulate=simulate,
        trace=trace,
        collapse_trace=collapse_trace,
    )
