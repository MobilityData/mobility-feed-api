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

from feeds_gen.models.feature_flag_value import FeatureFlagValue
from feeds_gen.models.operation_feature_flag import OperationFeatureFlag
from shared.users_database_gen.sqlacodegen_models import FeatureFlag


class OperationFeatureFlagImpl(OperationFeatureFlag):
    """Converts a FeatureFlag ORM object to an OperationFeatureFlag Pydantic model."""

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, flag: FeatureFlag | None) -> OperationFeatureFlag | None:
        if not flag:
            return None
        return cls(
            id=flag.id,
            name=flag.name,
            description=flag.description,
            created_at=flag.created_at,
            value_type=flag.value_type,
            default_value=FeatureFlagValue(actual_instance=flag.default_value),
        )
