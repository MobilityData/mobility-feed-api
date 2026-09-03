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
from shared.common.early_access import apply_invited_email_grants
from shared.database.database import generate_unique_id
from shared.database.users_database import with_users_db_session
from shared.db_models.app_user_impl import AppUserImpl
from user_service.impl.identity import require_user_id
from shared.db_models.notification_subscription_impl import NotificationSubscriptionImpl
from shared.db_models.subscription_feed_group_impl import SubscriptionFeedGroupImpl
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
    ERROR_MESSAGE_USER_FEATURE_NOT_ENABLED,
    FEED_SCOPED_NOTIFICATION_TYPE_IDS,
    NOTIFICATIONS_FEATURE_FLAG_ID,
    feature_flag_enabled,
    find_unknown_feed_ids,
    resolve_feed_metadata,
    set_announcements_optin,
)
from user_service_gen.apis.users_api_base import BaseUsersApi
from user_service_gen.models.create_notification_subscription_request import (
    CreateNotificationSubscriptionRequest,
)
from user_service_gen.models.notification_subscription import NotificationSubscription
from user_service_gen.models.subscription_feed_group import SubscriptionFeedGroup
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

            # Only fires on account creation: the CSV import grants a matching existing account
            # immediately at import time, so an invite row only exists for someone who had no
            # account yet, and their first sign-in (right above) is the only place it can be
            # claimed. SAVEPOINT + broad except: this is the most-called endpoint in the service
            # and must never 500 because a program row is malformed.
            if user.email:
                try:
                    with db_session.begin_nested():
                        apply_invited_email_grants(user_id, user.email, db_session)
                except Exception:
                    logger.exception(
                        "Early access invite claim failed for user_id=%s; continuing without it.",
                        user_id,
                    )

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

        # Detect a real change to the announcements opt-in so we can reconcile the
        # subscription + Brevo membership below. Writing the boolean alone would
        # leave the DB flag, the notification_subscription row, and Brevo out of
        # sync (the historical bug this closes). Only act on an actual change so
        # unrelated profile edits never make a (slow, failable) Brevo call.
        optin_field = "is_registered_to_receive_api_announcements"
        optin_target = None
        if optin_field in update_data:
            new_value = bool(update_data[optin_field])
            if new_value != bool(user.is_registered_to_receive_api_announcements):
                optin_target = new_value

        for field, value in update_data.items():
            setattr(user, field, value)
        user.updated_at = datetime.now(timezone.utc)

        if optin_target is not None:
            # Holds the DB connection through the Brevo call so the profile write
            # and the opt-in change commit (or roll back on a 502) atomically.
            set_announcements_optin(db_session, user, subscribe=optin_target)

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
        # Resolve feed metadata for every targeted feed in a single feeds-DB query (skipped
        # entirely when the user has no feed-scoped subscriptions).
        stable_ids = [f.feed_stable_id for s in subs for f in s.notification_subscription_feeds]
        feed_metadata = resolve_feed_metadata(stable_ids) if stable_ids else {}
        return [NotificationSubscriptionImpl.from_orm(s, feed_metadata) for s in subs]

    @with_users_db_session
    def get_user_subscription_feeds(self, db_session=None) -> List[SubscriptionFeedGroup]:
        """Returns the feeds the authenticated user has at least one subscription targeting,
        each with the subscriptions that target it."""
        user_id = self._require_user_id()
        return self._query_subscription_feed_groups(db_session, user_id)

    @with_users_db_session
    def get_user_subscription_feed_by_id(self, id: str, db_session=None) -> SubscriptionFeedGroup:
        """Returns the authenticated user's subscriptions targeting a single feed stable ID.

        404 collapses "feed doesn't exist" and "user has no subscription targeting it" into one
        condition (no matching join rows), so no separate feeds-DB existence check is needed.
        """
        user_id = self._require_user_id()
        groups = self._query_subscription_feed_groups(db_session, user_id, feed_stable_id=id)
        if not groups:
            raise HTTPException(status_code=404, detail="Feed not found, or no subscription targets it.")
        return groups[0]

    @staticmethod
    def _query_subscription_feed_groups(
        db_session, user_id: str, feed_stable_id: str = None
    ) -> List[SubscriptionFeedGroup]:
        query = (
            db_session.query(NotificationSubscriptionFeedOrm, NotificationSubscriptionOrm)
            .join(
                NotificationSubscriptionOrm,
                NotificationSubscriptionFeedOrm.subscription_id == NotificationSubscriptionOrm.id,
            )
            .filter(NotificationSubscriptionOrm.user_id == user_id)
        )
        if feed_stable_id is not None:
            query = query.filter(NotificationSubscriptionFeedOrm.feed_stable_id == feed_stable_id)
        rows = query.order_by(
            NotificationSubscriptionFeedOrm.feed_stable_id, NotificationSubscriptionOrm.created_at
        ).all()

        grouped: dict[str, list[NotificationSubscriptionOrm]] = {}
        for feed_row, sub in rows:
            grouped.setdefault(feed_row.feed_stable_id, []).append(sub)

        feed_metadata = resolve_feed_metadata(list(grouped.keys())) if grouped else {}
        return [
            SubscriptionFeedGroupImpl.from_subscriptions(stable_id, subs, feed_metadata)
            for stable_id, subs in grouped.items()
        ]

    @with_users_db_session
    def create_user_subscription(
        self, create_notification_subscription_request: CreateNotificationSubscriptionRequest, db_session=None
    ) -> NotificationSubscription:
        """Subscribes the authenticated user to a notification type (idempotent).

        For feed-scoped notification types (``feed.url_updated``, ``feed.url_availability``,
        ``feed.coverage``) a non-empty ``feed_ids`` list is required and is persisted in the
        ``notification_subscription_feed`` join table; the supplied feeds are merged into the
        single (user, type) subscription's existing feed set (union), not a replacement, so
        callers don't need to know which feeds the user is already subscribed to. ``feed_ids``
        must not be supplied for other notification types. To remove specific feeds, use
        ``update_user_subscription``'s ``remove_feed_ids``.
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

        # Every supplied feed must exist (feeds live in a separate DB, referenced by stable_id).
        if feed_ids:
            unknown_feed_ids = find_unknown_feed_ids(feed_ids)
            if unknown_feed_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown feed stable IDs: {', '.join(unknown_feed_ids)}.",
                )

        user = db_session.get(AppUser, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")

        if notification_id == ANNOUNCEMENTS_NOTIFICATION_TYPE_ID:
            # Reconcile the subscription row, Brevo membership and the app_user
            # opt-in flag together so all three stay consistent.
            sub = set_announcements_optin(db_session, user, subscribe=True)
        else:
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
            # Merge the supplied feeds into the subscription's existing feed set (no-op for
            # non feed-scoped types, whose feed_ids is always empty here).
            self._add_subscription_feeds(sub, feed_ids)
            if existing is None:
                db_session.add(sub)

        db_session.flush()
        stable_ids = [f.feed_stable_id for f in sub.notification_subscription_feeds]
        feed_metadata = resolve_feed_metadata(stable_ids) if stable_ids else {}
        return NotificationSubscriptionImpl.from_orm(sub, feed_metadata)

    @with_users_db_session
    def update_user_subscription(
        self, id: str, update_notification_subscription_request: UpdateNotificationSubscriptionRequest, db_session=None
    ) -> NotificationSubscription:
        """Activates or deactivates a notification subscription by ID, and/or removes specific
        feeds from a feed-scoped subscription via ``remove_feed_ids``.

        To add feeds instead, call ``create_user_subscription`` (POST), which merges into the
        existing feed set. A feed-scoped subscription can't exist with no feeds, so removing
        the last remaining feed deletes the subscription entirely (same as
        ``delete_user_subscription``); the response reflects the subscription's final state.
        """
        user_id = self._require_user_id()
        self._require_notifications_enabled(db_session, user_id)
        sub = self._get_owned_subscription(db_session, id, user_id)

        # Managing an admin.event_summary subscription requires the additional admin flag.
        if sub.notification_type_id == ADMIN_EVENT_SUMMARY_NOTIFICATION_TYPE_ID:
            self._require_admin_summary_enabled(db_session, user_id)

        remove_feed_ids = list(dict.fromkeys(update_notification_subscription_request.remove_feed_ids or []))
        if remove_feed_ids:
            if sub.notification_type_id not in FEED_SCOPED_NOTIFICATION_TYPE_IDS:
                raise HTTPException(
                    status_code=400,
                    detail=f"remove_feed_ids is not supported for notification type '{sub.notification_type_id}'.",
                )
            self._remove_subscription_feeds(sub, remove_feed_ids)
            if not sub.notification_subscription_feeds:
                result = NotificationSubscriptionImpl.from_orm(sub, {})
                db_session.delete(sub)
                db_session.flush()
                return result

        active = update_notification_subscription_request.active
        if active is not None:
            if sub.notification_type_id == ANNOUNCEMENTS_NOTIFICATION_TYPE_ID:
                user = db_session.get(AppUser, user_id)
                set_announcements_optin(db_session, user, subscribe=active, subscription=sub)
            else:
                sub.active = active
        db_session.flush()
        stable_ids = [f.feed_stable_id for f in sub.notification_subscription_feeds]
        feed_metadata = resolve_feed_metadata(stable_ids) if stable_ids else {}
        return NotificationSubscriptionImpl.from_orm(sub, feed_metadata)

    @with_users_db_session
    def delete_user_subscription(self, id: str, db_session=None) -> None:
        """Removes a notification subscription by ID.

        The announcements subscription cannot be deleted; it is disabled instead.
        """
        user_id = self._require_user_id()
        self._require_notifications_enabled(db_session, user_id)
        sub = self._get_owned_subscription(db_session, id, user_id)

        if sub.notification_type_id == ANNOUNCEMENTS_NOTIFICATION_TYPE_ID:
            user = db_session.get(AppUser, user_id)
            # release_connection_before_brevo=True: only reads happened above, so
            # committing just returns the pooled connection before the (possibly
            # slow) Brevo call. Also clears the app_user opt-in flag.
            set_announcements_optin(
                db_session,
                user,
                subscribe=False,
                subscription=sub,
                release_connection_before_brevo=True,
            )
        else:
            db_session.delete(sub)
        db_session.flush()

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _require_user_id() -> str:
        return require_user_id()

    @classmethod
    def _require_notifications_enabled(cls, db_session, user_id: str) -> None:
        """Gate: only users with the ``isNotificationsEnabled`` feature flag may manage subscriptions.

        Raises 403 unless the flag resolves to true for this user.
        """
        if not feature_flag_enabled(db_session, user_id, NOTIFICATIONS_FEATURE_FLAG_ID):
            logger.info(
                "Subscription action denied for user %s: feature flag %r not enabled.",
                user_id,
                NOTIFICATIONS_FEATURE_FLAG_ID,
            )
            raise HTTPException(status_code=403, detail=ERROR_MESSAGE_USER_FEATURE_NOT_ENABLED)

    @classmethod
    def _require_admin_summary_enabled(cls, db_session, user_id: str) -> None:
        """Gate: the ``admin.event_summary`` type additionally requires ``isAdminSummarySubscriptionEnabled``.

        Layered on top of the general notifications gate. Raises 403 unless the flag resolves to
        true for this user.
        """
        if not feature_flag_enabled(db_session, user_id, ADMIN_SUMMARY_FEATURE_FLAG_ID):
            logger.info(
                "Subscription action denied for user %s: feature flag %r not enabled.",
                user_id,
                ADMIN_SUMMARY_FEATURE_FLAG_ID,
            )
            raise HTTPException(
                status_code=403,
                detail=ERROR_MESSAGE_USER_FEATURE_NOT_ENABLED,
            )

    @staticmethod
    def _add_subscription_feeds(sub: NotificationSubscriptionOrm, feed_ids: List[str]) -> None:
        """Merge ``feed_ids`` into the subscription's feed set (union; no-op for IDs already present).

        Appending to ``NotificationSubscription.notification_subscription_feeds`` (see
        ``shared.database.users_database``) inserts the row on flush.
        """
        current = {row.feed_stable_id for row in sub.notification_subscription_feeds}
        for stable_id in feed_ids:
            if stable_id not in current:
                sub.notification_subscription_feeds.append(NotificationSubscriptionFeedOrm(feed_stable_id=stable_id))

    @staticmethod
    def _remove_subscription_feeds(sub: NotificationSubscriptionOrm, feed_ids: List[str]) -> None:
        """Remove ``feed_ids`` from the subscription's feed set (no-op for IDs not present).

        Relies on the ``delete-orphan`` cascade configured on
        ``NotificationSubscription.notification_subscription_feeds`` (see
        ``shared.database.users_database``): removing a row from the collection deletes it on flush.
        """
        to_remove = set(feed_ids)
        for row in list(sub.notification_subscription_feeds):
            if row.feed_stable_id in to_remove:
                sub.notification_subscription_feeds.remove(row)

    @staticmethod
    def _get_owned_subscription(db_session, sub_id: str, user_id: str) -> NotificationSubscriptionOrm:
        sub = db_session.get(NotificationSubscriptionOrm, sub_id)
        if sub is None or sub.user_id != user_id:
            raise HTTPException(status_code=404, detail="Subscription not found.")
        return sub
