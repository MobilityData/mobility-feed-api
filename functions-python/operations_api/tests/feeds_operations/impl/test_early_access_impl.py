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
"""DB-backed tests for the Operations early access programs API (product-tasks#213).

Runs against the real Postgres users test database (``MobilityDatabaseUsersTest``), mirroring
``test_licenses_propagate_match.py``'s ``db_session`` fixture style. Each test creates its own
rows and cleans them up in a fixture teardown.
"""

import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from feeds_gen.models.create_early_access_program_request import (
    CreateEarlyAccessProgramRequest,
)
from feeds_gen.models.early_access_program_feature_flag_grant import (
    EarlyAccessProgramFeatureFlagGrant,
)
from feeds_gen.models.import_early_access_invited_emails_request import (
    ImportEarlyAccessInvitedEmailsRequest,
)
from feeds_gen.models.put_early_access_program_feature_flags_request import (
    PutEarlyAccessProgramFeatureFlagsRequest,
)
from feeds_gen.models.remove_early_access_invited_emails_request import (
    RemoveEarlyAccessInvitedEmailsRequest,
)
from feeds_operations.impl.early_access_impl import EarlyAccessApiImpl
from shared.database.users_database import UsersDatabase
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    EarlyAccessEnrollment,
    EarlyAccessInvitedEmail,
    EarlyAccessProgram,
    EarlyAccessProgramFeatureFlag,
    FeatureFlag,
)
from test_shared.test_utils.database_utils import default_users_db_url


def _reset_singleton():
    UsersDatabase.instance = None
    UsersDatabase.initialized = False


def _uid() -> str:
    return uuid.uuid4().hex


@pytest.fixture
def session():
    """A real users-DB session, rolled back (never committed) so nothing persists.

    Uses ``db.Session()`` directly rather than ``start_db_session()``, which commits on a clean
    exit - this keeps the test DB clean across repeated runs without needing to track and delete
    every row each test creates.
    """
    _reset_singleton()
    db = UsersDatabase(users_database_url=default_users_db_url)
    s = db.Session()
    try:
        yield s
    finally:
        s.rollback()
        s.close()
        _reset_singleton()


@pytest.fixture
def flag(session):
    flag_id = f"test.flag.{_uid()}"
    session.add(FeatureFlag(id=flag_id, value_type="boolean", default_value=False))
    session.flush()
    return flag_id


@pytest.fixture
def api():
    return EarlyAccessApiImpl()


class TestCreateProgram:
    def test_writes_program_and_feature_flags_atomically(self, api, session, flag):
        request = CreateEarlyAccessProgramRequest(
            name="Summit 2026",
            feature_flags=[
                EarlyAccessProgramFeatureFlagGrant(feature_flag_id=flag, value=True)
            ],
        )

        result = api.create_early_access_program(request, db_session=session)

        assert result.name == "Summit 2026"
        assert [g.feature_flag_id for g in result.feature_flags] == [flag]
        program = session.get(EarlyAccessProgram, result.id)
        assert program is not None
        grants = (
            session.query(EarlyAccessProgramFeatureFlag)
            .filter_by(program_id=result.id)
            .all()
        )
        assert [g.feature_flag_id for g in grants] == [flag]

    def test_unknown_feature_flag_rejected_nothing_written(self, api, session):
        request = CreateEarlyAccessProgramRequest(
            name="Bad Program",
            feature_flags=[
                EarlyAccessProgramFeatureFlagGrant(
                    feature_flag_id="does-not-exist", value=True
                )
            ],
        )

        with pytest.raises(HTTPException) as exc_info:
            api.create_early_access_program(request, db_session=session)
        assert exc_info.value.status_code == 422
        assert (
            session.query(EarlyAccessProgram).filter_by(name="Bad Program").first()
            is None
        )

    def test_value_type_mismatch_rejected_nothing_written(self, api, session, flag):
        request = CreateEarlyAccessProgramRequest(
            name="Bad Value Program",
            feature_flags=[
                EarlyAccessProgramFeatureFlagGrant(
                    feature_flag_id=flag, value="not-a-boolean"
                )
            ],
        )

        with pytest.raises(HTTPException) as exc_info:
            api.create_early_access_program(request, db_session=session)
        assert exc_info.value.status_code == 422
        assert (
            session.query(EarlyAccessProgram)
            .filter_by(name="Bad Value Program")
            .first()
            is None
        )


