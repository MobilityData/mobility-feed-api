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
"""Operations API for early access programs. The only enrollment path: there is no
self-service join endpoint in the public API."""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from email_validator import EmailNotValidError, validate_email
from fastapi import HTTPException, Response
from sqlalchemy import delete, func
from sqlalchemy.orm import selectinload

from feeds_gen.apis.early_access_api_base import BaseEarlyAccessApi
from feeds_gen.models.create_early_access_program_request import (
    CreateEarlyAccessProgramRequest,
)
from feeds_gen.models.early_access_import_category_summary import (
    EarlyAccessImportCategorySummary,
)
from feeds_gen.models.early_access_invalid_email_entry import (
    EarlyAccessInvalidEmailEntry,
)
from feeds_gen.models.early_access_program_feature_flag_grant import (
    EarlyAccessProgramFeatureFlagGrant,
)
from feeds_gen.models.early_access_program_report import EarlyAccessProgramReport
from feeds_gen.models.early_access_report_row import EarlyAccessReportRow
from feeds_gen.models.early_access_report_summary import EarlyAccessReportSummary
from feeds_gen.models.early_access_report_summary_by_source import (
    EarlyAccessReportSummaryBySource,
)
from feeds_gen.models.import_early_access_invited_emails_request import (
    ImportEarlyAccessInvitedEmailsRequest,
)
from feeds_gen.models.import_early_access_invited_emails_response import (
    ImportEarlyAccessInvitedEmailsResponse,
)
from feeds_gen.models.list_early_access_programs200_response import (
    ListEarlyAccessPrograms200Response,
)
from feeds_gen.models.operation_early_access_program import OperationEarlyAccessProgram
from feeds_gen.models.remove_early_access_invited_emails_request import (
    RemoveEarlyAccessInvitedEmailsRequest,
)
from feeds_gen.models.remove_early_access_invited_emails_response import (
    RemoveEarlyAccessInvitedEmailsResponse,
)
from feeds_gen.models.update_early_access_program_request import (
    UpdateEarlyAccessProgramRequest,
)
from feeds_operations.impl.csv_utils import CSV_FORMAT, JSON_FORMAT, csv_response
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

# Every category returns a sample; only `invalid` is returned in full, for the operator to fix.
_SAMPLE_SIZE = 5

_STATUS_ENROLLED = "enrolled"
_STATUS_INVITED = "invited"

# Explicit, so adding a field to the row model cannot reorder a file someone already parses.
_REPORT_CSV_FIELDS = (
    "email",
    "status",
    "user_id",
    "enrolled_at",
    "source",
    "invited_at",
)


def _validate_format(format: Optional[str]) -> None:
    """The generated param is a plain `str`, so the spec's enum is not enforced for us."""
    if format is not None and format not in (JSON_FORMAT, CSV_FORMAT):
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported format '{format}'. Expected '{JSON_FORMAT}' or '{CSV_FORMAT}'.",
        )


def _validate_status(status: Optional[str]) -> None:
    """As _validate_format: the generated param is a plain `str`."""
    if status is not None and status not in (_STATUS_ENROLLED, _STATUS_INVITED):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unsupported status '{status}'. "
                f"Expected '{_STATUS_ENROLLED}' or '{_STATUS_INVITED}'."
            ),
        )


