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

import requests

logger = logging.getLogger(__name__)


def revalidate_feed_handler(payload: dict | None = None) -> dict:
    """
    Call the web app's revalidation endpoint to invalidate the cached
    feed detail page for a specific feed.

    Payload:
        feed_stable_id (str): The stable ID of the feed to revalidate.
    """
    payload = payload or {}
    feed_stable_id = payload.get("feed_stable_id")
    if not feed_stable_id:
        return {"error": "feed_stable_id is required", "status": "error"}

    revalidate_url = os.getenv("WEB_APP_REVALIDATE_URL")
    revalidate_secret = os.getenv("WEB_APP_REVALIDATE_SECRET")

    if not revalidate_url:
        logger.warning("WEB_APP_REVALIDATE_URL not configured; skipping revalidation.")
        return {
            "message": "Revalidation skipped: WEB_APP_REVALIDATE_URL not configured.",
            "feed_stable_id": feed_stable_id,
            "status": "skipped",
        }

    if not revalidate_secret:
        logger.warning(
            "WEB_APP_REVALIDATE_SECRET not configured; skipping revalidation."
        )
        return {
            "message": "Revalidation skipped: WEB_APP_REVALIDATE_SECRET not configured.",
            "feed_stable_id": feed_stable_id,
            "status": "skipped",
        }

    try:
        response = requests.post(
            revalidate_url,
            json={"feedIds": [feed_stable_id], "type": "specific-feeds"},
            headers={
                "x-revalidate-secret": revalidate_secret,
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        response.raise_for_status()
        logger.info(
            "Revalidation succeeded for feed %s (status=%s)",
            feed_stable_id,
            response.status_code,
        )
        return {
            "message": f"Revalidation triggered for feed {feed_stable_id}.",
            "feed_stable_id": feed_stable_id,
            "status": "success",
            "http_status": response.status_code,
        }
    except requests.RequestException as e:
        logger.error("Revalidation failed for feed %s: %s", feed_stable_id, e)
        return {
            "error": f"Revalidation failed for feed {feed_stable_id}: {e}",
            "feed_stable_id": feed_stable_id,
            "status": "error",
        }
