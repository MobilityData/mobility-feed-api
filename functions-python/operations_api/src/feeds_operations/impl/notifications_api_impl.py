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

import logging
from typing import List, Optional

import sib_api_v3_sdk
import urllib3
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from feeds_gen.apis.notifications_api_base import BaseNotificationsApi
from feeds_gen.models.operation_brevo_contact_state import OperationBrevoContactState
from feeds_gen.models.operation_brevo_sync_status import OperationBrevoSyncStatus
from feeds_gen.models.operation_notification_event_detail import (
    OperationNotificationEventDetail,
)
from feeds_gen.models.operation_notification_event_list import (
    OperationNotificationEventList,
)
from feeds_gen.models.operation_notification_log import OperationNotificationLog
from feeds_gen.models.operation_notification_log_list import (
    OperationNotificationLogList,
)
from feeds_gen.models.operation_notification_subscription import (
    OperationNotificationSubscription,
)
from feeds_operations.impl.feeds_operations_impl import _as_datetime
from feeds_operations.impl.models.operation_notification_impl import (
    OperationNotificationEventDetailImpl,
    OperationNotificationEventImpl,
    OperationNotificationLogImpl,
    OperationNotificationSubscriptionImpl,
)
from shared.common.brevo import (
    BrevoContactListState,
    BrevoSubscriptionStatus,
    get_announcements_list_id,
    get_contact_list_state,
)
from shared.database.users_database import with_users_db_session
from shared.notifications.notification_constants import (
    NotificationLogStatus,
    NotificationTypeId,
)
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    NotificationEvent,
    NotificationEventFeed,
    NotificationLog,
    NotificationSubscription,
)

logger = logging.getLogger(__name__)

_LOG_STATUSES = {
    NotificationLogStatus.PENDING,
    NotificationLogStatus.SENT,
    NotificationLogStatus.FAILED,
    NotificationLogStatus.PERMANENTLY_FAILED,
}


def _logs_query(db_session):
    """Delivery logs joined to their subscription's owner and type."""
    return db_session.query(
        NotificationLog,
        NotificationSubscription.user_id,
        NotificationSubscription.notification_type_id,
    ).outerjoin(
        NotificationSubscription,
        NotificationSubscription.id == NotificationLog.subscription_id,
    )


def _log_rows_to_models(rows) -> List[OperationNotificationLog]:
    return [
        OperationNotificationLogImpl.from_orm(log, user_id, notification_type_id)
        for log, user_id, notification_type_id in rows
    ]


def _brevo_sync_issues(
    subscription_id: Optional[str],
    subscription_active: Optional[bool],
    subscription_count: int,
    app_user_opt_in: bool,
    brevo: BrevoContactListState,
) -> List[str]:
    """One line per disagreement between the subscription row, the flag and Brevo."""
    issues = []
    if subscription_id is None:
        issues.append("No api.announcements subscription row.")
    elif subscription_count > 1:
        issues.append(
            f"{subscription_count} api.announcements subscription rows; expected one."
        )
    if subscription_id is not None and subscription_active != app_user_opt_in:
        issues.append(
            f"Subscription active is {subscription_active} but the app_user "
            f"opt-in flag is {app_user_opt_in}."
        )

    # The subscription row decides what Brevo should hold; the flag only when there is no row.
    opted_in = subscription_active if subscription_id is not None else app_user_opt_in
    subscribed_in_brevo = (
        brevo.in_list and brevo.status == BrevoSubscriptionStatus.SUBSCRIBED
    )
    if opted_in and not subscribed_in_brevo:
        if brevo.status == BrevoSubscriptionStatus.NOT_FOUND:
            issues.append("Opted in but Brevo has no contact for this email.")
        elif brevo.email_blacklisted:
            issues.append(
                "Opted in but the Brevo contact is blacklisted (unsubscribed from all campaigns)."
            )
        elif brevo.list_unsubscribed:
            issues.append(
                "Opted in but the contact unsubscribed from the announcements list in Brevo."
            )
        else:
            issues.append("Opted in but the contact is not on the announcements list.")
    elif not opted_in and subscribed_in_brevo:
        issues.append(
            "Opted out but the contact is still subscribed to the announcements list in Brevo."
        )

    if (
        subscription_id is not None
        and brevo.in_list
        and brevo.mdb_subscription_id != subscription_id
    ):
        issues.append(
            f"Brevo MDB_SUBSCRIPTION_ID is {brevo.mdb_subscription_id or 'unset'} "
            f"but the subscription ID is {subscription_id}."
        )
    return issues


