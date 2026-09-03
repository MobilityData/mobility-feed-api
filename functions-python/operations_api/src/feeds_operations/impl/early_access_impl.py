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
"""Operations API for early access programs (product-tasks#213).

This is the only enrollment path in the system — there is no self-service join endpoint anywhere
in the public API.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from email_validator import EmailNotValidError, validate_email
from fastapi import HTTPException
from sqlalchemy import delete, func
from sqlalchemy.orm import selectinload

from feeds_gen.apis.early_access_api_base import BaseEarlyAccessApi
from feeds_gen.models.create_early_access_program_request import (
    CreateEarlyAccessProgramRequest,
)
from feeds_gen.models.early_access_enrollment import (
    EarlyAccessEnrollment as EarlyAccessEnrollmentModel,
)
from feeds_gen.models.early_access_import_category_summary import (
    EarlyAccessImportCategorySummary,
)
from feeds_gen.models.early_access_invalid_email_entry import (
    EarlyAccessInvalidEmailEntry,
)
from feeds_gen.models.early_access_invited_email import (
    EarlyAccessInvitedEmail as EarlyAccessInvitedEmailModel,
)
from feeds_gen.models.early_access_program_feature_flag_grant import (
    EarlyAccessProgramFeatureFlagGrant,
)
from feeds_gen.models.import_early_access_invited_emails_request import (
    ImportEarlyAccessInvitedEmailsRequest,
)
from feeds_gen.models.import_early_access_invited_emails_response import (
    ImportEarlyAccessInvitedEmailsResponse,
)
from feeds_gen.models.list_early_access_enrollments200_response import (
    ListEarlyAccessEnrollments200Response,
)
from feeds_gen.models.list_early_access_invited_emails200_response import (
    ListEarlyAccessInvitedEmails200Response,
)
from feeds_gen.models.list_early_access_programs200_response import (
    ListEarlyAccessPrograms200Response,
)
from feeds_gen.models.operation_early_access_program import OperationEarlyAccessProgram
from feeds_gen.models.put_early_access_program_feature_flags_request import (
    PutEarlyAccessProgramFeatureFlagsRequest,
)
from feeds_gen.models.remove_early_access_invited_emails_request import (
    RemoveEarlyAccessInvitedEmailsRequest,
)
from feeds_gen.models.remove_early_access_invited_emails_response import (
    RemoveEarlyAccessInvitedEmailsResponse,
)
from feeds_gen.models.update_early_access_program_request import (
    UpdateEarlyAccessProgramRequest,
)
from feeds_operations.impl.models.feature_flag_validation import validate_value_type
from feeds_operations.impl.models.operation_early_access_program_impl import (
    OperationEarlyAccessProgramImpl,
)
from shared.common.early_access import (
    early_access_program_not_found,
    grant_program_flags,
    unknown_feature_flags,
)
from shared.database.database import generate_unique_id
from shared.database.users_database import with_users_db_session
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    EarlyAccessEnrollment,
    EarlyAccessInvitedEmail,
    EarlyAccessProgram,
    EarlyAccessProgramFeatureFlag,
    FeatureFlag as FeatureFlagORM,
)

logger = logging.getLogger(__name__)

_PROGRAM_FLAGS_LOAD = selectinload(
    EarlyAccessProgram.early_access_program_feature_flags
)

# A sample, not the full list, is returned for every category except `invalid` (which the
# operator needs in full to fix and resubmit).
_SAMPLE_SIZE = 5


def _validate_window(program: EarlyAccessProgram) -> None:
    if program.starts_at and program.ends_at and program.ends_at <= program.starts_at:
        raise HTTPException(status_code=422, detail="ends_at must be after starts_at.")


def _dedupe_grants(
    grants: List[EarlyAccessProgramFeatureFlagGrant],
) -> List[EarlyAccessProgramFeatureFlagGrant]:
    """Keeps the last occurrence of each feature_flag_id (a client submitting the same id twice
    would otherwise violate the (program_id, feature_flag_id) primary key on flush)."""
    return list({grant.feature_flag_id: grant for grant in grants}.values())


def _validate_feature_flag_grants(
    db_session, grants: List[EarlyAccessProgramFeatureFlagGrant]
) -> None:
    if not grants:
        return
    flag_ids = [grant.feature_flag_id for grant in grants]
    value_type_by_id = {
        row.id: row.value_type
        for row in db_session.query(FeatureFlagORM.id, FeatureFlagORM.value_type)
        .filter(FeatureFlagORM.id.in_(flag_ids))
        .all()
    }
    missing = set(flag_ids) - value_type_by_id.keys()
    if missing:
        raise HTTPException(
            status_code=422,
            detail=unknown_feature_flags.format(", ".join(sorted(missing))),
        )
    for grant in grants:
        validate_value_type(value_type_by_id[grant.feature_flag_id], grant.value)


def _summary(emails: List[str]) -> EarlyAccessImportCategorySummary:
    return EarlyAccessImportCategorySummary(
        count=len(emails), sample=emails[:_SAMPLE_SIZE]
    )


class EarlyAccessApiImpl(BaseEarlyAccessApi):
    """Implementation of the Operations early-access-programs API."""

    @with_users_db_session
    def list_early_access_programs(
        self,
        limit: Optional[int] = 100,
        offset: Optional[int] = 0,
        db_session=None,
    ) -> ListEarlyAccessPrograms200Response:
        limit = limit or 100
        offset = offset or 0
        q = db_session.query(EarlyAccessProgram).options(_PROGRAM_FLAGS_LOAD)
        total = q.order_by(None).count()
        programs = (
            q.order_by(EarlyAccessProgram.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return ListEarlyAccessPrograms200Response(
            total=total,
            offset=offset,
            limit=limit,
            programs=[OperationEarlyAccessProgramImpl.from_orm(p) for p in programs],
        )

    @with_users_db_session
    def create_early_access_program(
        self,
        create_early_access_program_request: CreateEarlyAccessProgramRequest,
        db_session=None,
    ) -> OperationEarlyAccessProgram:
        req = create_early_access_program_request
        grants = _dedupe_grants(req.feature_flags or [])
        _validate_feature_flag_grants(db_session, grants)

        program = EarlyAccessProgram(
            id=generate_unique_id(),
            name=req.name,
            description=req.description,
            starts_at=req.starts_at,
            ends_at=req.ends_at,
            disabled=req.disabled or False,
            invite_retention_days=req.invite_retention_days or 90,
            created_at=datetime.now(timezone.utc),
        )
        _validate_window(program)
        db_session.add(program)
        db_session.flush()

        if grants:
            db_session.add_all(
                [
                    EarlyAccessProgramFeatureFlag(
                        program_id=program.id,
                        feature_flag_id=grant.feature_flag_id,
                        value=grant.value,
                    )
                    for grant in grants
                ]
            )
            db_session.flush()
            db_session.expire(program, ["early_access_program_feature_flags"])
        return OperationEarlyAccessProgramImpl.from_orm(program)

    @with_users_db_session
    def get_early_access_program(
        self, id: str, db_session=None
    ) -> OperationEarlyAccessProgram:
        program = (
            db_session.query(EarlyAccessProgram)
            .options(_PROGRAM_FLAGS_LOAD)
            .filter_by(id=id)
            .first()
        )
        if program is None:
            raise HTTPException(
                status_code=404, detail=early_access_program_not_found.format(id)
            )
        return OperationEarlyAccessProgramImpl.from_orm(program)

    @with_users_db_session
    def update_early_access_program(
        self,
        id: str,
        update_early_access_program_request: UpdateEarlyAccessProgramRequest,
        db_session=None,
    ) -> OperationEarlyAccessProgram:
        program = (
            db_session.query(EarlyAccessProgram)
            .options(_PROGRAM_FLAGS_LOAD)
            .filter_by(id=id)
            .first()
        )
        if program is None:
            raise HTTPException(
                status_code=404, detail=early_access_program_not_found.format(id)
            )

        update_data = update_early_access_program_request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(program, field, value)
        _validate_window(program)
        db_session.flush()
        return OperationEarlyAccessProgramImpl.from_orm(program)

    @with_users_db_session
    def delete_early_access_program(self, id: str, db_session=None) -> None:
        program = db_session.get(EarlyAccessProgram, id)
        if program is None:
            raise HTTPException(
                status_code=404, detail=early_access_program_not_found.format(id)
            )
        db_session.delete(program)
        db_session.flush()

    @with_users_db_session
    def put_early_access_program_feature_flags(
        self,
        id: str,
        put_early_access_program_feature_flags_request: PutEarlyAccessProgramFeatureFlagsRequest,
        db_session=None,
    ) -> OperationEarlyAccessProgram:
        program = db_session.get(EarlyAccessProgram, id)
        if program is None:
            raise HTTPException(
                status_code=404, detail=early_access_program_not_found.format(id)
            )

        grants = _dedupe_grants(
            put_early_access_program_feature_flags_request.feature_flags or []
        )
        _validate_feature_flag_grants(db_session, grants)

        # Replace: delete the program's current grant set, then insert the new one. This never
        # touches `user_feature_flag` rows already granted to existing enrollees — it only
        # changes what future enrollments and invite claims receive.
        db_session.query(EarlyAccessProgramFeatureFlag).filter_by(
            program_id=id
        ).delete()
        db_session.add_all(
            [
                EarlyAccessProgramFeatureFlag(
                    program_id=id,
                    feature_flag_id=grant.feature_flag_id,
                    value=grant.value,
                )
                for grant in grants
            ]
        )
        db_session.flush()
        db_session.expire(program, ["early_access_program_feature_flags"])
        return OperationEarlyAccessProgramImpl.from_orm(program)

    @with_users_db_session
    def list_early_access_enrollments(
        self,
        id: str,
        limit: Optional[int] = 100,
        offset: Optional[int] = 0,
        db_session=None,
    ) -> ListEarlyAccessEnrollments200Response:
        if db_session.get(EarlyAccessProgram, id) is None:
            raise HTTPException(
                status_code=404, detail=early_access_program_not_found.format(id)
            )
        limit = limit or 100
        offset = offset or 0
        q = (
            db_session.query(EarlyAccessEnrollment, AppUser.email)
            .join(AppUser, AppUser.id == EarlyAccessEnrollment.user_id)
            .filter(EarlyAccessEnrollment.program_id == id)
        )
        total = q.order_by(None).count()
        rows = (
            q.order_by(EarlyAccessEnrollment.enrolled_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return ListEarlyAccessEnrollments200Response(
            total=total,
            offset=offset,
            limit=limit,
            enrollments=[
                EarlyAccessEnrollmentModel(
                    id=enrollment.id,
                    user_id=enrollment.user_id,
                    email=email,
                    enrolled_at=enrollment.enrolled_at,
                    source=enrollment.source,
                )
                for enrollment, email in rows
            ],
        )

    @with_users_db_session
    def list_early_access_invited_emails(
        self,
        id: str,
        limit: Optional[int] = 100,
        offset: Optional[int] = 0,
        db_session=None,
    ) -> ListEarlyAccessInvitedEmails200Response:
        if db_session.get(EarlyAccessProgram, id) is None:
            raise HTTPException(
                status_code=404, detail=early_access_program_not_found.format(id)
            )
        limit = limit or 100
        offset = offset or 0
        q = db_session.query(EarlyAccessInvitedEmail).filter(
            EarlyAccessInvitedEmail.program_id == id
        )
        total = q.order_by(None).count()
        rows = (
            q.order_by(EarlyAccessInvitedEmail.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return ListEarlyAccessInvitedEmails200Response(
            total=total,
            offset=offset,
            limit=limit,
            invited_emails=[
                EarlyAccessInvitedEmailModel(
                    id=row.id,
                    email=row.email,
                    created_at=row.created_at,
                    created_by=row.created_by,
                )
                for row in rows
            ],
        )

    @with_users_db_session
    def import_early_access_invited_emails(
        self,
        id: str,
        import_early_access_invited_emails_request: ImportEarlyAccessInvitedEmailsRequest,
        db_session=None,
    ) -> ImportEarlyAccessInvitedEmailsResponse:
        if db_session.get(EarlyAccessProgram, id) is None:
            raise HTTPException(
                status_code=404, detail=early_access_program_not_found.format(id)
            )

        req = import_early_access_invited_emails_request
        dry_run = req.dry_run if req.dry_run is not None else True

        # Normalize (lower-case, strip, de-duplicate) and validate format. The cap at 5000 is
        # already enforced by the request schema (max_length) before this code runs.
        invalid: List[EarlyAccessInvalidEmailEntry] = []
        seen: set[str] = set()
        candidates: List[str] = []
        for raw in req.emails:
            candidate = (raw or "").strip().lower()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            try:
                validate_email(candidate, check_deliverability=False)
            except EmailNotValidError as error:
                invalid.append(
                    EarlyAccessInvalidEmailEntry(email=raw, reason=str(error))
                )
                continue
            candidates.append(candidate)

        # Case-insensitive match against app_user.email (idx_app_user_email_lower). Note:
        # app_user.email only carries a case-sensitive UNIQUE (feat_1683.sql) - two accounts
        # differing solely by case would collide here; this is a pre-existing data-quality edge
        # case, not introduced by this import.
        matched_by_email = {}
        if candidates:
            for row in (
                db_session.query(AppUser.id, AppUser.email)
                .filter(func.lower(AppUser.email).in_(candidates))
                .all()
            ):
                matched_by_email[row.email.lower()] = row.id

        already_invited_emails = set()
        if candidates:
            already_invited_emails = {
                row.email
                for row in db_session.query(EarlyAccessInvitedEmail.email)
                .filter(
                    EarlyAccessInvitedEmail.program_id == id,
                    EarlyAccessInvitedEmail.email.in_(candidates),
                )
                .all()
            }

        already_enrolled_user_ids = {
            row.user_id
            for row in db_session.query(EarlyAccessEnrollment.user_id)
            .filter(EarlyAccessEnrollment.program_id == id)
            .all()
        }

        matched_existing_account: List[str] = []
        no_account_yet: List[str] = []
        already_invited: List[str] = []
        already_enrolled: List[str] = []

        for email in candidates:
            user_id = matched_by_email.get(email)
            if user_id is not None and user_id in already_enrolled_user_ids:
                already_enrolled.append(email)
            elif user_id is not None:
                matched_existing_account.append(email)
            elif email in already_invited_emails:
                already_invited.append(email)
            else:
                no_account_yet.append(email)

        if not dry_run:
            now = datetime.now(timezone.utc)
            for email in matched_existing_account:
                user_id = matched_by_email[email]
                db_session.add(
                    EarlyAccessEnrollment(
                        id=generate_unique_id(),
                        program_id=id,
                        user_id=user_id,
                        enrolled_at=now,
                        source="operations",
                    )
                )
                grant_program_flags(user_id, id, db_session)
            db_session.add_all(
                [
                    EarlyAccessInvitedEmail(
                        id=generate_unique_id(),
                        program_id=id,
                        email=email,
                        created_at=now,
                    )
                    for email in no_account_yet
                ]
            )
            db_session.flush()
            logger.info(
                "early access program %s import applied: matched=%d no_account=%d "
                "already_invited=%d already_enrolled=%d invalid=%d",
                id,
                len(matched_existing_account),
                len(no_account_yet),
                len(already_invited),
                len(already_enrolled),
                len(invalid),
            )

        return ImportEarlyAccessInvitedEmailsResponse(
            program_id=id,
            dry_run=dry_run,
            matched_existing_account=_summary(matched_existing_account),
            no_account_yet=_summary(no_account_yet),
            already_invited=_summary(already_invited),
            already_enrolled=_summary(already_enrolled),
            invalid=invalid,
        )

    @with_users_db_session
    def remove_early_access_invited_emails(
        self,
        id: str,
        remove_early_access_invited_emails_request: RemoveEarlyAccessInvitedEmailsRequest,
        db_session=None,
    ) -> RemoveEarlyAccessInvitedEmailsResponse:
        if db_session.get(EarlyAccessProgram, id) is None:
            raise HTTPException(
                status_code=404, detail=early_access_program_not_found.format(id)
            )

        emails = {
            (email or "").strip().lower()
            for email in remove_early_access_invited_emails_request.emails
        }
        emails.discard("")
        if not emails:
            return RemoveEarlyAccessInvitedEmailsResponse(
                removed_count=0, not_found_count=0
            )

        removed = (
            db_session.execute(
                delete(EarlyAccessInvitedEmail)
                .where(
                    EarlyAccessInvitedEmail.program_id == id,
                    EarlyAccessInvitedEmail.email.in_(emails),
                )
                .returning(EarlyAccessInvitedEmail.email)
            )
            .scalars()
            .all()
        )
        db_session.flush()
        removed_count = len(removed)
        return RemoveEarlyAccessInvitedEmailsResponse(
            removed_count=removed_count,
            not_found_count=len(emails) - removed_count,
        )
