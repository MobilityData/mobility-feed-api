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

from fastapi import HTTPException

from shared.database.users_database import with_users_db_session
from shared.db_models.notification_subscription_impl import NotificationSubscriptionImpl
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    NotificationSubscription as NotificationSubscriptionOrm,
)
from user_service.impl.subscription_helpers import ANNOUNCEMENTS_NOTIFICATION_TYPE_ID, sync_announcements
from user_service_gen.apis.subscriptions_api_base import BaseSubscriptionsApi
from user_service_gen.models.notification_subscription import NotificationSubscription


class SubscriptionsApiImpl(BaseSubscriptionsApi):
    """Public, unauthenticated subscription management.

    The subscription UUID is the access capability
    """

    @with_users_db_session
    def get_subscription(self, id: str, db_session=None) -> NotificationSubscription:
        sub = db_session.get(NotificationSubscriptionOrm, id)
        if sub is None:
            raise HTTPException(status_code=404, detail="Subscription not found.")
        return NotificationSubscriptionImpl.from_orm(sub)

    @with_users_db_session
    def delete_subscription(self, id: str, db_session=None) -> None:
        sub = db_session.get(NotificationSubscriptionOrm, id)
        if sub is None:
            raise HTTPException(status_code=404, detail="Subscription not found.")

        if sub.notification_type_id == ANNOUNCEMENTS_NOTIFICATION_TYPE_ID:
            user = db_session.get(AppUser, sub.user_id)
            if user is not None:
                sync_announcements(user.email, subscribe=False)

        db_session.delete(sub)
        db_session.flush()
