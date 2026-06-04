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

from fastapi import HTTPException

from user_service_gen.apis.notifications_api_base import BaseNotificationsApi
from user_service_gen.models.notification_type import NotificationType

_NOT_IMPLEMENTED = "Not yet implemented."


class NotificationsApiImpl(BaseNotificationsApi):
    """Stub implementation — scheduled for a follow-up issue."""

    def get_notifications(self) -> List[NotificationType]:
        raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)
