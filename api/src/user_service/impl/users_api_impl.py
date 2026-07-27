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
from datetime import datetime, timezone
from typing import List

from fastapi import HTTPException

from sqlalchemy.orm import selectinload

from middleware.request_context import get_request_context
from shared.database.database import generate_unique_id
from shared.database.users_database import with_users_db_session
from shared.db_models.app_user_impl import AppUserImpl
from shared.db_models.notification_subscription_impl import NotificationSubscriptionImpl
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    FeatureFlag,
    UserFeatureFlag,
    NotificationSubscription as NotificationSubscriptionOrm,
    NotificationSubscriptionFeed as NotificationSubscriptionFeedOrm,
    NotificationType,
)
from user_service.impl.subscription_helpers import (
    ADMIN_EVENT_SUMMARY_NOTIFICATION_TYPE_ID,
    ADMIN_SUMMARY_FEATURE_FLAG_ID,
    ANNOUNCEMENTS_NOTIFICATION_TYPE_ID,
    FEED_SCOPED_NOTIFICATION_TYPE_IDS,
    NOTIFICATIONS_FEATURE_FLAG_ID,
    sync_announcements,
)
from user_service_gen.apis.users_api_base import BaseUsersApi
from user_service_gen.models.create_notification_subscription_request import (
    CreateNotificationSubscriptionRequest,
)
from user_service_gen.models.notification_subscription import NotificationSubscription
from user_service_gen.models.update_notification_subscription_request import (
    UpdateNotificationSubscriptionRequest,
)
from user_service_gen.models.update_user_request import UpdateUserRequest
from user_service_gen.models.user_profile import UserProfile

logger = logging.getLogger(__name__)


