#
#   MobilityData 2025
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import logging
import os
from typing import List

import requests

logger = logging.getLogger(__name__)

# The website endpoint is given 30s for one feed, as it always has been. A batched call asks it
# to revalidate up to `WEB_REVALIDATION_CHUNK_SIZE` pages in one request, so it gets
# proportionally longer before the task is retried. Both sit far below the function's own
# timeout (1000s), so neither can outlive its invocation.
SINGLE_REQUEST_TIMEOUT_SECONDS = 30
BATCH_REQUEST_TIMEOUT_SECONDS = 120


def _requested_feed_ids(payload: dict) -> List[str]:
    """The feeds to revalidate, from either payload shape.

    `feed_stable_ids` is the batched form; `feed_stable_id` is the original single-feed
    form, still produced by `create_web_revalidation_task` and by every dataset-driven call
    site, and still in flight in the queue whenever this deploys.
    """
    feed_stable_ids = payload.get("feed_stable_ids")
    if feed_stable_ids:
        return list(feed_stable_ids)
    feed_stable_id = payload.get("feed_stable_id")
    return [feed_stable_id] if feed_stable_id else []


def _describe(feed_stable_ids: List[str]) -> str:
    """How the feeds are named in messages and logs: the id itself, or how many there are."""
    if len(feed_stable_ids) == 1:
        return f"feed {feed_stable_ids[0]}"
    return f"{len(feed_stable_ids)} feeds"


def _identity(feed_stable_ids: List[str]) -> dict:
    """The feed keys echoed back in the response.

    `feed_stable_id` is kept for a single-feed call so the existing response shape is
    unchanged - callers and tests predate the batched form.
    """
    identity = {"feed_stable_ids": feed_stable_ids}
    if len(feed_stable_ids) == 1:
        identity["feed_stable_id"] = feed_stable_ids[0]
    return identity


def revalidate_feed_handler(payload: dict | None = None) -> dict:
    """
    Call the website revalidation endpoint to invalidate the cached
    feed detail pages for one or more feeds.

    The endpoint takes a list, so a batched call is one request rather than one per feed. That
    is what lets the nightly seal run revalidate every feed it changed.

    Payload (exactly one of):
        feed_stable_ids (list[str]): The stable IDs of the feeds to revalidate.
        feed_stable_id (str): The stable ID of a single feed to revalidate.
    """
    payload = payload or {}
    feed_stable_ids = _requested_feed_ids(payload)
    if not feed_stable_ids:
        return {
            "error": "feed_stable_id or feed_stable_ids is required",
            "status": "error",
        }

    identity = _identity(feed_stable_ids)
    described = _describe(feed_stable_ids)

    revalidate_url = os.getenv("WEB_APP_REVALIDATE_URL")
    revalidate_secret = os.getenv("WEB_APP_REVALIDATE_SECRET")

    if not revalidate_url:
        logger.warning("WEB_APP_REVALIDATE_URL not configured; skipping revalidation.")
        return {
            "message": "Revalidation skipped: WEB_APP_REVALIDATE_URL not configured.",
            **identity,
            "status": "skipped",
        }

    if not revalidate_secret:
        logger.warning(
            "WEB_APP_REVALIDATE_SECRET not configured; skipping revalidation."
        )
        return {
            "message": "Revalidation skipped: WEB_APP_REVALIDATE_SECRET not configured.",
            **identity,
            "status": "skipped",
        }

    timeout = (
        SINGLE_REQUEST_TIMEOUT_SECONDS
        if len(feed_stable_ids) == 1
        else BATCH_REQUEST_TIMEOUT_SECONDS
    )

    try:
        response = requests.post(
            revalidate_url,
            json={"feedIds": feed_stable_ids, "type": "specific-feeds"},
            headers={
                "x-revalidate-secret": revalidate_secret,
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        logger.info(
            "Revalidation succeeded for %s (status=%s)",
            described,
            response.status_code,
        )
        return {
            "message": f"Revalidation triggered for {described}.",
            **identity,
            "status": "success",
            "http_status": response.status_code,
        }
    except requests.RequestException as e:
        logger.error("Revalidation failed for %s: %s", described, e)
        return {
            "error": f"Revalidation failed for {described}: {e}",
            **identity,
            "status": "error",
        }
