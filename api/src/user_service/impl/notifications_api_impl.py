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
from typing import List

from middleware.request_context import get_request_context
from shared.database.users_database import with_users_db_session
from shared.db_models.notification_type_impl import NotificationTypeImpl
from shared.users_database_gen.sqlacodegen_models import NotificationType as NotificationTypeOrm
from user_service.impl.subscription_helpers import (
    ADMIN_EVENT_SUMMARY_NOTIFICATION_TYPE_ID,
    ADMIN_SUMMARY_FEATURE_FLAG_ID,
    feature_flag_enabled,
)
from user_service_gen.apis.notifications_api_base import BaseNotificationsApi
from user_service_gen.models.notification_type import NotificationType


class NotificationsApiImpl(BaseNotificationsApi):
    """Implementation of the User Service notifications API."""

    @with_users_db_session
    def get_notifications(self, db_session=None) -> List[NotificationType]:
        """Returns the notification types the caller can subscribe to, ordered by id.

        ``admin.event_summary`` is only included for users with the
        ``isAdminSummarySubscriptionEnabled`` flag, mirroring the create/update gate.
        """
        types = db_session.query(NotificationTypeOrm).order_by(NotificationTypeOrm.id).all()

        user_id = get_request_context().get("user_id")
        if not (user_id and feature_flag_enabled(db_session, user_id, ADMIN_SUMMARY_FEATURE_FLAG_ID)):
            types = [t for t in types if t.id != ADMIN_EVENT_SUMMARY_NOTIFICATION_TYPE_ID]

        return [NotificationTypeImpl.from_orm(t) for t in types]
