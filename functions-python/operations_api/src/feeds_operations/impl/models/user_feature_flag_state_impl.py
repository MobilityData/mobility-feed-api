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

from feeds_gen.models.user_feature_flag_state import UserFeatureFlagState
from shared.users_database_gen.sqlacodegen_models import UserFeatureFlag


class UserFeatureFlagStateImpl(UserFeatureFlagState):
    """Converts a UserFeatureFlag ORM row (with loaded feature_flag) to UserFeatureFlagState."""

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, uff: UserFeatureFlag | None) -> UserFeatureFlagState | None:
        if not uff:
            return None
        return cls(
            feature_flag_id=uff.feature_flag_id,
            name=uff.feature_flag.name,
            value_type=uff.feature_flag.value_type,
            default_value=uff.feature_flag.default_value,
            user_value=uff.value,
        )
