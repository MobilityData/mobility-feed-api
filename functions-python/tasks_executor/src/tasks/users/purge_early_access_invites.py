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
"""Purges unclaimed early access invited emails past their program's retention window.

Legal/privacy requirement (product-tasks#213): we must not hold the email address of someone who
never registered. Claiming an invite already deletes its row (see `apply_invited_email_grants` in
`shared/common/early_access.py`); this task is the other half — sweeping up invites that were
never claimed at all, once they are older than their program's `invite_retention_days`.

``dry_run`` (default True) computes counts without deleting. Reports counts **per program only,
never addresses** — the whole point of this task is to stop holding them, so they must not
reappear in logs on the way out.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from shared.database.users_database import with_users_db_session

logger = logging.getLogger(__name__)

# Two programs can have different `invite_retention_days`, so the cutoff is computed per-row
# against each invite's own program, not a single global cutoff.
_EXPIRED_INVITES_BY_PROGRAM_SQL = text("""
    SELECT i.program_id AS program_id, count(*) AS expired_count
      FROM early_access_invited_email i
      JOIN early_access_program p ON i.program_id = p.id
     WHERE i.created_at < now() - make_interval(days => p.invite_retention_days)
     GROUP BY i.program_id
    """)

_DELETE_EXPIRED_INVITES_SQL = text("""
    DELETE FROM early_access_invited_email i
     USING early_access_program p
     WHERE i.program_id = p.id
       AND i.created_at < now() - make_interval(days => p.invite_retention_days)
    RETURNING i.program_id AS program_id
    """)


def purge_early_access_invites(
    dry_run: bool = True, db_session: Session | None = None
) -> dict:
    """Core purge logic.

    Args:
        dry_run: When True (default), counts expired invites per program without deleting them.
        db_session: Injected by the @with_users_db_session decorator.

    Returns:
        Summary dict: dry_run, programs_with_expired_invites, total_expired_invites, and
        counts_by_program (program_id -> count). No email addresses anywhere in the result.
    """
    if dry_run:
        counts_by_program = {
            row.program_id: row.expired_count
            for row in db_session.execute(_EXPIRED_INVITES_BY_PROGRAM_SQL).all()
        }
    else:
        counts_by_program: dict[str, int] = {}
        for row in db_session.execute(_DELETE_EXPIRED_INVITES_SQL).all():
            counts_by_program[row.program_id] = (
                counts_by_program.get(row.program_id, 0) + 1
            )
        db_session.flush()

    results = {
        "dry_run": dry_run,
        "programs_with_expired_invites": len(counts_by_program),
        "total_expired_invites": sum(counts_by_program.values()),
        "counts_by_program": counts_by_program,
    }
    logger.info(
        "purge_early_access_invites_completed",
        extra={"json_fields": {"task": "purge_early_access_invites", **results}},
    )
    return results


@with_users_db_session
def purge_early_access_invites_handler(
    payload: dict | None = None, db_session: Session | None = None
) -> dict:
    """tasks_executor entry point.

    Payload keys (all optional):
        dry_run (bool, default True): Count expired invites per program without deleting them.
    """
    payload = payload or {}
    logger.info("purge_early_access_invites_handler called with payload=%s", payload)

    dry_run = payload.get("dry_run", True)
    dry_run = dry_run if isinstance(dry_run, bool) else str(dry_run).lower() == "true"

    return purge_early_access_invites(dry_run=dry_run, db_session=db_session)
