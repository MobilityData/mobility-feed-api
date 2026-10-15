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
"""Task entry point for the nightly Seal of Reliability evaluation (issue #1761)."""

import logging
from datetime import datetime, timezone

from tasks.seal_of_reliability.revalidation import revalidate_changed_feeds
from tasks.seal_of_reliability.seal_updater import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_MAX_REPORTED_FEEDS,
    update_seals,
)

logger = logging.getLogger(__name__)


def _parse_now(now: str) -> datetime:
    """Parse the `now` payload string to a UTC-aware datetime.

    An operator may pass a date or a naive timestamp (`2026-08-01`,
    `2026-08-01T00:00:00`); `fromisoformat` would return a naive value. The state machine
    compares `now` against tz-aware `timestamptz` columns, so a naive value raises
    `TypeError: can't subtract offset-naive and offset-aware datetimes`. Assume UTC when no
    offset is given, and normalize any offset to UTC otherwise.
    """
    parsed = datetime.fromisoformat(now)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def get_parameters(payload: dict):
    """Read the task parameters from the payload, applying defaults."""
    now = payload.get("now")
    return (
        payload.get("stable_feed_ids"),
        payload.get("dry_run", True),
        payload.get("limit", None),
        payload.get("criteria", None),
        payload.get("batch_size", DEFAULT_BATCH_SIZE),
        _parse_now(now) if now else None,
        payload.get("max_reported_feeds", DEFAULT_MAX_REPORTED_FEEDS),
        payload.get("revalidate", False),
    )


def update_seal_of_reliability_handler(payload: dict) -> dict:
    """
    Handler for the nightly Seal of Reliability evaluation.

    Payload parameters:
        stable_feed_ids (list[str]): Required and non-empty. The feeds to evaluate; there is
                        no run-the-whole-catalogue mode. Ineligible ids are skipped with a
                        logged warning, and it raises if none can be evaluated.
        dry_run (bool): Evaluate the feeds and return the report without writing.
                        Default: True.
        limit (int | None): Cap the number of feeds evaluated, from the list. Default: no
                        limit.
        criteria (list[str] | None): Evaluate only these criteria. A partial set skips the
                        has_seal roll-up. Default: None (every implemented criterion).
        batch_size (int): Feeds loaded per query batch. Every eligible feed is still
                        evaluated; this only sizes the queries. Default: 200.
        now (str | None): ISO timestamp to evaluate against, for replays and backfills.
                        Default: current UTC time.
        max_reported_feeds (int): Cap on the `feeds` list in the response. Everything is
                        still evaluated and written; `feeds_omitted` reports how many
                        entries were left out. Default: 50.
        revalidate (bool): Bust the website's Feed Detail cache for the feeds whose rendered
                        seal state changed. Opt-in here, unlike the nightly
                        orchestrator worker which always does it: an ad-hoc run is usually a
                        check, not a publication. Ignored on a dry run, which writes nothing
                        to compare against. Default: False.
    """
    (
        stable_feed_ids,
        dry_run,
        limit,
        criteria,
        batch_size,
        now,
        max_reported_feeds,
        revalidate,
    ) = get_parameters(payload)
    report = update_seals(
        stable_feed_ids=stable_feed_ids,
        dry_run=dry_run,
        limit=limit,
        criteria=criteria,
        batch_size=batch_size,
        now=now,
        max_reported_feeds=max_reported_feeds,
    )
    if revalidate and not dry_run:
        # Best-effort, as at every other revalidation call site: a cache that could not be
        # busted must not turn a completed evaluation into a failed task.
        try:
            # A manual invocation has no retry identity to preserve, so the key only has to be
            # unique per call.
            dedup_key = f"adhoc-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}"
            report.update(
                revalidate_changed_feeds(
                    report["changed_stable_ids"], dedup_key=dedup_key
                )
            )
        except Exception as error:
            logger.warning("Failed to enqueue web revalidation tasks: %s", error)
    return report
