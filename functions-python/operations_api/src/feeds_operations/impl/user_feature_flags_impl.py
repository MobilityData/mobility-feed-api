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
from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from feeds_gen.apis.users_api_base import BaseUsersApi
from feeds_gen.models.create_feature_flag_request import CreateFeatureFlagRequest
from feeds_gen.models.get_operations_users200_response import (
    GetOperationsUsers200Response,
)
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
    UserFeatureFlag,
)

logger = logging.getLogger(__name__)

_USER_FLAGS_LOAD = selectinload(AppUser.user_feature_flags).selectinload(
    UserFeatureFlag.feature_flag
)

# Maps a flag's value_type to the JSON/Python type(s) its value must have.
_VALUE_TYPE_LABELS = {
    "boolean": "a boolean",
    "string": "a string",
    "numeric": "a number",
    "array": "an array",
    "json": "an object",
}


def _validate_value_type(value_type: str, value) -> None:
    """Ensures `value` is compatible with the declared `value_type`.

    Raises HTTPException(422) when the value's shape does not match the type.
    """
    if value_type == "boolean":
        ok = isinstance(value, bool)
    elif value_type == "string":
        ok = isinstance(value, str)
    elif value_type == "numeric":
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif value_type == "array":
        ok = isinstance(value, list)
    elif value_type == "json":
        ok = isinstance(value, dict)
    else:
        ok = False

    if not ok:
        raise HTTPException(
            status_code=422,
            detail=(
                f"default_value does not match value_type '{value_type}': "
                f"expected {_VALUE_TYPE_LABELS.get(value_type, 'a valid value')}."
            ),
        )


class UserFeatureFlagsApiImpl(BaseUsersApi):
    """Implementation of the Operations users/feature-flags API."""

    @with_users_db_session
    def get_operations_users(
        self,
        search_query: Optional[str] = None,
        limit: Optional[int] = 100,
        offset: Optional[int] = 0,
        db_session=None,
    ) -> GetOperationsUsers200Response:
        limit = limit or 100
        offset = offset or 0
        q = db_session.query(AppUser).options(_USER_FLAGS_LOAD)
        if search_query:
            pattern = f"%{search_query}%"
            q = q.filter(
                or_(
                    AppUser.email.ilike(pattern),
                    AppUser.full_name.ilike(pattern),
                    AppUser.legacy_org_name.ilike(pattern),
                )
            )
        total = q.order_by(None).count()
        users = q.order_by(AppUser.email).offset(offset).limit(limit).all()
        all_flags = db_session.query(FeatureFlagORM).order_by(FeatureFlagORM.id).all()
        return GetOperationsUsers200Response(
            total=total,
            offset=offset,
            limit=limit,
            users=[OperationUserProfileImpl.from_orm(u, all_flags) for u in users],
        )

    @with_users_db_session
    def get_operations_user(
        self, user_id: str, db_session=None
    ) -> OperationUserProfile:
        user = (
            db_session.query(AppUser)
            .options(_USER_FLAGS_LOAD)
            .filter_by(id=user_id)
            .first()
        )
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        all_flags = db_session.query(FeatureFlagORM).order_by(FeatureFlagORM.id).all()
        return OperationUserProfileImpl.from_orm(user, all_flags)

    @with_users_db_session
    def list_feature_flags(self, db_session=None) -> List[OperationFeatureFlag]:
        flags = db_session.query(FeatureFlagORM).order_by(FeatureFlagORM.id).all()
        return [OperationFeatureFlagImpl.from_orm(f) for f in flags]

    @with_users_db_session
    def create_feature_flag(
        self, create_feature_flag_request: CreateFeatureFlagRequest, db_session=None
    ) -> OperationFeatureFlag:
        if db_session.get(FeatureFlagORM, create_feature_flag_request.id):
            raise HTTPException(
                status_code=409, detail="A feature flag with this ID already exists."
            )
        _validate_value_type(
            create_feature_flag_request.value_type,
            create_feature_flag_request.default_value,
        )
        flag = FeatureFlagORM(
            id=create_feature_flag_request.id,
            name=create_feature_flag_request.name,
            description=create_feature_flag_request.description,
            value_type=create_feature_flag_request.value_type,
            default_value=create_feature_flag_request.default_value,
            disabled=create_feature_flag_request.disabled or False,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(flag)
        db_session.flush()
        return OperationFeatureFlagImpl.from_orm(flag)

    @with_users_db_session
    def delete_feature_flag(self, id: str, db_session=None) -> None:
        flag = db_session.get(FeatureFlagORM, id)
        if not flag:
            raise HTTPException(status_code=404, detail="Feature flag not found.")
        db_session.delete(flag)
        db_session.flush()

    @with_users_db_session
    def update_feature_flag(
        self,
        id: str,
        update_feature_flag_request: UpdateFeatureFlagRequest,
        db_session=None,
    ) -> OperationFeatureFlag:
        flag = db_session.get(FeatureFlagORM, id)
        if not flag:
            raise HTTPException(status_code=404, detail="Feature flag not found.")
        update_data = update_feature_flag_request.model_dump(exclude_unset=True)
        # value_type is immutable; validate any new default_value against it.
        if "default_value" in update_data:
            _validate_value_type(flag.value_type, update_data["default_value"])
        for field, value in update_data.items():
            setattr(flag, field, value)
        db_session.flush()
        return OperationFeatureFlagImpl.from_orm(flag)

    @with_users_db_session
    def patch_user_feature_flags(
        self,
        user_id: str,
        patch_user_feature_flags_request: PatchUserFeatureFlagsRequest,
        db_session=None,
    ) -> OperationUserProfile:
        user = (
            db_session.query(AppUser)
            .options(_USER_FLAGS_LOAD)
            .filter_by(id=user_id)
            .first()
        )
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        assignments = patch_user_feature_flags_request.assignments or []
        flag_ids = [a.feature_flag_id for a in assignments]

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
        db_session.query(UserFeatureFlag).filter_by(user_id=user_id).delete()
        db_session.add_all(
            [
                UserFeatureFlag(
                    user_id=user_id,
                    feature_flag_id=a.feature_flag_id,
                    value=a.value,
                )
                for a in assignments
            ]
        )
        db_session.flush()

        # Reload to reflect the new state
        db_session.refresh(user)
        all_flags = db_session.query(FeatureFlagORM).order_by(FeatureFlagORM.id).all()
        return OperationUserProfileImpl.from_orm(user, all_flags)
