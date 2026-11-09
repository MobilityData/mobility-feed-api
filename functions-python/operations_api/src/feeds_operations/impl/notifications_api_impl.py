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
import os
from typing import Dict, List, Optional

import google.auth.transport.requests
import requests
import sib_api_v3_sdk
import urllib3
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from google.oauth2 import id_token
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from feeds_gen.apis.notifications_api_base import BaseNotificationsApi
from feeds_gen.models.operation_brevo_contact_state import OperationBrevoContactState
from feeds_gen.models.operation_brevo_sync_status import OperationBrevoSyncStatus
from feeds_gen.models.operation_notification_dispatch_planned_run import (
    OperationNotificationDispatchPlannedRun,
)
from feeds_gen.models.operation_notification_dispatch_request import (
    OperationNotificationDispatchRequest,
)
from feeds_gen.models.operation_notification_dispatch_run import (
    OperationNotificationDispatchRun,
)
from feeds_gen.models.operation_notification_dispatch_start import (
    OperationNotificationDispatchStart,
)
from feeds_gen.models.operation_notification_test_event_request import (
    OperationNotificationTestEventRequest,
)
from feeds_gen.models.operation_notification_event import OperationNotificationEvent
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
from shared.database.database import with_db_session
from shared.database.users_database import with_users_db_session
from shared.database_gen.sqlacodegen_models import Feed
from shared.helpers.task_execution.task_execution_tracker import TaskExecutionTracker
from shared.notifications.notification_constants import (
    DISPATCH_RUN_TASK_NAME,
    FeedUrlUpdateType,
    NotificationFeedRole,
    NotificationLogStatus,
    NotificationSource,
    NotificationTypeId,
    TEST_RECIPIENT_USER_IDS_KEY,
)
from shared.notifications.notification_event_service import add_event
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


# Shown as the new URL of a test `url_replaced` event when the caller gives none.
_TEST_NEW_URL = "https://example.com/operations-test/feed.zip"
# The dispatch batch only plans and enqueues workers, but with many subscriptions
# the enqueue loop takes a while; stay under the function's own 540s timeout.
_TASKS_EXECUTOR_TIMEOUT_SECONDS = 480


@with_db_session
def _feed_producer_urls(stable_ids: List[str], db_session=None) -> Dict[str, str]:
    """producer_url by stable_id for the feeds that exist (feeds DB)."""
    rows = (
        db_session.query(Feed.stable_id, Feed.producer_url)
        .filter(Feed.stable_id.in_(stable_ids))
        .all()
    )
    return {stable_id: producer_url for stable_id, producer_url in rows}


