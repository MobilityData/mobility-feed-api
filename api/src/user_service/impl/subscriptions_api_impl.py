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
from typing import Final

from fastapi import HTTPException

from shared.database.users_database import with_users_db_session
from shared.db_models.notification_subscription_impl import NotificationSubscriptionImpl
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    NotificationSubscription as NotificationSubscriptionOrm,
)
from user_service.impl.subscription_helpers import (
    ANNOUNCEMENTS_NOTIFICATION_TYPE_ID,
    ERROR_MESSAGE_USER_FEATURE_NOT_ENABLED,
    NOTIFICATIONS_FEATURE_FLAG_ID,
    feature_flag_enabled,
    resolve_feed_metadata,
    set_announcements_optin,
)
from user_service_gen.apis.subscriptions_api_base import BaseSubscriptionsApi
from user_service_gen.models.notification_subscription import NotificationSubscription

logger = logging.getLogger(__name__)

# Values of the ?scope query parameter on DELETE /v1/subscriptions/{id}.
SCOPE_ONE: Final = "one"
SCOPE_ALL: Final = "all"


class SubscriptionsApiImpl(BaseSubscriptionsApi):
    """Subscription management keyed on the subscription ID, with no end-user auth.

    The subscription UUID (``notification_subscription.id``) is the access
    capability; these methods never read the request context.
    """

    @with_users_db_session
    def get_subscription(self, id: str, db_session=None) -> NotificationSubscription:
        sub = db_session.get(NotificationSubscriptionOrm, id)
        if sub is None:
            raise HTTPException(status_code=404, detail="Subscription not found.")
        stable_ids = [f.feed_stable_id for f in sub.notification_subscription_feeds]
        feed_metadata = resolve_feed_metadata(stable_ids) if stable_ids else {}
        return NotificationSubscriptionImpl.from_orm(sub, feed_metadata)

    @with_users_db_session
    def delete_subscription(self, id: str, scope: str = None, db_session=None) -> None:
        """Unsubscribe by subscription ID.

        ``scope='all'`` uses ``id`` only to resolve the owning user and
        unsubscribes that user from every notification type they hold.
        ``scope='one'`` (the default) affects just the subscription identified by
        ``id``. Any other value is rejected with a 400 rather than silently
        falling back to ``'one'``, since a typo here changes the blast radius of
        an unauthenticated delete.

        In both cases the ``api.announcements`` subscription is never deleted, only
        disabled (and its Brevo contact + opt-in flag are cleared); every other
        type is hard-deleted.
        """
        if scope is not None and scope not in (SCOPE_ONE, SCOPE_ALL):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid scope '{scope}'; must be '{SCOPE_ONE}' or '{SCOPE_ALL}'.",
            )

        sub = db_session.get(NotificationSubscriptionOrm, id)
        if sub is None:
            raise HTTPException(status_code=404, detail="Subscription not found.")

        # Gated by the subscription owner's isNotificationsEnabled flag (this endpoint is
        # unauthenticated; the subscription UUID is the capability, so we resolve the flag for
        # the subscription's owner rather than a request user).
        if not feature_flag_enabled(db_session, sub.user_id, NOTIFICATIONS_FEATURE_FLAG_ID):
            logger.info(
                "Public delete denied for subscription %s (owner %s): feature flag %r not enabled.",
                id,
                sub.user_id,
                NOTIFICATIONS_FEATURE_FLAG_ID,
            )
            raise HTTPException(status_code=403, detail=ERROR_MESSAGE_USER_FEATURE_NOT_ENABLED)

        if scope == SCOPE_ALL:
            subscriptions = (
                db_session.query(NotificationSubscriptionOrm)
                .filter(NotificationSubscriptionOrm.user_id == sub.user_id)
                .all()
            )
            # Keep the whole batch in one transaction: release_connection_before_brevo
            # stays False so a Brevo failure on the announcements row rolls back every
            # deletion in this call instead of leaving the user half-unsubscribed.
            for subscription in subscriptions:
                self._unsubscribe(db_session, subscription, release_connection_before_brevo=False)
        else:
            # Single unsubscribe: only reads happened above, so the announcements
            # path can commit and release the pooled connection before the
            # (possibly slow) Brevo call.
            self._unsubscribe(db_session, sub, release_connection_before_brevo=True)

        db_session.flush()

    @staticmethod
    def _unsubscribe(
        db_session,
        sub: NotificationSubscriptionOrm,
        *,
        release_connection_before_brevo: bool,
    ) -> None:
        """Disable-and-sync an ``api.announcements`` subscription, or hard-delete any other type."""
        if sub.notification_type_id == ANNOUNCEMENTS_NOTIFICATION_TYPE_ID:
            user = db_session.get(AppUser, sub.user_id)
            if user is not None:
                set_announcements_optin(
                    db_session,
                    user,
                    subscribe=False,
                    subscription=sub,
                    release_connection_before_brevo=release_connection_before_brevo,
                )
            else:
                # Orphaned subscription (no owning user): just disable it.
                sub.active = False
        else:
            db_session.delete(sub)
