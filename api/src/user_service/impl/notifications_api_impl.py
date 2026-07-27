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

from shared.database.users_database import with_users_db_session
from shared.db_models.notification_type_impl import NotificationTypeImpl
from shared.users_database_gen.sqlacodegen_models import NotificationType as NotificationTypeOrm
from user_service_gen.apis.notifications_api_base import BaseNotificationsApi
from user_service_gen.models.notification_type import NotificationType


class NotificationsApiImpl(BaseNotificationsApi):
    """Implementation of the User Service notifications API."""

    @with_users_db_session
    def get_notifications(self, db_session=None) -> List[NotificationType]:
        """Returns all predefined notification types users can subscribe to, ordered by id."""
        types = db_session.query(NotificationTypeOrm).order_by(NotificationTypeOrm.id).all()
        return [NotificationTypeImpl.from_orm(t) for t in types]