def _dedupe_grants(
    grants: List[EarlyAccessProgramFeatureFlagGrant],
) -> List[EarlyAccessProgramFeatureFlagGrant]:
    """Last occurrence wins; a repeated id would otherwise violate the composite primary key."""
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
            disabled=req.disabled or False,
            invite_retention_days=req.invite_retention_days or 90,
            created_at=datetime.now(timezone.utc),
        )
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

        # Own fields are a partial update; feature_flags is a full replace, handled below.
        update_data = update_early_access_program_request.model_dump(exclude_unset=True)
        update_data.pop("feature_flags", None)
        for field, value in update_data.items():
            setattr(program, field, value)

        grants = _dedupe_grants(update_early_access_program_request.feature_flags or [])
        _validate_feature_flag_grants(db_session, grants)

        # Full replace, so omitting feature_flags clears the set. Only affects what future
        # enrollments receive; never touches flags already granted to existing enrollees.
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
        # The bulk delete bypasses the relationship, so the eager-loaded collection would
        # still hold the removed rows.
        db_session.expire(program, ["early_access_program_feature_flags"])
        return OperationEarlyAccessProgramImpl.from_orm(program)

    @with_users_db_session
    def delete_early_access_program(self, id: str, db_session=None) -> Response:
        program = db_session.get(EarlyAccessProgram, id)
        if program is None:
            raise HTTPException(
                status_code=404, detail=early_access_program_not_found.format(id)
            )
        # Cascades to grants, enrollments and invites via ON DELETE CASCADE (see the mapper
        # listener in shared/database/users_database.py). Flags already granted are untouched.
        db_session.delete(program)
        db_session.flush()
        # The generator records 204 only under `responses`, never as the route's status_code,
        # so returning None here would answer 200.
        return Response(status_code=204)

    @with_users_db_session
    def get_early_access_program_report(
        self,
        id: str,
        limit: Optional[int] = 100,
        offset: Optional[int] = 0,
        status: Optional[str] = None,
        format: Optional[str] = JSON_FORMAT,
        db_session=None,
    ) -> EarlyAccessProgramReport:
        if db_session.get(EarlyAccessProgram, id) is None:
            raise HTTPException(
                status_code=404, detail=early_access_program_not_found.format(id)
            )
        _validate_format(format)
        _validate_status(status)
        limit = limit or 100
        offset = offset or 0

        # Merged in Python, not a SQL UNION: the halves carry different columns, so a UNION
        # would need NULL-literal padding per side.
        enrolled = [
            EarlyAccessReportRow(
                email=email,
                status=_STATUS_ENROLLED,
                user_id=enrollment.user_id,
                enrolled_at=enrollment.enrolled_at,
                source=enrollment.source,
                invited_at=None,
            )
            for enrollment, email in db_session.query(
                EarlyAccessEnrollment, AppUser.email
            )
            .join(AppUser, AppUser.id == EarlyAccessEnrollment.user_id)
            .filter(EarlyAccessEnrollment.program_id == id)
            .all()
        ]
        invited = [
            EarlyAccessReportRow(
                email=row.email,
                status=_STATUS_INVITED,
                user_id=None,
                enrolled_at=None,
                source=None,
                invited_at=row.created_at,
            )
            for row in db_session.query(EarlyAccessInvitedEmail)
            .filter(EarlyAccessInvitedEmail.program_id == id)
            .all()
        ]

        # Always the whole program, so `status` below narrows rows but not these counts.
        by_source: Dict[str, int] = {}
        for row in enrolled:
            by_source[row.source] = by_source.get(row.source, 0) + 1
        summary = EarlyAccessReportSummary(
            enrolled_count=len(enrolled),
            outstanding_invite_count=len(invited),
            total=len(enrolled) + len(invited),
            by_source=EarlyAccessReportSummaryBySource(
                invited_email=by_source.get("invited_email", 0),
                operations=by_source.get("operations", 0),
            ),
        )

        if status == _STATUS_ENROLLED:
            selected = enrolled
        elif status == _STATUS_INVITED:
            selected = invited
        else:
            selected = enrolled + invited
        all_rows = sorted(selected, key=lambda row: (row.status, row.email))
        page = all_rows[offset : offset + limit]
        if format == CSV_FORMAT:
            # Rows only; the summary has no sensible tabular form alongside them.
            return csv_response(
                f"early-access-{id}-report.csv",
                _REPORT_CSV_FIELDS,
                [row.model_dump() for row in page],
            )
        return EarlyAccessProgramReport(
            program_id=id,
            summary=summary,
            total=len(all_rows),
            offset=offset,
            limit=limit,
            rows=page,
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

        # The 5000 cap is enforced by the request schema before this runs.
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

        # Case-insensitive match via idx_app_user_email_lower. app_user.email is only
        # case-sensitively UNIQUE, so two accounts differing by case would both match here.
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
