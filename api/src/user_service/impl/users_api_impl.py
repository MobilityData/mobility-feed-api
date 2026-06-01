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

from middleware.request_context import get_request_context
from shared.database.users_database import with_users_db_session
from shared.db_models.app_user_impl import AppUserImpl
from shared.users_database_gen.sqlacodegen_models import AppUser
from user_service_gen.apis.users_api_base import BaseUsersApi
from user_service_gen.models.create_notification_subscription_request import CreateNotificationSubscriptionRequest
from user_service_gen.models.notification_subscription import NotificationSubscription
from user_service_gen.models.update_notification_subscription_request import UpdateNotificationSubscriptionRequest
from user_service_gen.models.update_user_request import UpdateUserRequest
from user_service_gen.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

_NOT_IMPLEMENTED = "Not yet implemented."


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
            logger.warning("Skipping user creation as guest users cannot create a profile. user_id=%s", user_id)
            return UserProfile.from_dict({"id": user_id, "email": "", "created_at": datetime.now(timezone.utc)})

        user = db_session.get(AppUser, user_id)
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

        return AppUserImpl.from_orm(user)

    @with_users_db_session
    def update_user(self, update_user_request: UpdateUserRequest, db_session=None) -> UserProfile:
        """
        Updates the authenticated user's mutable profile fields.
        Email is intentionally excluded (requires re-verification).
        Guest users cannot update their profile.
        """
        context = get_request_context()
        user_id: str | None = context.get("user_id")

        if not user_id:
            raise HTTPException(status_code=401, detail="Unable to determine user identity from token.")

        if context.get("is_guest"):
            raise HTTPException(status_code=403, detail="Guest users cannot update a profile.")

        user = db_session.get(AppUser, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")

        update_data = update_user_request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        user.updated_at = datetime.now(timezone.utc)
        db_session.flush()

        return AppUserImpl.from_orm(user)

    # ── Subscription stubs — implemented in a follow-up issue ────────────────

    def get_user_subscriptions(self) -> List[NotificationSubscription]:
        raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)

    def create_user_subscription(
        self, create_notification_subscription_request: CreateNotificationSubscriptionRequest
    ) -> NotificationSubscription:
        raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)

    def update_user_subscription(
        self, id: str, update_notification_subscription_request: UpdateNotificationSubscriptionRequest
    ) -> NotificationSubscription:
        raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)

    def delete_user_subscription(self, id: str) -> None:
        raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)
