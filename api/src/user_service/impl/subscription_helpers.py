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
"""Helpers shared between the authenticated (users) and public (subscriptions) APIs."""

import logging

from fastapi import HTTPException

import sib_api_v3_sdk
import urllib3
from shared.common.brevo import add_contact_to_list, get_announcements_list_id, remove_contact_from_list

logger = logging.getLogger(__name__)

ANNOUNCEMENTS_NOTIFICATION_TYPE_ID = "api.announcements"

# Feature flag (feature_flag.id) that gates notification-subscription management: a user must
# have this boolean flag resolved to true to create (POST) or update (PATCH) subscriptions.
NOTIFICATIONS_FEATURE_FLAG_ID = "isNotificationEnabled"

# The admin dispatch-summary notification type and the additional feature flag required to
# subscribe to (or manage a subscription for) it. This is layered on top of the general
# NOTIFICATIONS_FEATURE_FLAG_ID gate.
ADMIN_EVENT_SUMMARY_NOTIFICATION_TYPE_ID = "admin.event_summary"
ADMIN_SUMMARY_FEATURE_FLAG_ID = "isAdminSummarySubscriptionEnabled"

# Notification types that are scoped to specific feeds. A subscription to any of
# these must carry a non-empty list of feed stable IDs (persisted in the
# notification_subscription_feed join table); other types must not carry feeds.
FEED_SCOPED_NOTIFICATION_TYPE_IDS = frozenset(
    {
        "feed.url_updated",
        "feed.url_availability",
        "feed.coverage",
    }
)


def sync_announcements(email: str, subscribe: bool, subscription_id: str | None = None) -> None:
    """Sync an api.announcements subscription with Brevo, mapping provider errors to 502."""
    try:
        if subscribe:
            add_contact_to_list(email, get_announcements_list_id(), subscription_id)
        else:
            remove_contact_from_list(email, get_announcements_list_id())
    except (RuntimeError, sib_api_v3_sdk.rest.ApiException, urllib3.exceptions.HTTPError, OSError) as exc:
        # urllib3.exceptions.HTTPError / OSError cover connection failures and timeouts (e.g. Brevo
        # unreachable), so the request fails fast with a 502 instead of hanging on retries.
        logger.error("Brevo sync failed for %s: %s", email, exc)
        raise HTTPException(status_code=502, detail="Failed to sync subscription with email provider.")
