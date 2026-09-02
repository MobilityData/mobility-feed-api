#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""Integration tests for the purge_early_access_invites task.

These run against the real Postgres users test database (``MobilityDatabaseUsersTest``). Each
test creates its own programs/invites and removes them again in tearDown.

Calls the core (undecorated) ``purge_early_access_invites`` through a locally-decorated wrapper
pinned to ``default_users_db_url``, rather than the ``_handler`` entry point: the handler's
``@with_users_db_session`` has no ``db_url`` override, so it resolves ``USERS_DATABASE_URL`` from
the environment at call time - which in local dev points at the real ``MobilityDatabaseUsers`` DB,
not the test one.
"""

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from shared.database.users_database import with_users_db_session
from shared.users_database_gen.sqlacodegen_models import (
    EarlyAccessInvitedEmail,
    EarlyAccessProgram,
)
from tasks.users.purge_early_access_invites import purge_early_access_invites
from test_shared.test_utils.database_utils import default_users_db_url


@with_users_db_session(db_url=default_users_db_url)
def _run_purge(dry_run: bool, db_session: Session = None) -> dict:
    return purge_early_access_invites(dry_run=dry_run, db_session=db_session)


@with_users_db_session(db_url=default_users_db_url)
def _cleanup(db_session: Session = None):
    db_session.query(EarlyAccessInvitedEmail).delete()
    db_session.query(EarlyAccessProgram).delete()


def _uid() -> str:
    return str(uuid.uuid4())


@with_users_db_session(db_url=default_users_db_url)
def _make_program(
    program_id: str, invite_retention_days: int, db_session: Session = None
) -> None:
    db_session.add(
        EarlyAccessProgram(
            id=program_id,
            name=f"Program {program_id}",
            invite_retention_days=invite_retention_days,
        )
    )


@with_users_db_session(db_url=default_users_db_url)
def _make_invite(
    program_id: str, email: str, created_at: datetime, db_session: Session = None
) -> None:
    db_session.add(
        EarlyAccessInvitedEmail(
            id=_uid(),
            program_id=program_id,
            email=email,
            created_at=created_at,
        )
    )


@with_users_db_session(db_url=default_users_db_url)
def _invite_exists(program_id: str, email: str, db_session: Session = None) -> bool:
    return (
        db_session.query(EarlyAccessInvitedEmail)
        .filter_by(program_id=program_id, email=email)
        .first()
        is not None
    )


class TestPurgeEarlyAccessInvites(unittest.TestCase):
    def tearDown(self):
        _cleanup()

    def test_dry_run_deletes_nothing(self):
        program_id = _uid()
        _make_program(program_id, invite_retention_days=1)
        expired_at = datetime.now(timezone.utc) - timedelta(days=2)
        _make_invite(program_id, "expired@example.com", expired_at)

        result = _run_purge(dry_run=True)

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["total_expired_invites"], 1)
        self.assertEqual(result["counts_by_program"], {program_id: 1})
        self.assertTrue(_invite_exists(program_id, "expired@example.com"))

    def test_young_invite_survives_old_invite_purged(self):
        program_id = _uid()
        _make_program(program_id, invite_retention_days=1)
        now = datetime.now(timezone.utc)
        _make_invite(program_id, "old@example.com", now - timedelta(days=2))
        _make_invite(program_id, "young@example.com", now)

        result = _run_purge(dry_run=False)

        self.assertFalse(result["dry_run"])
        self.assertEqual(result["counts_by_program"].get(program_id), 1)
        self.assertFalse(_invite_exists(program_id, "old@example.com"))
        self.assertTrue(_invite_exists(program_id, "young@example.com"))

    def test_two_programs_different_retention_honoured_in_one_sweep(self):
        short_program_id = _uid()
        long_program_id = _uid()
        _make_program(short_program_id, invite_retention_days=1)
        _make_program(long_program_id, invite_retention_days=30)
        two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
        _make_invite(short_program_id, "short@example.com", two_days_ago)
        _make_invite(long_program_id, "long@example.com", two_days_ago)

        result = _run_purge(dry_run=False)

        self.assertEqual(result["counts_by_program"].get(short_program_id), 1)
        self.assertNotIn(long_program_id, result["counts_by_program"])
        self.assertFalse(_invite_exists(short_program_id, "short@example.com"))
        self.assertTrue(_invite_exists(long_program_id, "long@example.com"))

    def test_result_carries_counts_only(self):
        program_id = _uid()
        _make_program(program_id, invite_retention_days=1)
        _make_invite(
            program_id,
            "expired@example.com",
            datetime.now(timezone.utc) - timedelta(days=2),
        )

        result = _run_purge(dry_run=False)

        expected_keys = {
            "dry_run",
            "programs_with_expired_invites",
            "total_expired_invites",
            "counts_by_program",
        }
        self.assertEqual(set(result.keys()), expected_keys)
        self.assertNotIn("expired@example.com", str(result))
