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
"""Bust the website's Feed Detail cache for the feeds whose seal changed."""

import logging
from typing import Sequence

from shared.common.gcp_utils import create_web_revalidation_batch_tasks

logger = logging.getLogger(__name__)


def revalidate_changed_feeds(
    changed_stable_ids: Sequence[str],
    dedup_key: str,
) -> dict:
    """Enqueue a website revalidation for every feed whose rendered seal state changed.

    Args:
        changed_stable_ids: The feeds to revalidate. An empty sequence is a no-op.
        dedup_key: Identifies the work being enqueued, so that a redelivery of the same unit
            produces the same task names and enqueues nothing new. The nightly worker passes
            its run and batch ids, which is exactly what Cloud Tasks may redeliver.

    Returns:
        `{"feeds_revalidated": int, "revalidation_tasks": int}`, to be merged into the batch
        report the monitor aggregates. The two differ only by the batching: every changed feed
        is always counted in the first.
    """
    if not changed_stable_ids:
        return {"feeds_revalidated": 0, "revalidation_tasks": 0}

    feed_stable_ids = list(changed_stable_ids)
    tasks = create_web_revalidation_batch_tasks(feed_stable_ids, dedup_key=dedup_key)
    logger.info(
        "Enqueued %d web revalidation task(s) for %d feed(s) whose seal state changed.",
        tasks,
        len(feed_stable_ids),
    )
    return {
        "feeds_revalidated": len(feed_stable_ids),
        "revalidation_tasks": tasks,
    }
