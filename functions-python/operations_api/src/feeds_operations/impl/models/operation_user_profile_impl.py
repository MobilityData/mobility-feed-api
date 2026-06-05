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

from feeds_gen.models.operation_user_profile import OperationUserProfile
from feeds_operations.impl.models.operation_feature_flag_impl import (
    OperationFeatureFlagImpl,
)
from shared.users_database_gen.sqlacodegen_models import AppUser


class OperationUserProfileImpl(OperationUserProfile):
    """Converts an AppUser ORM object to an OperationUserProfile Pydantic model."""

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, user: AppUser | None) -> OperationUserProfile | None:
        if not user:
            return None
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            legacy_org_name=user.legacy_org_name,
            features=[
                OperationFeatureFlagImpl.from_orm(ff)
                for ff in (user.feature_flags or [])
            ],
        )