class UsersApiImpl(BaseUsersApi):
    """Implementation of the User Service users API."""

    @with_users_db_session
    def get_user(self, db_session=None) -> UserProfile:
        """
        Returns the authenticated user's profile, creating it on first call (upsert).
        Guest users are not persisted — if no existing record exists, a 403 is returned.
        """
        context = get_request_context()
        user_id: str | None = context.get("user_id")
        user_email: str | None = context.get("user_email")

        if not user_id:
            raise HTTPException(status_code=401, detail="Unable to determine user identity from token.")

        if context.get("is_guest"):
            logger.warning(
                "Skipping user creation as guest users cannot create a profile. user_id=%s",
                user_id,
            )
            return UserProfile.from_dict({"id": user_id, "email": "", "created_at": datetime.now(timezone.utc)})

        user = (
            db_session.query(AppUser)
            .options(selectinload(AppUser.user_feature_flags).selectinload(UserFeatureFlag.feature_flag))
            .filter_by(id=user_id)
            .first()
        )
        if user is None:
            logger.info("Creating new app_user record for user_id=%s", user_id)
            user = AppUser(
                id=user_id,
                email=user_email or "",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db_session.add(user)
            db_session.flush()

        all_flags = db_session.query(FeatureFlag).filter(FeatureFlag.disabled.is_(False)).order_by(FeatureFlag.id).all()
        return AppUserImpl.from_orm(user, all_flags)

    @with_users_db_session
    def update_user(self, update_user_request: UpdateUserRequest, db_session=None) -> UserProfile:
        """
        Updates the authenticated user's mutable profile fields.
        Email is intentionally excluded (requires re-verification).
        Guest users cannot update their profile.
        """
        user_id = self._require_user_id()

        user = (
            db_session.query(AppUser)
            .options(selectinload(AppUser.user_feature_flags).selectinload(UserFeatureFlag.feature_flag))
            .filter_by(id=user_id)
            .first()
        )
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")

        update_data = update_user_request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        user.updated_at = datetime.now(timezone.utc)
        db_session.flush()

        all_flags = db_session.query(FeatureFlag).filter(FeatureFlag.disabled.is_(False)).order_by(FeatureFlag.id).all()
        return AppUserImpl.from_orm(user, all_flags)

    # ── Subscriptions ────────────────────────────────────────────────────────

    @with_users_db_session
    def get_user_subscriptions(self, db_session=None) -> List[NotificationSubscription]:
        """Returns all notification subscriptions for the authenticated user."""
        user_id = self._require_user_id()
        subs = (
            db_session.query(NotificationSubscriptionOrm)
            .options(selectinload(NotificationSubscriptionOrm.notification_subscription_feeds))
            .filter(NotificationSubscriptionOrm.user_id == user_id)
            .order_by(NotificationSubscriptionOrm.created_at)
            .all()
        )
        return [NotificationSubscriptionImpl.from_orm(s) for s in subs]

    @with_users_db_session
    def create_user_subscription(
        self, create_notification_subscription_request: CreateNotificationSubscriptionRequest, db_session=None
    ) -> NotificationSubscription:
        """Subscribes the authenticated user to a notification type (idempotent).

        For feed-scoped notification types (``feed.url_updated``, ``feed.url_availability``,
        ``feed.coverage``) a non-empty ``feed_ids`` list is required and is persisted in the
        ``notification_subscription_feed`` join table; the single (user, type) subscription's
        feed set is replaced with the supplied feeds. ``feed_ids`` must not be supplied for
        other notification types.
        """
        user_id = self._require_user_id()
        self._require_notifications_enabled(db_session, user_id)
        notification_id = create_notification_subscription_request.notification_id
        # De-duplicate while preserving order; treat null as no feeds.
        feed_ids = list(dict.fromkeys(create_notification_subscription_request.feed_ids or []))

        if db_session.get(NotificationType, notification_id) is None:
            raise HTTPException(status_code=400, detail=f"Unknown notification type '{notification_id}'.")

        # The admin dispatch-summary type is gated by an additional feature flag.
        if notification_id == ADMIN_EVENT_SUMMARY_NOTIFICATION_TYPE_ID:
            self._require_admin_summary_enabled(db_session, user_id)

        # Feed scoping is validated in code (the OpenAPI 3.0 schema keeps feed_ids optional).
        is_feed_scoped = notification_id in FEED_SCOPED_NOTIFICATION_TYPE_IDS
        if is_feed_scoped and not feed_ids:
            raise HTTPException(
                status_code=400,
                detail=f"feed_ids is required for notification type '{notification_id}'.",
            )
        if not is_feed_scoped and feed_ids:
            raise HTTPException(
                status_code=400,
                detail=f"feed_ids is not supported for notification type '{notification_id}'.",
            )

        user = db_session.get(AppUser, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")

        # Idempotent: reuse an existing subscription, reactivating if needed.
        existing = (
            db_session.query(NotificationSubscriptionOrm)
            .filter(
                NotificationSubscriptionOrm.user_id == user_id,
                NotificationSubscriptionOrm.notification_type_id == notification_id,
            )
            .one_or_none()
        )
        sub = existing or NotificationSubscriptionOrm(
            id=generate_unique_id(),
            user_id=user_id,
            notification_type_id=notification_id,
            created_at=datetime.now(timezone.utc),
        )
        sub.active = True

        # Replace the subscription's feed set with the supplied feeds (no-op for non-scoped
        # types, whose feed_ids is always empty here).
        self._sync_subscription_feeds(sub, feed_ids)

        if notification_id == ANNOUNCEMENTS_NOTIFICATION_TYPE_ID:
            sync_announcements(user.email, subscribe=True, subscription_id=sub.id)

        if existing is None:
            db_session.add(sub)
        db_session.flush()
        return NotificationSubscriptionImpl.from_orm(sub)

    @with_users_db_session
    def update_user_subscription(
        self, id: str, update_notification_subscription_request: UpdateNotificationSubscriptionRequest, db_session=None
    ) -> NotificationSubscription:
        """Activates or deactivates a notification subscription by ID."""
        user_id = self._require_user_id()
        self._require_notifications_enabled(db_session, user_id)
        sub = self._get_owned_subscription(db_session, id, user_id)

        # Managing an admin.event_summary subscription requires the additional admin flag.
        if sub.notification_type_id == ADMIN_EVENT_SUMMARY_NOTIFICATION_TYPE_ID:
            self._require_admin_summary_enabled(db_session, user_id)

        active = update_notification_subscription_request.active
        if sub.notification_type_id == ANNOUNCEMENTS_NOTIFICATION_TYPE_ID:
            user = db_session.get(AppUser, user_id)
            sync_announcements(user.email, subscribe=active, subscription_id=sub.id)

        sub.active = active
        db_session.flush()
        return NotificationSubscriptionImpl.from_orm(sub)

    @with_users_db_session
    def delete_user_subscription(self, id: str, db_session=None) -> None:
        """Removes a notification subscription by ID.

        The announcements subscription cannot be deleted; it is disabled instead.
        """
        user_id = self._require_user_id()
        sub = self._get_owned_subscription(db_session, id, user_id)

        if sub.notification_type_id == ANNOUNCEMENTS_NOTIFICATION_TYPE_ID:
            email = db_session.get(AppUser, user_id).email
            # Release the pooled DB connection before the (potentially slow) Brevo call so a slow
            # or unreachable provider never holds a connection while we talk to it. The reads above
            # took no row locks, so committing here only returns the connection to the pool.
            db_session.commit()
            sync_announcements(email, subscribe=False)
            sub.active = False
        else:
            db_session.delete(sub)
        db_session.flush()

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _require_user_id() -> str:
        context = get_request_context()
        user_id = context.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Unable to determine user identity from token.")
        if context.get("is_guest"):
            raise HTTPException(status_code=403, detail="Guest users cannot perform this action.")
        return user_id

    @classmethod
    def _require_notifications_enabled(cls, db_session, user_id: str) -> None:
        """Gate: only users with the ``isNotificationEnabled`` feature flag may manage subscriptions.

        Raises 403 unless the flag resolves to true for this user.
        """
        if not cls._feature_flag_enabled(db_session, user_id, NOTIFICATIONS_FEATURE_FLAG_ID):
            raise HTTPException(status_code=403, detail="Notifications are not enabled for this user.")

    @classmethod
    def _require_admin_summary_enabled(cls, db_session, user_id: str) -> None:
        """Gate: the ``admin.event_summary`` type additionally requires ``isAdminSummarySubscriptionEnabled``.

        Layered on top of the general notifications gate. Raises 403 unless the flag resolves to
        true for this user.
        """
        if not cls._feature_flag_enabled(db_session, user_id, ADMIN_SUMMARY_FEATURE_FLAG_ID):
            raise HTTPException(
                status_code=403,
                detail=f"The '{ADMIN_EVENT_SUMMARY_NOTIFICATION_TYPE_ID}' subscription is not enabled for this user.",
            )

    @staticmethod
    def _feature_flag_enabled(db_session, user_id: str, flag_id: str) -> bool:
        """Resolve a boolean feature flag for a user.

        A globally disabled or missing flag denies everyone; otherwise the user's override wins,
        falling back to the flag's default value.
        """
        flag = db_session.get(FeatureFlag, flag_id)
        if flag is None or flag.disabled:
            return False
        override = db_session.get(UserFeatureFlag, (user_id, flag_id))
        value = override.value if override is not None and override.value is not None else flag.default_value
        return value is True

    @staticmethod
    def _sync_subscription_feeds(sub: NotificationSubscriptionOrm, feed_ids: List[str]) -> None:
        """Make the subscription's feed set exactly ``feed_ids``.

        Relies on the ``delete-orphan`` cascade configured on
        ``NotificationSubscription.notification_subscription_feeds`` (see
        ``shared.database.users_database``): removing a row from the collection deletes it and
        appending one inserts it on flush.
        """
        desired = set(feed_ids)
        current = {row.feed_stable_id: row for row in sub.notification_subscription_feeds}

        for stable_id, row in current.items():
            if stable_id not in desired:
                sub.notification_subscription_feeds.remove(row)

        for stable_id in feed_ids:
            if stable_id not in current:
                sub.notification_subscription_feeds.append(NotificationSubscriptionFeedOrm(feed_stable_id=stable_id))

    @staticmethod
    def _get_owned_subscription(db_session, sub_id: str, user_id: str) -> NotificationSubscriptionOrm:
        sub = db_session.get(NotificationSubscriptionOrm, sub_id)
        if sub is None or sub.user_id != user_id:
            raise HTTPException(status_code=404, detail="Subscription not found.")
        return sub
