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
"""DB-backed tests for the invited-email claim hook in `get_user`, against the real users test
database. There is no user-facing early-access endpoint; `GET /v1/user`'s `features[]` is the
only surface."""

import uuid

import pytest

from middleware.request_context import _request_context
from shared.common.early_access import grant_program_flags
from shared.common.feature_flags import feature_flag_enabled
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
from user_service.impl.users_api_impl import UsersApiImpl


def _reset_singleton():
    UsersDatabase.instance = None
    UsersDatabase.initialized = False


def _uid() -> str:
    return uuid.uuid4().hex


@pytest.fixture
def session(users_test_database_url):
    _reset_singleton()
    db = UsersDatabase()
    s = db.Session()
    try:
        yield s
    finally:
        s.rollback()
        s.close()
        _reset_singleton()
        _request_context.set({})


def _make_flag(session, suffix, default_value=False):
    flag_id = f"test.flag.{suffix}"
    session.add(FeatureFlag(id=flag_id, value_type="boolean", default_value=default_value))
    return flag_id


def _make_program(session, *flag_ids_and_values, invite_retention_days=90):
    program = EarlyAccessProgram(id=_uid(), name=f"Program {_uid()}", invite_retention_days=invite_retention_days)
    session.add(program)
    session.flush()
    for flag_id, value in flag_ids_and_values:
        session.add(EarlyAccessProgramFeatureFlag(program_id=program.id, feature_flag_id=flag_id, value=value))
    session.flush()
    return program


def _make_invite(session, program_id, email):
    session.add(EarlyAccessInvitedEmail(id=_uid(), program_id=program_id, email=email))
    session.flush()


class TestInvitedEmailClaimOnGetUser:
    def test_claim_grants_flag_deletes_invite_creates_enrollment(self, session):
        flag_id = _make_flag(session, "single")
        program = _make_program(session, (flag_id, True))
        user_id = f"user-{_uid()}"
        email = f"{user_id}@example.com"
        _make_invite(session, program.id, email)
        _request_context.set({"user_id": user_id, "user_email": email, "is_guest": False})

        UsersApiImpl().get_user(db_session=session)

        _assert_flag_granted(session, user_id, flag_id)
        assert session.query(EarlyAccessInvitedEmail).filter_by(program_id=program.id, email=email).first() is None
        enrollment = session.query(EarlyAccessEnrollment).filter_by(program_id=program.id, user_id=user_id).first()
        assert enrollment is not None
        assert enrollment.source == "invited_email"

    def test_multi_flag_program_grants_all_its_flags(self, session):
        flag_a = _make_flag(session, "a")
        flag_b = _make_flag(session, "b")
        program = _make_program(session, (flag_a, True), (flag_b, True))
        user_id = f"user-{_uid()}"
        email = f"{user_id}@example.com"
        _make_invite(session, program.id, email)
        _request_context.set({"user_id": user_id, "user_email": email, "is_guest": False})

        UsersApiImpl().get_user(db_session=session)

        _assert_flag_granted(session, user_id, flag_a)
        _assert_flag_granted(session, user_id, flag_b)

    def test_no_pending_invite_is_a_noop(self, session):
        user_id = f"user-{_uid()}"
        email = f"{user_id}@example.com"
        _request_context.set({"user_id": user_id, "user_email": email, "is_guest": False})

        result = UsersApiImpl().get_user(db_session=session)

        assert result.id == user_id
        assert session.query(EarlyAccessEnrollment).filter_by(user_id=user_id).first() is None

    def test_invite_added_after_first_signin_is_not_claimed_on_a_later_call(self, session):
        """Creation-only by design: an existing account is granted at bulk-add time, so a
        pending invite for one is only reachable via a narrow race and is left unclaimed."""
        flag_id = _make_flag(session, "later")
        user_id = f"user-{_uid()}"
        email = f"{user_id}@example.com"
        _request_context.set({"user_id": user_id, "user_email": email, "is_guest": False})

        # First call: account is created, nothing pending yet.
        UsersApiImpl().get_user(db_session=session)
        assert not feature_flag_enabled(session, user_id, flag_id)

        # An invite arrives after the user already has an account.
        program = _make_program(session, (flag_id, True))
        _make_invite(session, program.id, email)

        UsersApiImpl().get_user(db_session=session)

        assert not feature_flag_enabled(session, user_id, flag_id)
        invite = session.query(EarlyAccessInvitedEmail).filter_by(program_id=program.id, email=email).first()
        assert invite is not None


def _assert_flag_granted(session, user_id, flag_id):
    assert feature_flag_enabled(session, user_id, flag_id) is True


class TestGrantProgramFlagsConflicts:
    """Why `grant_program_flags` needs ON CONFLICT DO NOTHING: a plain insert would raise
    IntegrityError on both these normal paths."""

    def test_two_programs_granting_the_same_flag_do_not_collide(self, session):
        flag_id = _make_flag(session, "shared")
        program_a = _make_program(session, (flag_id, True))
        program_b = _make_program(session, (flag_id, True))
        user_id = f"user-{_uid()}"
        email = f"{user_id}@example.com"
        _make_invite(session, program_a.id, email)
        _make_invite(session, program_b.id, email)
        _request_context.set({"user_id": user_id, "user_email": email, "is_guest": False})

        # Both invites in one transaction, so the second grant hits the same primary key.
        UsersApiImpl().get_user(db_session=session)

        _assert_flag_granted(session, user_id, flag_id)
        assert session.query(UserFeatureFlag).filter_by(user_id=user_id, feature_flag_id=flag_id).count() == 1
        enrolled = {row.program_id for row in session.query(EarlyAccessEnrollment).filter_by(user_id=user_id).all()}
        assert enrolled == {program_a.id, program_b.id}

    def test_program_grant_never_overwrites_an_operator_set_flag(self, session):
        flag_id = _make_flag(session, "operator")
        program = _make_program(session, (flag_id, True))
        user_id = f"user-{_uid()}"
        session.add(AppUser(id=user_id, email=f"{user_id}@example.com"))
        session.flush()
        # An operator explicitly turned this flag OFF for this user; a program grant must lose.
        session.add(UserFeatureFlag(user_id=user_id, feature_flag_id=flag_id, value=False))
        session.flush()

        grant_program_flags(user_id, program.id, session)

        assert feature_flag_enabled(session, user_id, flag_id) is False
