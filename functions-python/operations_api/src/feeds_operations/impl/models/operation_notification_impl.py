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

from typing import List, Optional

from feeds_gen.models.operation_notification_event import OperationNotificationEvent
from feeds_gen.models.operation_notification_event_detail import (
    OperationNotificationEventDetail,
)
from feeds_gen.models.operation_notification_event_feed import (
    OperationNotificationEventFeed,
)
from feeds_gen.models.operation_notification_log import OperationNotificationLog
from feeds_gen.models.operation_notification_subscription import (
    OperationNotificationSubscription,
)
from shared.users_database_gen.sqlacodegen_models import (
    NotificationEvent,
    NotificationLog,
    NotificationSubscription,
)


def _event_feeds(event: NotificationEvent) -> List[OperationNotificationEventFeed]:
    return [
        OperationNotificationEventFeed(feed_stable_id=f.feed_stable_id, role=f.role)
        for f in sorted(
            event.notification_event_feeds or [],
            key=lambda f: (f.role, f.feed_stable_id),
        )
    ]


class OperationNotificationEventImpl(OperationNotificationEvent):
    """Converts a NotificationEvent ORM object to an OperationNotificationEvent Pydantic model."""

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, event: NotificationEvent) -> OperationNotificationEvent:
        return cls(
            id=event.id,
            notification_type_id=event.notification_type_id,
            event_subtype=event.event_subtype,
            source=event.source,
            payload=event.payload,
            created_at=event.created_at,
            feeds=_event_feeds(event),
        )


class OperationNotificationEventDetailImpl(OperationNotificationEventDetail):
    """Converts a NotificationEvent and its delivery logs to an OperationNotificationEventDetail."""

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(
        cls,
        event: NotificationEvent,
        logs: List[OperationNotificationLog],
    ) -> OperationNotificationEventDetail:
        return cls(
            id=event.id,
            notification_type_id=event.notification_type_id,
            event_subtype=event.event_subtype,
            source=event.source,
            payload=event.payload,
            created_at=event.created_at,
            feeds=_event_feeds(event),
            logs=logs,
        )


class OperationNotificationLogImpl(OperationNotificationLog):
    """Converts a NotificationLog ORM object to an OperationNotificationLog Pydantic model.

    ``user_id`` and ``notification_type_id`` live on the subscription, so the caller
    passes them in from the joined row.
    """

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(
        cls,
        log: NotificationLog,
        user_id: Optional[str] = None,
        notification_type_id: Optional[str] = None,
    ) -> OperationNotificationLog:
        return cls(
            id=log.id,
            notification_event_id=log.notification_event_id,
            subscription_id=log.subscription_id,
            user_id=user_id,
            notification_type_id=notification_type_id,
            channel=log.channel,
            status=log.status,
            retry_count=log.retry_count or 0,
            error_message=log.error_message,
            sent_at=log.sent_at,
        )


class OperationNotificationSubscriptionImpl(OperationNotificationSubscription):
    """Converts a NotificationSubscription ORM object to an OperationNotificationSubscription."""

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(
        cls, subscription: NotificationSubscription
    ) -> OperationNotificationSubscription:
        return cls(
            id=subscription.id,
            notification_type_id=subscription.notification_type_id,
            active=subscription.active,
            cadence=subscription.cadence,
            digest=subscription.digest,
            feed_ids=sorted(
                f.feed_stable_id
                for f in (subscription.notification_subscription_feeds or [])
            ),
            filter_params=subscription.filter_params,
            created_at=subscription.created_at,
            active_since=subscription.active_since,
        )