def _run_tasks_executor(task: str, payload: dict) -> dict:
    """Run a tasks_executor task over HTTP, the way Cloud Scheduler triggers it:
    a POST of ``{"task", "payload"}`` with an OIDC token for the function URL."""
    url = os.getenv("TASKS_EXECUTOR_URL")
    if not url:
        logger.error("TASKS_EXECUTOR_URL is not configured.")
        raise HTTPException(
            status_code=500, detail="The tasks executor is not configured."
        )
    try:
        token = id_token.fetch_id_token(google.auth.transport.requests.Request(), url)
        response = requests.post(
            url,
            json={"task": task, "payload": payload},
            headers={"Authorization": f"Bearer {token}"},
            timeout=_TASKS_EXECUTOR_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error("tasks_executor task %s failed: %s", task, e)
        raise HTTPException(
            status_code=502, detail=f"Failed to run the {task} task."
        ) from None


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
    brevo: BrevoContactListState,
) -> List[str]:
    """One line per disagreement between the subscription row and Brevo."""
    issues = []
    if subscription_id is None:
        issues.append("No api.announcements subscription row.")
    elif subscription_count > 1:
        issues.append(
            f"{subscription_count} api.announcements subscription rows; expected one."
        )

    # The opt-in is the active subscription row; with no row the user is opted out.
    opted_in = bool(subscription_active)
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
    """Implementation of the Operations notifications API."""

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
            brevo,
        )
        return OperationBrevoSyncStatus(
            user_id=user_id,
            email=email,
            subscription_id=subscription_id,
            subscription_active=subscription_active,
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

    @with_users_db_session
    def create_test_notification_event(
        self,
        operation_notification_test_event_request: OperationNotificationTestEventRequest,
        db_session=None,
    ) -> OperationNotificationEvent:
        request = operation_notification_test_event_request
        recipient_user_ids = list(dict.fromkeys(request.recipient_user_ids or []))
        if not recipient_user_ids:
            raise HTTPException(
                status_code=400, detail="recipient_user_ids must not be empty."
            )
        redirected = request.event_subtype == FeedUrlUpdateType.FEED_REDIRECTED
        if redirected and not request.target_feed_stable_id:
            raise HTTPException(
                status_code=400,
                detail="target_feed_stable_id is required for feed_redirected.",
            )

        stable_ids = [request.feed_stable_id]
        if redirected:
            stable_ids.append(request.target_feed_stable_id)
        producer_urls = _feed_producer_urls(stable_ids)
        missing_feeds = [s for s in stable_ids if s not in producer_urls]
        if missing_feeds:
            raise HTTPException(
                status_code=404, detail=f"Feed not found: {', '.join(missing_feeds)}."
            )

        known_users = {
            user_id
            for (user_id,) in db_session.query(AppUser.id).filter(
                AppUser.id.in_(recipient_user_ids)
            )
        }
        unknown_users = [u for u in recipient_user_ids if u not in known_users]
        if unknown_users:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown recipient user IDs: {', '.join(unknown_users)}.",
            )

        feeds = [(request.feed_stable_id, NotificationFeedRole.SUBJECT)]
        if redirected:
            feeds.append((request.target_feed_stable_id, NotificationFeedRole.TARGET))
            default_new_url = producer_urls[request.target_feed_stable_id]
        else:
            default_new_url = _TEST_NEW_URL
        event_id = add_event(
            db_session=db_session,
            notification_type_id=NotificationTypeId.FEED_URL_UPDATED,
            event_subtype=request.event_subtype,
            source=NotificationSource.OPERATIONS_TEST,
            feeds=feeds,
            payload={
                "old_url": request.old_url or producer_urls[request.feed_stable_id],
                "new_url": request.new_url or default_new_url,
                TEST_RECIPIENT_USER_IDS_KEY: recipient_user_ids,
            },
        )
        db_session.commit()

        event = (
            db_session.query(NotificationEvent)
            .options(selectinload(NotificationEvent.notification_event_feeds))
            .filter(NotificationEvent.id == event_id)
            .one()
        )
        payload = OperationNotificationEventImpl.from_orm(event).model_dump()
        return JSONResponse(status_code=201, content=jsonable_encoder(payload))

    def start_notification_dispatch(
        self,
        operation_notification_dispatch_request: OperationNotificationDispatchRequest,
    ) -> OperationNotificationDispatchStart:
        request = operation_notification_dispatch_request
        result = _run_tasks_executor(
            "notifications_dispatch_batch",
            {
                "cadence": request.cadence,
                "user_ids": request.user_ids or [],
                "dry_run": bool(request.dry_run),
                "force": bool(request.force),
            },
        )
        by_cadence = result.get("by_cadence") or {}
        return OperationNotificationDispatchStart(
            runs=[
                OperationNotificationDispatchPlannedRun(
                    cadence=cadence,
                    run_id=run["run_id"],
                    subscriptions=run["subscriptions"],
                    enqueued=run["enqueued"],
                    dry_run=run["dry_run"],
                    preview=run.get("preview"),
                )
                for cadence, run in by_cadence.items()
            ]
        )

    @with_db_session
    def get_notification_dispatch_run(
        self, run_id: str, db_session=None
    ) -> OperationNotificationDispatchRun:
        summary = TaskExecutionTracker(
            task_name=DISPATCH_RUN_TASK_NAME,
            run_id=run_id,
            db_session=db_session,
        ).get_summary()
        if summary["run_status"] is None:
            raise HTTPException(status_code=404, detail="Dispatch run not found.")
        params = summary["params"] or {}
        return OperationNotificationDispatchRun(
            run_id=run_id,
            status=summary["run_status"],
            cadence=params.get("cadence"),
            params=params,
            created_at=summary["created_at"],
            total=summary["total_count"] or 0,
            triggered=summary["triggered"],
            completed=summary["completed"],
            failed=summary["failed"],
            # Only the numeric sums: the workers store nothing else.
            stats={
                key: value
                for key, value in summary["metadata_summary"].items()
                if isinstance(value, (int, float))
            },
        )