class TestPutFeatureFlags:
    def test_replaces_the_grant_set(self, api, session):
        flag_a = f"test.flag.{_uid()}"
        flag_b = f"test.flag.{_uid()}"
        session.add(FeatureFlag(id=flag_a, value_type="boolean", default_value=False))
        session.add(FeatureFlag(id=flag_b, value_type="boolean", default_value=False))
        session.flush()
        program = EarlyAccessProgram(id=_uid(), name="Replace Test")
        session.add(program)
        session.flush()
        session.add(
            EarlyAccessProgramFeatureFlag(
                program_id=program.id, feature_flag_id=flag_a, value=True
            )
        )
        session.flush()

        result = api.put_early_access_program_feature_flags(
            program.id,
            PutEarlyAccessProgramFeatureFlagsRequest(
                feature_flags=[
                    EarlyAccessProgramFeatureFlagGrant(
                        feature_flag_id=flag_b, value=True
                    )
                ]
            ),
            db_session=session,
        )

        assert [g.feature_flag_id for g in result.feature_flags] == [flag_b]
        remaining = (
            session.query(EarlyAccessProgramFeatureFlag)
            .filter_by(program_id=program.id)
            .all()
        )
        assert [g.feature_flag_id for g in remaining] == [flag_b]

    def test_unknown_program_404(self, api, session):
        with pytest.raises(HTTPException) as exc_info:
            api.put_early_access_program_feature_flags(
                "does-not-exist",
                PutEarlyAccessProgramFeatureFlagsRequest(feature_flags=[]),
                db_session=session,
            )
        assert exc_info.value.status_code == 404