class NotificationsApiImpl(BaseNotificationsApi):
    """Implementation of the Operations notifications API (read-only)."""

    @with_users_db_session
    def list_notification_events(
        self,
        notification_type_id: Optional[str] = None,
        event_subtype: Optional[str] = None,
        source: Optional[str] = None,
        feed_stable_id: Optional[str] = None,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
        limit: Optional[int] = 100,
        offset: Optional[int] = 0,
        db_session=None,
    ) -> OperationNotificationEventList:
        limit = limit or 100
        offset = offset or 0
        created_after = _as_datetime(created_after)
        created_before = _as_datetime(created_before)

        q = db_session.query(NotificationEvent)
        if notification_type_id:
            q = q.filter(NotificationEvent.notification_type_id == notification_type_id)
        if event_subtype:
            q = q.filter(NotificationEvent.event_subtype == event_subtype)
        if source:
            q = q.filter(NotificationEvent.source == source)
        if feed_stable_id:
            q = q.filter(
                NotificationEvent.id.in_(
                    select(NotificationEventFeed.notification_event_id).where(
                        NotificationEventFeed.feed_stable_id == feed_stable_id
                    )
                )
            )
        if created_after:
            q = q.filter(NotificationEvent.created_at >= created_after)
        if created_before:
            q = q.filter(NotificationEvent.created_at < created_before)

        total = q.order_by(None).count()
        events = (
            q.options(selectinload(NotificationEvent.notification_event_feeds))
            .order_by(NotificationEvent.created_at.desc(), NotificationEvent.id)
            .offset(offset)
            .limit(limit)
            .all()
        )
        return OperationNotificationEventList(
            total=total,
            offset=offset,
            limit=limit,
            events=[OperationNotificationEventImpl.from_orm(e) for e in events],
        )

    @with_users_db_session
    def get_notification_event(
        self, id: str, db_session=None
    ) -> OperationNotificationEventDetail:
        event = (
            db_session.query(NotificationEvent)
            .options(selectinload(NotificationEvent.notification_event_feeds))
            .filter(NotificationEvent.id == id)
            .first()
        )
        if not event:
            raise HTTPException(status_code=404, detail="Notification event not found.")
        rows = (
            _logs_query(db_session)
            .filter(NotificationLog.notification_event_id == id)
            .order_by(NotificationLog.sent_at.desc(), NotificationLog.id)
            .all()
        )
        return OperationNotificationEventDetailImpl.from_orm(
            event, _log_rows_to_models(rows)
        )

    @with_users_db_session
    def list_notification_logs(
        self,
        status: Optional[str] = None,
        subscription_id: Optional[str] = None,
        user_id: Optional[str] = None,
        notification_event_id: Optional[str] = None,
        notification_type_id: Optional[str] = None,
        sent_after: Optional[str] = None,
        sent_before: Optional[str] = None,
        limit: Optional[int] = 100,
        offset: Optional[int] = 0,
        db_session=None,
    ) -> OperationNotificationLogList:
        limit = limit or 100
        offset = offset or 0
        if status and status not in _LOG_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. "
                f"Expected one of: {', '.join(sorted(_LOG_STATUSES))}.",
            )
        sent_after = _as_datetime(sent_after)
        sent_before = _as_datetime(sent_before)

        q = _logs_query(db_session)
        if status:
            q = q.filter(NotificationLog.status == status)
        if subscription_id:
            q = q.filter(NotificationLog.subscription_id == subscription_id)
        if user_id:
            q = q.filter(NotificationSubscription.user_id == user_id)
        if notification_event_id:
            q = q.filter(NotificationLog.notification_event_id == notification_event_id)
        if notification_type_id:
            q = q.filter(
                NotificationSubscription.notification_type_id == notification_type_id
            )
        if sent_after:
            q = q.filter(NotificationLog.sent_at >= sent_after)
        if sent_before:
            q = q.filter(NotificationLog.sent_at < sent_before)

        total = q.order_by(None).count()
        rows = (
            q.order_by(NotificationLog.sent_at.desc(), NotificationLog.id)
            .offset(offset)
            .limit(limit)
            .all()
        )
        return OperationNotificationLogList(
            total=total,
            offset=offset,
            limit=limit,
            logs=_log_rows_to_models(rows),
        )

    @with_users_db_session
    def get_operations_user_subscriptions(
        self, user_id: str, db_session=None
    ) -> List[OperationNotificationSubscription]:
        if not db_session.get(AppUser, user_id):
            raise HTTPException(status_code=404, detail="User not found.")
        subscriptions = (
            db_session.query(NotificationSubscription)
            .options(
                selectinload(NotificationSubscription.notification_subscription_feeds)
            )
            .filter(NotificationSubscription.user_id == user_id)
            .order_by(NotificationSubscription.created_at, NotificationSubscription.id)
            .all()
        )
        return [
            OperationNotificationSubscriptionImpl.from_orm(s) for s in subscriptions
        ]

    @with_users_db_session
    def get_operations_user_brevo_sync(
        self, user_id: str, db_session=None
    ) -> OperationBrevoSyncStatus:
        user = db_session.get(AppUser, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        subscriptions = (
            db_session.query(NotificationSubscription)
            .filter(
                NotificationSubscription.user_id == user_id,
                NotificationSubscription.notification_type_id
                == NotificationTypeId.API_ANNOUNCEMENTS,
            )
            .order_by(NotificationSubscription.created_at, NotificationSubscription.id)
            .all()
        )
        # Read everything needed into plain values first: the commit below expires the
        # ORM objects, and touching them afterwards would reopen a connection.
        email = user.email
        app_user_opt_in = bool(user.is_registered_to_receive_api_announcements)
        subscription = subscriptions[0] if subscriptions else None
        subscription_id = subscription.id if subscription else None
        subscription_active = bool(subscription.active) if subscription else None
        # Only reads happened above: committing returns the pooled connection before the
        # (possibly slow) Brevo call.
        db_session.commit()

        try:
            brevo = get_contact_list_state(email, get_announcements_list_id())
        except RuntimeError as e:
            logger.error("Brevo is not configured: %s", e)
            raise HTTPException(
                status_code=500, detail="Brevo is not configured."
            ) from None
        except (sib_api_v3_sdk.rest.ApiException, urllib3.exceptions.HTTPError) as e:
            logger.warning("Brevo lookup failed for user %s: %s", user_id, e)
            raise HTTPException(
                status_code=502, detail="Failed to reach the email provider."
            ) from None

        issues = _brevo_sync_issues(
            subscription_id,
            subscription_active,
            len(subscriptions),
            app_user_opt_in,
            brevo,
        )
        return OperationBrevoSyncStatus(
            user_id=user_id,
            email=email,
            subscription_id=subscription_id,
            subscription_active=subscription_active,
            app_user_opt_in=app_user_opt_in,
            brevo=OperationBrevoContactState(
                status=brevo.status.value,
                in_list=brevo.in_list,
                email_blacklisted=brevo.email_blacklisted,
                list_unsubscribed=brevo.list_unsubscribed,
                mdb_subscription_id=brevo.mdb_subscription_id,
            ),
            in_sync=not issues,
            issues=issues,
        )
