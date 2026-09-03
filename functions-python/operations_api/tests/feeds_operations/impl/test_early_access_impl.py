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
"""DB-backed tests for the Operations early access programs API, against the real users test
database."""

import csv
import io
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
from feeds_gen.models.remove_early_access_invited_emails_request import (
    RemoveEarlyAccessInvitedEmailsRequest,
)
from feeds_gen.models.update_early_access_program_request import (
    UpdateEarlyAccessProgramRequest,
)
from feeds_operations.impl.early_access_impl import EarlyAccessApiImpl
from shared.common.early_access import grant_program_flags
from shared.database.users_database import UsersDatabase
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    EarlyAccessEnrollment,
    EarlyAccessInvitedEmail,
    EarlyAccessProgram,
    EarlyAccessProgramFeatureFlag,
    FeatureFlag,
    UserFeatureFlag,
)
from test_shared.test_utils.database_utils import default_users_db_url


def _reset_singleton():
    UsersDatabase.instance = None
    UsersDatabase.initialized = False


def _uid() -> str:
    return uuid.uuid4().hex


@pytest.fixture
def session():
    """A real users-DB session, rolled back so nothing persists. `db.Session()` rather than
    `start_db_session()`, which commits on a clean exit."""
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


class TestDeleteProgram:
    def test_deletes_a_program_that_has_children(self, api, session, flag):
        """Without passive_deletes on the generated relationships, SQLAlchemy blanks the NOT
        NULL child FKs first and this fails on anything but an empty program."""
        program = EarlyAccessProgram(id=_uid(), name="Delete With Children")
        session.add(program)
        session.flush()
        session.add(
            EarlyAccessProgramFeatureFlag(
                program_id=program.id, feature_flag_id=flag, value=True
            )
        )
        user = AppUser(id=f"user-{_uid()}", email=f"enrolled-{_uid()}@example.com")
        session.add(user)
        session.flush()
        session.add(
            EarlyAccessEnrollment(
                id=_uid(),
                program_id=program.id,
                user_id=user.id,
                source="operations",
            )
        )
        session.add(
            EarlyAccessInvitedEmail(
                id=_uid(), program_id=program.id, email=f"invited-{_uid()}@example.com"
            )
        )
        grant_program_flags(user.id, program.id, session)
        session.flush()
        assert (
            session.query(UserFeatureFlag)
            .filter_by(user_id=user.id, feature_flag_id=flag)
            .count()
            == 1
        )

        api.delete_early_access_program(program.id, db_session=session)

        assert session.get(EarlyAccessProgram, program.id) is None
        for model, attr in (
            (EarlyAccessProgramFeatureFlag, "program_id"),
            (EarlyAccessEnrollment, "program_id"),
            (EarlyAccessInvitedEmail, "program_id"),
        ):
            assert session.query(model).filter_by(**{attr: program.id}).count() == 0

        # The cascade stops at the program's own rows: the flag definition is shared, and
        # granted access is never revoked.
        assert session.get(FeatureFlag, flag) is not None
        assert (
            session.query(UserFeatureFlag)
            .filter_by(user_id=user.id, feature_flag_id=flag)
            .count()
            == 1
        )
        assert session.get(AppUser, user.id) is not None

    def test_returns_204(self, api, session):
        program = EarlyAccessProgram(id=_uid(), name="Delete Status")
        session.add(program)
        session.flush()

        response = api.delete_early_access_program(program.id, db_session=session)

        # The generator never sets status_code, so the impl returns the Response itself.
        assert response.status_code == 204

    def test_unknown_program_404(self, api, session):
        with pytest.raises(HTTPException) as exc_info:
            api.delete_early_access_program("does-not-exist", db_session=session)
        assert exc_info.value.status_code == 404


