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
"""Cloud CDN caching of `<feed>/latest.zip`.

Only latest.zip is served through the CDN (the files URL map routes it to a CDN-enabled
backend bucket); every other object in the datasets bucket bypasses it. latest.zip is
overwritten every time a feed publishes a new dataset, so the CDN keeps it for a day
through `s-maxage` and the batch process tells it to drop its copy after each upload.
`max-age=0` keeps clients and proxies downstream of the CDN from holding their own stale
copy, since the CDN passes the header through to them unchanged and no invalidation can
reach them.
"""

import logging
import os
import time
from typing import Optional

LATEST_DATASET_CACHE_CONTROL = "public, max-age=0, s-maxage=86400"

COMPUTE_API_URL = "https://compute.googleapis.com/compute/v1"
# Short: the invalidation is fire-and-forget and runs inside dataset processing.
REQUEST_TIMEOUT_SECONDS = 10
MAX_ATTEMPTS = 3


def latest_dataset_object_name(feed_stable_id: str) -> str:
    """The name of a feed's latest dataset in the datasets bucket.

    Keep in sync with the files URL map route that sends it to the CDN
    (`path_template_match` in infra/batch/main.tf).
    """
    return f"{feed_stable_id}/latest.zip"


def latest_dataset_path(feed_stable_id: str) -> str:
    """The path of a feed's latest dataset as the CDN sees it."""
    return f"/{latest_dataset_object_name(feed_stable_id)}"


def invalidate_cdn_cache(path: str) -> Optional[str]:
    """Ask Cloud CDN to drop its cached copies of `path`.

    Returns the name of the Compute operation, or None when no URL map is configured
    (local runs and tests), in which case nothing is sent. The invalidation itself runs
    asynchronously on Google's side and usually takes effect within minutes.
    Retries a failed submission a couple of times before raising.
    """
    url_map = os.getenv("FILES_URL_MAP_NAME")
    project_id = os.getenv("PROJECT_ID")
    if not url_map or not project_id:
        logging.info(
            "FILES_URL_MAP_NAME or PROJECT_ID not set; skipping CDN invalidation of %s",
            path,
        )
        return None

    # Imported here so that modules using only the constants above never touch auth.
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    session = AuthorizedSession(credentials)
    url = (
        f"{COMPUTE_API_URL}/projects/{project_id}/global/urlMaps/{url_map}"
        "/invalidateCache"
    )
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = session.post(
                url, json={"path": path}, timeout=REQUEST_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            break
        except Exception as error:
            if attempt == MAX_ATTEMPTS:
                raise
            logging.warning(
                "CDN invalidation of %s failed (attempt %d/%d): %s",
                path,
                attempt,
                MAX_ATTEMPTS,
                error,
            )
            time.sleep(2**attempt)
    operation = response.json().get("name")
    logging.info("Requested CDN invalidation of %s (operation %s)", path, operation)
    return operation
