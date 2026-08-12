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

from datetime import datetime

from tasks.seal_of_reliability.seal_updater import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_MAX_REPORTED_EVALUATIONS,
    update_seals,
)


def get_parameters(payload: dict):
    """Read the task parameters from the payload, applying defaults."""
    now = payload.get("now")
    return (
        payload.get("dry_run", True),
        payload.get("stable_feed_ids", None),
        payload.get("limit", None),
        payload.get("criteria", None),
        payload.get("batch_size", DEFAULT_BATCH_SIZE),
        datetime.fromisoformat(now) if now else None,
        payload.get("max_reported_evaluations", DEFAULT_MAX_REPORTED_EVALUATIONS),
    )


def update_seal_of_reliability_handler(payload: dict) -> dict:
    """
    Handler for the nightly Seal of Reliability evaluation.

    Payload parameters:
        dry_run (bool): Evaluate every feed and return the report without writing.
                        Default: True.
        stable_feed_ids (list[str] | None): Evaluate only these feeds. Unknown ids raise.
                        When set, `evaluations` covers every criterion of those feeds.
                        Default: None (all eligible feeds).
        limit (int | None): Cap the number of feeds evaluated. Default: no limit.
        criteria (list[str] | None): Evaluate only these criteria. A partial set skips the
                        has_seal roll-up. Default: None (every implemented criterion).
        batch_size (int): Feeds loaded per query batch. Every eligible feed is still
                        evaluated; this only sizes the queries. Default: 200.
        now (str | None): ISO timestamp to evaluate against, for replays and backfills.
                        Default: current UTC time.
        max_reported_evaluations (int): Cap on the `evaluations` list in the response. Everything is
                        still evaluated and written; `evaluations_omitted` reports how many
                        entries were left out. Default: 50.
    """
    (
        dry_run,
        stable_feed_ids,
        limit,
        criteria,
        batch_size,
        now,
        max_reported_evaluations,
    ) = get_parameters(payload)
    return update_seals(
        dry_run=dry_run,
        stable_feed_ids=stable_feed_ids,
        limit=limit,
        criteria=criteria,
        batch_size=batch_size,
        now=now,
        max_reported_evaluations=max_reported_evaluations,
    )
