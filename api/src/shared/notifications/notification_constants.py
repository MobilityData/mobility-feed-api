#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""Notification system string constants.

These classes act as namespaced string constants for values stored in the
``notification_type.id``, ``notification_event.update_type``,
``notification_subscription.cadence``, ``notification_log.status``, and
``notification_event.source`` columns.

Usage
-----
    from shared.notifications.notification_constants import (
        NotificationTypeId,
        FeedUrlUpdateType,
        AdminEventUpdateType,
        NotificationCadence,
        NotificationLogStatus,
        NotificationSource,
    )
"""


class NotificationTypeId:
    """Primary keys of rows in the ``notification_type`` table."""

    FEED_URL_UPDATED = "feed.url_updated"
    ADMIN_EVENT_SUMMARY = "admin.event_summary"


class FeedUrlUpdateType:
    """Allowed values for ``notification_event.update_type`` when
    ``notification_type_id == NotificationTypeId.FEED_URL_UPDATED``."""

    URL_REPLACED = "url_replaced"
    FEED_REDIRECTED = "feed_redirected"


class AdminEventUpdateType:
    """Allowed values for ``notification_event.update_type`` when
    ``notification_type_id == NotificationTypeId.ADMIN_EVENT_SUMMARY``."""

    DISPATCH_SUMMARY = "dispatch_summary"


class NotificationCadence:
    """Allowed values for ``notification_subscription.cadence``."""

    IMMEDIATE = "immediate"
    DAILY = "daily"
    WEEKLY = "weekly"


class NotificationLogStatus:
    """Allowed values for ``notification_log.status``."""

    SENT = "sent"
    FAILED = "failed"
    PERMANENTLY_FAILED = "permanently_failed"


class NotificationSource:
    """Human-readable tags for ``notification_event.source``."""

    DISPATCHER = "dispatcher"
    TDG_REDIRECTS = "tdg_redirects"
    TDG_IMPORT = "tdg_import"
