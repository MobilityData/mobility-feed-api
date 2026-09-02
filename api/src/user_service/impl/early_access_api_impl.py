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
from sqlalchemy.orm import selectinload

from middleware.request_context import get_request_context
from shared.common.early_access import guest_no_early_access
from shared.database.users_database import with_users_db_session
from shared.db_models.early_access_impl import EarlyAccessImpl
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    EarlyAccessEnrollment,
    EarlyAccessProgram,
    EarlyAccessProgramFeatureFlag,
)
from user_service_gen.apis.early_access_api_base import BaseEarlyAccessApi
from user_service_gen.models.early_access_grant import EarlyAccessGrant


class EarlyAccessApiImpl(BaseEarlyAccessApi):
    """Implementation of the User Service early-access API.

    Thin by design: identity, a single eager-loaded query, model conversion. There is no join
    endpoint here — enrollment is driven entirely by the operations CSV import (see
    EARLY-ACCESS-PLAN.md).
    """

    @with_users_db_session
    def get_user_early_access(self, db_session=None) -> List[EarlyAccessGrant]:
        context = get_request_context()
        user_id: str | None = context.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Unable to determine user identity from token.")
        if context.get("is_guest"):
            raise HTTPException(status_code=403, detail=guest_no_early_access)

        user = (
            db_session.query(AppUser)
            .options(
                selectinload(AppUser.user_feature_flags),
                selectinload(AppUser.early_access_enrollments)
                .selectinload(EarlyAccessEnrollment.program)
                .selectinload(EarlyAccessProgram.early_access_program_feature_flags)
                .selectinload(EarlyAccessProgramFeatureFlag.feature_flag),
            )
            .filter_by(id=user_id)
            .first()
        )
        return EarlyAccessImpl.from_orm(user)
