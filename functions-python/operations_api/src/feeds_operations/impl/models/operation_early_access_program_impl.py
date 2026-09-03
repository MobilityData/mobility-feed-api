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

from feeds_gen.models.early_access_program_feature_flag_grant import (
    EarlyAccessProgramFeatureFlagGrant,
)
from feeds_gen.models.operation_early_access_program import OperationEarlyAccessProgram
from shared.users_database_gen.sqlacodegen_models import EarlyAccessProgram


class OperationEarlyAccessProgramImpl(OperationEarlyAccessProgram):
    """Converts an EarlyAccessProgram ORM object (with its feature flag grants) to an
    OperationEarlyAccessProgram Pydantic model."""

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(
        cls, program: EarlyAccessProgram | None
    ) -> OperationEarlyAccessProgram | None:
        if not program:
            return None
        return cls(
            id=program.id,
            name=program.name,
            description=program.description,
            disabled=program.disabled,
            invite_retention_days=program.invite_retention_days,
            created_at=program.created_at,
            created_by=program.created_by,
            feature_flags=[
                EarlyAccessProgramFeatureFlagGrant(
                    feature_flag_id=grant.feature_flag_id, value=grant.value
                )
                for grant in sorted(
                    program.early_access_program_feature_flags or [],
                    key=lambda grant: grant.feature_flag_id,
                )
            ],
        )