class TestUpdateProgram:
    """Own fields are a partial update; `feature_flags` is a full replace, so omitting it
    clears the set."""

    def _program_with_flag(self, session, name):
        flag_a = f"test.flag.{_uid()}"
        flag_b = f"test.flag.{_uid()}"
        session.add(FeatureFlag(id=flag_a, value_type="boolean", default_value=False))
        session.add(FeatureFlag(id=flag_b, value_type="boolean", default_value=False))
        session.flush()
        program = EarlyAccessProgram(id=_uid(), name=name)
        session.add(program)
        session.flush()
        session.add(
            EarlyAccessProgramFeatureFlag(
                program_id=program.id, feature_flag_id=flag_a, value=True
            )
        )
        session.flush()
        return program, flag_a, flag_b

    def _grants(self, session, program_id):
        return [
            g.feature_flag_id
            for g in session.query(EarlyAccessProgramFeatureFlag)
            .filter_by(program_id=program_id)
            .all()
        ]

    def test_replaces_the_grant_set(self, api, session):
        program, _flag_a, flag_b = self._program_with_flag(session, "Replace Test")

        result = api.update_early_access_program(
            program.id,
            UpdateEarlyAccessProgramRequest(
                feature_flags=[
                    EarlyAccessProgramFeatureFlagGrant(
                        feature_flag_id=flag_b, value=True
                    )
                ]
            ),
            db_session=session,
        )

        assert [g.feature_flag_id for g in result.feature_flags] == [flag_b]
        assert self._grants(session, program.id) == [flag_b]

    def test_omitting_feature_flags_clears_the_grant_set(self, api, session):
        program, _flag_a, _flag_b = self._program_with_flag(session, "Clear Test")

        result = api.update_early_access_program(
            program.id,
            UpdateEarlyAccessProgramRequest(name="Renamed"),
            db_session=session,
        )

        assert result.name == "Renamed"
        assert result.feature_flags == []
        assert self._grants(session, program.id) == []

    def test_updates_own_fields_partially(self, api, session):
        program, _flag_a, flag_b = self._program_with_flag(session, "Partial Test")

        result = api.update_early_access_program(
            program.id,
            UpdateEarlyAccessProgramRequest(
                description="now described",
                feature_flags=[
                    EarlyAccessProgramFeatureFlagGrant(
                        feature_flag_id=flag_b, value=True
                    )
                ],
            ),
            db_session=session,
        )

        # `name` was not in the body, so it is untouched.
        assert result.name == "Partial Test"
        assert result.description == "now described"

    def test_unknown_feature_flag_rejected_nothing_written(self, api, session):
        program, flag_a, _flag_b = self._program_with_flag(session, "Bad Flag Test")

        with pytest.raises(HTTPException) as exc_info:
            api.update_early_access_program(
                program.id,
                UpdateEarlyAccessProgramRequest(
                    name="should not stick",
                    feature_flags=[
                        EarlyAccessProgramFeatureFlagGrant(
                            feature_flag_id="does-not-exist", value=True
                        )
                    ],
                ),
                db_session=session,
            )
        assert exc_info.value.status_code == 422
        # The pre-existing grant survives: validation runs before the replace.
        assert self._grants(session, program.id) == [flag_a]

    def test_unknown_program_404(self, api, session):
        with pytest.raises(HTTPException) as exc_info:
            api.update_early_access_program(
                "does-not-exist",
                UpdateEarlyAccessProgramRequest(feature_flags=[]),
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


class TestUploadInvitedEmailsCsv:
    @pytest.fixture
    def program(self, session):
        p = EarlyAccessProgram(id=_uid(), name="Upload Test")
        session.add(p)
        session.flush()
        return p

    def test_reads_the_email_column_at_any_position_and_case(
        self, api, session, program
    ):
        existing = AppUser(id=f"user-{_uid()}", email=f"matched-{_uid()}@example.com")
        session.add(existing)
        session.flush()
        new_email = f"new-{_uid()}@example.com"
        csv_text = (
            "Name,EMAIL,Org\r\n"
            f'"Doe, Ada",{existing.email},ACME\r\n'
            f"Grace,{new_email},ACME\r\n"
        )

        result = api.upload_early_access_invited_emails_csv(
            program.id, csv_text, dry_run=True, db_session=session
        )

        # The quoted "Doe, Ada" must not shift the columns.
        assert result.matched_existing_account.count == 1
        assert result.no_account_yet.count == 1
        assert result.dry_run is True

    def test_other_columns_are_ignored(self, api, session, program):
        csv_text = (
            f"email,backup_email\nnew-{_uid()}@example.com,other-{_uid()}@example.com\n"
        )

        result = api.upload_early_access_invited_emails_csv(
            program.id, csv_text, dry_run=True, db_session=session
        )

        assert result.no_account_yet.count == 1

    def test_malformed_rows_come_back_as_invalid(self, api, session, program):
        csv_text = f"email\nnew-{_uid()}@example.com\nnot-an-email\n"

        result = api.upload_early_access_invited_emails_csv(
            program.id, csv_text, dry_run=True, db_session=session
        )

        assert result.no_account_yet.count == 1
        assert [entry.email for entry in result.invalid] == ["not-an-email"]

    def test_applies_when_not_dry_run(self, api, session, program):
        new_email = f"new-{_uid()}@example.com"

        api.upload_early_access_invited_emails_csv(
            program.id, f"email\n{new_email}\n", dry_run=False, db_session=session
        )

        assert (
            session.query(EarlyAccessInvitedEmail)
            .filter_by(program_id=program.id, email=new_email)
            .count()
            == 1
        )

    def test_no_email_column_is_422(self, api, session, program):
        with pytest.raises(HTTPException) as exc_info:
            api.upload_early_access_invited_emails_csv(
                program.id, "id,name\n1,Alex\n", dry_run=True, db_session=session
            )
        assert exc_info.value.status_code == 422
        # The rejection must not echo the file's contents.
        assert "Alex" not in exc_info.value.detail

    def test_empty_file_is_422(self, api, session, program):
        with pytest.raises(HTTPException) as exc_info:
            api.upload_early_access_invited_emails_csv(
                program.id, "", dry_run=True, db_session=session
            )
        assert exc_info.value.status_code == 422

    def test_over_the_cap_is_422_without_listing_addresses(self, api, session, program):
        rows = "\n".join(f"user{i}@example.com" for i in range(5001))
        with pytest.raises(HTTPException) as exc_info:
            api.upload_early_access_invited_emails_csv(
                program.id, f"email\n{rows}\n", dry_run=True, db_session=session
            )
        assert exc_info.value.status_code == 422
        assert "5001" in exc_info.value.detail
        assert "@example.com" not in exc_info.value.detail

    def test_unknown_program_404(self, api, session):
        with pytest.raises(HTTPException) as exc_info:
            api.upload_early_access_invited_emails_csv(
                "does-not-exist",
                "email\na@example.com\n",
                dry_run=True,
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


def _csv_rows(response):
    """Parse a csv_response body back into (header, data_rows)."""
    reader = csv.reader(io.StringIO(response.body.decode()))
    rows = list(reader)
    return rows[0], rows[1:]


class TestProgramReport:
    @pytest.fixture
    def populated(self, session):
        """1 enrollment from an invite claim, 1 direct ops grant, 2 outstanding invites."""
        program = EarlyAccessProgram(id=_uid(), name="Report Test")
        session.add(program)
        session.flush()
        for source in ("invited_email", "operations"):
            user = AppUser(id=f"user-{_uid()}", email=f"{source}-{_uid()}@example.com")
            session.add(user)
            session.flush()
            session.add(
                EarlyAccessEnrollment(
                    id=_uid(),
                    program_id=program.id,
                    user_id=user.id,
                    source=source,
                )
            )
        for _ in range(2):
            session.add(
                EarlyAccessInvitedEmail(
                    id=_uid(),
                    program_id=program.id,
                    email=f"invited-{_uid()}@example.com",
                )
            )
        session.flush()
        return program

    def test_unions_both_halves_with_summary(self, api, session, populated):
        result = api.get_early_access_program_report(populated.id, db_session=session)

        assert result.program_id == populated.id
        assert result.summary.enrolled_count == 2
        assert result.summary.outstanding_invite_count == 2
        assert result.summary.total == 4
        assert result.summary.by_source.invited_email == 1
        assert result.summary.by_source.operations == 1
        assert result.total == 4
        assert len(result.rows) == 4

        statuses = [row.status for row in result.rows]
        assert statuses.count("enrolled") == 2
        assert statuses.count("invited") == 2
        # Enrolled rows carry account fields; invited rows carry the invite timestamp instead.
        for row in result.rows:
            if row.status == "enrolled":
                assert row.user_id is not None and row.enrolled_at is not None
                assert row.invited_at is None
            else:
                assert row.user_id is None and row.enrolled_at is None
                assert row.invited_at is not None

    def test_rows_sorted_by_status_then_email(self, api, session, populated):
        result = api.get_early_access_program_report(populated.id, db_session=session)
        keys = [(row.status, row.email) for row in result.rows]
        assert keys == sorted(keys)

    def test_report_csv(self, api, session, populated):
        response = api.get_early_access_program_report(
            populated.id, format="csv", db_session=session
        )

        header, rows = _csv_rows(response)
        assert header == [
            "email",
            "status",
            "user_id",
            "enrolled_at",
            "source",
            "invited_at",
        ]
        assert len(rows) == 4
        # An invited row leaves the enrolled-only columns as blank cells, not "None".
        invited = [row for row in rows if row[1] == "invited"]
        assert len(invited) == 2
        assert all(row[2] == "" and row[3] == "" and row[4] == "" for row in invited)

    def test_csv_metadata(self, api, session, populated):
        response = api.get_early_access_program_report(
            populated.id, format="csv", db_session=session
        )
        assert response.media_type == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]

    def test_pagination(self, api, session, populated):
        result = api.get_early_access_program_report(
            populated.id, limit=3, offset=0, db_session=session
        )
        assert result.total == 4
        assert len(result.rows) == 3
        # The summary counts the whole program, not just the page.
        assert result.summary.total == 4

        result = api.get_early_access_program_report(
            populated.id, limit=3, offset=3, db_session=session
        )
        assert len(result.rows) == 1

    def test_csv_honours_limit_and_offset(self, api, session, populated):
        response = api.get_early_access_program_report(
            populated.id, limit=3, offset=0, format="csv", db_session=session
        )
        _header, rows = _csv_rows(response)
        assert len(rows) == 3

        response = api.get_early_access_program_report(
            populated.id, limit=3, offset=3, format="csv", db_session=session
        )
        _header, rows = _csv_rows(response)
        assert len(rows) == 1

    def test_status_filter_narrows_rows_but_not_the_summary(
        self, api, session, populated
    ):
        for status, expected in (("enrolled", 2), ("invited", 2)):
            result = api.get_early_access_program_report(
                populated.id, status=status, db_session=session
            )
            assert [row.status for row in result.rows] == [status] * expected
            assert result.total == expected
            # The headline numbers still describe the whole program.
            assert result.summary.enrolled_count == 2
            assert result.summary.outstanding_invite_count == 2
            assert result.summary.total == 4

    def test_status_filter_applies_to_csv(self, api, session, populated):
        response = api.get_early_access_program_report(
            populated.id, status="invited", format="csv", db_session=session
        )
        _header, rows = _csv_rows(response)
        assert len(rows) == 2
        assert all(row[1] == "invited" for row in rows)

    def test_unsupported_format_422(self, api, session, populated):
        with pytest.raises(HTTPException) as exc_info:
            api.get_early_access_program_report(
                populated.id, format="xlsx", db_session=session
            )
        assert exc_info.value.status_code == 422

    def test_unsupported_status_422(self, api, session, populated):
        with pytest.raises(HTTPException) as exc_info:
            api.get_early_access_program_report(
                populated.id, status="pending", db_session=session
            )
        assert exc_info.value.status_code == 422

    def test_unknown_program_404(self, api, session):
        with pytest.raises(HTTPException) as exc_info:
            api.get_early_access_program_report("does-not-exist", db_session=session)
        assert exc_info.value.status_code == 404
