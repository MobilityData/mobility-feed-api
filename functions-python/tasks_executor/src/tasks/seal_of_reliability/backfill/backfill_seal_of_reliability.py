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
    """Parse a payload date string to a `date`, or None when it is absent.

    A plain date is what the window is expressed in, but an operator copying a value from a
    log or from the nightly task's `now` will paste a full timestamp. Accept both rather than
    failing on a value whose meaning is unambiguous; the time of day is dropped either way,
    since the march is day-granular.
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
    )


def backfill_seal_of_reliability_handler(payload: dict) -> dict:
    """
    Handler for the Seal of Reliability backfill.

    The day march is not implemented yet: a dry run returns the resolved plan, and a non-dry
    run raises rather than reporting a success that wrote nothing.

    Payload parameters:
        stable_feed_ids (list[str]): Required and non-empty. The feeds to backfill; there is
                        no run-the-whole-catalogue mode. Ineligible ids are skipped with a
                        logged warning, and it raises if none can be used.
        start_date (str | None): First day of the window, ISO date. Clamped up to each feed's
                        own created_at. Default: end_date minus days_back.
        end_date (str | None): Last day simulated, and the day the written state belongs to.
                        Resolved once for the whole run. Default: yesterday UTC.
        days_back (int): Window length used when start_date is absent. Default: 365 — the
                        "12 months" of #1763, a cost/coverage default rather than a
                        correctness threshold.
        dry_run (bool): Resolve and return the plan without marching or writing.
                        Default: True.
        limit (int | None): Cap the number of feeds, from the list. Default: no limit.
        criteria (list[str] | None): Backfill only these criteria. Default: None, meaning
                        every implemented criterion.
        batch_size (int): Feeds loaded and marched per batch. Default: 200.
        only_missing (bool): Skip feeds that already have seal state, which is #1763's stated
                        scope. False re-backfills them, overwriting what is stored.
                        Default: True.
        snapshot_mode (str): "final" (only the last day, per #1763), "all" (every simulated
                        day — millions of rows over a year, but what would let #1803 resume
                        inside the backfilled window), or "none". Default: "final".
        resume_from_snapshot (bool): Seed each criterion from its snapshot at march_start - 1
                        rather than cold-starting empty. The #1803 hook. Default: False.
        max_reported_feeds (int): Cap on the `feeds` list in the response; `feeds_omitted`
                        reports how many entries were left out. Default: 50.
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
    )