class TestImportInvitedEmails:
    @pytest.fixture
    def program(self, session):
        p = EarlyAccessProgram(id=_uid(), name="Import Test")
        session.add(p)
        session.flush()
        return p

    def test_five_categories(self, api, session, program):
        existing_user = AppUser(
            id=f"user-{_uid()}", email=f"matched-{_uid()}@example.com"
        )
        session.add(existing_user)
        session.flush()
        enrolled_user = AppUser(
            id=f"user-{_uid()}", email=f"enrolled-{_uid()}@example.com"
        )
        session.add(enrolled_user)
        session.flush()
        session.add(
            EarlyAccessEnrollment(
                id=_uid(),
                program_id=program.id,
                user_id=enrolled_user.id,
                source="operations",
            )
        )
        already_invited_email = f"invited-{_uid()}@example.com"
        session.add(
            EarlyAccessInvitedEmail(
                id=_uid(), program_id=program.id, email=already_invited_email
            )
        )
        session.flush()

        request = ImportEarlyAccessInvitedEmailsRequest(
            emails=[
                existing_user.email,
                enrolled_user.email,
                already_invited_email,
                f"new-{_uid()}@example.com",
                "not-an-email",
            ],
            dry_run=True,
        )

        result = api.import_early_access_invited_emails(
            program.id, request, db_session=session
        )

        assert result.matched_existing_account.count == 1
        assert result.already_enrolled.count == 1
        assert result.already_invited.count == 1
        assert result.no_account_yet.count == 1
        assert len(result.invalid) == 1
        assert result.invalid[0].email == "not-an-email"

    def test_dry_run_writes_nothing(self, api, session, program):
        existing_user = AppUser(
            id=f"user-{_uid()}", email=f"matched-{_uid()}@example.com"
        )
        session.add(existing_user)
        session.flush()
        new_email = f"new-{_uid()}@example.com"

        api.import_early_access_invited_emails(
            program.id,
            ImportEarlyAccessInvitedEmailsRequest(
                emails=[existing_user.email, new_email], dry_run=True
            ),
            db_session=session,
        )

        assert (
            session.query(EarlyAccessEnrollment)
            .filter_by(program_id=program.id)
            .first()
            is None
        )
        assert (
            session.query(EarlyAccessInvitedEmail)
            .filter_by(program_id=program.id, email=new_email)
            .first()
            is None
        )

    def test_apply_grants_existing_account_and_invites_new_one(
        self, api, session, program, flag
    ):
        session.add(
            EarlyAccessProgramFeatureFlag(
                program_id=program.id, feature_flag_id=flag, value=True
            )
        )
        session.flush()
        existing_user = AppUser(
            id=f"user-{_uid()}", email=f"matched-{_uid()}@example.com"
        )
        session.add(existing_user)
        session.flush()
        new_email = f"new-{_uid()}@example.com"

        result = api.import_early_access_invited_emails(
            program.id,
            ImportEarlyAccessInvitedEmailsRequest(
                emails=[existing_user.email, new_email], dry_run=False
            ),
            db_session=session,
        )

        assert result.dry_run is False
        enrollment = (
            session.query(EarlyAccessEnrollment)
            .filter_by(program_id=program.id, user_id=existing_user.id)
            .first()
        )
        assert enrollment is not None
        assert enrollment.source == "operations"
        invite = (
            session.query(EarlyAccessInvitedEmail)
            .filter_by(program_id=program.id, email=new_email)
            .first()
        )
        assert invite is not None

    def test_case_insensitive_and_deduplicated_matching(self, api, session, program):
        existing_user = AppUser(
            id=f"user-{_uid()}", email=f"Mixed.Case-{_uid()}@Example.com"
        )
        session.add(existing_user)
        session.flush()

        result = api.import_early_access_invited_emails(
            program.id,
            ImportEarlyAccessInvitedEmailsRequest(
                emails=[
                    existing_user.email.upper(),
                    existing_user.email.lower(),
                    existing_user.email.lower(),
                ],
                dry_run=True,
            ),
            db_session=session,
        )

        assert result.matched_existing_account.count == 1

    def test_reupload_identical_csv_is_a_noop(self, api, session, program):
        new_email = f"new-{_uid()}@example.com"
        request = ImportEarlyAccessInvitedEmailsRequest(
            emails=[new_email], dry_run=False
        )

        first = api.import_early_access_invited_emails(
            program.id, request, db_session=session
        )
        second = api.import_early_access_invited_emails(
            program.id, request, db_session=session
        )

        assert first.no_account_yet.count == 1
        assert second.no_account_yet.count == 0
        assert second.already_invited.count == 1
        assert (
            session.query(EarlyAccessInvitedEmail)
            .filter_by(program_id=program.id, email=new_email)
            .count()
            == 1
        )

    def test_cap_exceeded_rejected_before_reaching_impl(self):
        with pytest.raises(ValidationError):
            ImportEarlyAccessInvitedEmailsRequest(
                emails=[f"user{i}@example.com" for i in range(5001)]
            )

    def test_unknown_program_404(self, api, session):
        with pytest.raises(HTTPException) as exc_info:
            api.import_early_access_invited_emails(
                "does-not-exist",
                ImportEarlyAccessInvitedEmailsRequest(emails=["a@example.com"]),
                db_session=session,
            )
        assert exc_info.value.status_code == 404


class TestRemoveInvitedEmails:
    def test_removes_outstanding_invites_and_counts_not_found(self, api, session):
        program = EarlyAccessProgram(id=_uid(), name="Remove Test")
        session.add(program)
        session.flush()
        present_email = f"present-{_uid()}@example.com"
        session.add(
            EarlyAccessInvitedEmail(
                id=_uid(), program_id=program.id, email=present_email
            )
        )
        session.flush()
        absent_email = f"absent-{_uid()}@example.com"

        result = api.remove_early_access_invited_emails(
            program.id,
            RemoveEarlyAccessInvitedEmailsRequest(emails=[present_email, absent_email]),
            db_session=session,
        )

        assert result.removed_count == 1
        assert result.not_found_count == 1
        remaining = (
            session.query(EarlyAccessInvitedEmail)
            .filter_by(program_id=program.id, email=present_email)
            .first()
        )
        assert remaining is None
