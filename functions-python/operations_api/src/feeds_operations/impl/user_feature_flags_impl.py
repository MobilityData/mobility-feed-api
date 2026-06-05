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
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import delete, insert, or_
from sqlalchemy.orm import selectinload

from feeds_gen.apis.users_api_base import BaseUsersApi
from feeds_gen.models.create_feature_flag_request import CreateFeatureFlagRequest
from feeds_gen.models.operation_feature_flag import OperationFeatureFlag
from feeds_gen.models.operation_user_profile import OperationUserProfile
from feeds_gen.models.patch_user_feature_flags_request import (
    PatchUserFeatureFlagsRequest,
)
from feeds_gen.models.update_feature_flag_request import UpdateFeatureFlagRequest
from feeds_operations.impl.models.operation_feature_flag_impl import (
    OperationFeatureFlagImpl,
)
from feeds_operations.impl.models.operation_user_profile_impl import (
    OperationUserProfileImpl,
)
from shared.database.users_database import with_users_db_session
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    FeatureFlag as FeatureFlagORM,
    t_user_feature_flag,
)

logger = logging.getLogger(__name__)


class UserFeatureFlagsApiImpl(BaseUsersApi):
    """Implementation of the Operations users/feature-flags API."""

    @with_users_db_session
    async def get_operations_users(
        self,
        search_query: Optional[str] = None,
        limit: Optional[int] = 100,
        offset: Optional[int] = 0,
        db_session=None,
    ) -> List[OperationUserProfile]:
        q = db_session.query(AppUser).options(selectinload(AppUser.feature_flags))
        if search_query:
            pattern = f"%{search_query}%"
            q = q.filter(
                or_(
                    AppUser.email.ilike(pattern),
                    AppUser.full_name.ilike(pattern),
                    AppUser.legacy_org_name.ilike(pattern),
                )
            )
        users = q.order_by(AppUser.email).offset(offset or 0).limit(limit or 100).all()
        return [OperationUserProfileImpl.from_orm(u) for u in users]

    @with_users_db_session
    async def get_operations_user(
        self, user_id: str, db_session=None
    ) -> OperationUserProfile:
        user = (
            db_session.query(AppUser)
            .options(selectinload(AppUser.feature_flags))
            .filter_by(id=user_id)
            .first()
        )
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        return OperationUserProfileImpl.from_orm(user)

    @with_users_db_session
    async def list_feature_flags(self, db_session=None) -> List[OperationFeatureFlag]:
        flags = db_session.query(FeatureFlagORM).order_by(FeatureFlagORM.id).all()
        return [OperationFeatureFlagImpl.from_orm(f) for f in flags]

    @with_users_db_session
    async def create_feature_flag(
        self, create_feature_flag_request: CreateFeatureFlagRequest, db_session=None
    ) -> OperationFeatureFlag:
        if db_session.get(FeatureFlagORM, create_feature_flag_request.id):
            raise HTTPException(
                status_code=409, detail="A feature flag with this ID already exists."
            )
        flag = FeatureFlagORM(
            id=create_feature_flag_request.id,
            name=create_feature_flag_request.name,
            description=create_feature_flag_request.description,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(flag)
        db_session.flush()
        return OperationFeatureFlagImpl.from_orm(flag)

    @with_users_db_session
    async def update_feature_flag(
        self,
        id: str,
        update_feature_flag_request: UpdateFeatureFlagRequest,
        db_session=None,
    ) -> OperationFeatureFlag:
        flag = db_session.get(FeatureFlagORM, id)
        if not flag:
            raise HTTPException(status_code=404, detail="Feature flag not found.")
        update_data = update_feature_flag_request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(flag, field, value)
        db_session.flush()
        return OperationFeatureFlagImpl.from_orm(flag)

    @with_users_db_session
    async def patch_user_feature_flags(
        self,
        user_id: str,
        patch_user_feature_flags_request: PatchUserFeatureFlagsRequest,
        db_session=None,
    ) -> OperationUserProfile:
        user = (
            db_session.query(AppUser)
            .options(selectinload(AppUser.feature_flags))
            .filter_by(id=user_id)
            .first()
        )
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        flag_ids = patch_user_feature_flags_request.feature_flag_ids or []

        # Validate all provided flag IDs exist before making any changes
        if flag_ids:
            existing_flags = (
                db_session.query(FeatureFlagORM.id)
                .filter(FeatureFlagORM.id.in_(flag_ids))
                .all()
            )
            found_ids = {row.id for row in existing_flags}
            missing = set(flag_ids) - found_ids
            if missing:
                raise HTTPException(
                    status_code=404,
                    detail=f"Feature flag(s) not found: {', '.join(sorted(missing))}",
                )

        # Replace: delete all existing assignments then insert the new set
        db_session.execute(
            delete(t_user_feature_flag).where(t_user_feature_flag.c.user_id == user_id)
        )
        if flag_ids:
            db_session.execute(
                insert(t_user_feature_flag),
                [
                    {
                        "user_id": user_id,
                        "feature_flag_id": fid,
                        "assigned_at": datetime.now(timezone.utc),
                    }
                    for fid in flag_ids
                ],
            )
        db_session.flush()

        # Reload to reflect the new state
        db_session.refresh(user)
        return OperationUserProfileImpl.from_orm(user)
