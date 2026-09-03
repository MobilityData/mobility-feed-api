import logging
from datetime import datetime, timezone
from typing import Final

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from shared.database.database import generate_unique_id
from shared.users_database_gen.sqlacodegen_models import (
    EarlyAccessEnrollment,
    EarlyAccessInvitedEmail,
    EarlyAccessProgram,
    EarlyAccessProgramFeatureFlag,
    UserFeatureFlag,
)

logger = logging.getLogger(__name__)

early_access_program_not_found: Final[str] = "Early access program '{}' not found."
unknown_feature_flags: Final[str] = "Unknown feature flag(s): {}."


def grant_program_flags(user_id: str, program_id: str, db_session: Session) -> bool:
    """Grant every feature flag `program_id` configures to `user_id`.

    No-ops if the program is disabled or configures no flags. Returns whether a grant was
    attempted, not whether any row was written: DO NOTHING because the user may already hold the
    flag from an operator (who wins) or from another program granting the same one.
    """
    program = db_session.get(EarlyAccessProgram, program_id)
    if program is None or program.disabled:
        logger.debug("early access program %r missing or disabled; nothing granted", program_id)
        return False

    grants = (
        db_session.query(EarlyAccessProgramFeatureFlag)
        .filter(EarlyAccessProgramFeatureFlag.program_id == program_id)
        .all()
    )
    if not grants:
        logger.debug("early access program %r has no feature flag grants configured", program_id)
        return False

    now = datetime.now(timezone.utc)
    stmt = pg_insert(UserFeatureFlag.__table__).values(
        [
            {
                "user_id": user_id,
                "feature_flag_id": grant.feature_flag_id,
                "value": grant.value,
                "assigned_at": now,
            }
            for grant in grants
        ]
    )
    db_session.execute(stmt.on_conflict_do_nothing(index_elements=["user_id", "feature_flag_id"]))
    return True


def apply_invited_email_grants(user_id: str, email: str, db_session: Session) -> list[str]:
    """Claim every outstanding invited-email row for `email`, returning the program_ids claimed.

    DELETE ... RETURNING claims exclusively, so only one caller acts on a given invite. Rows for
    a disabled program are left in place so re-enabling it lets them be claimed later.
    """
    email = email.lower()
    not_disabled_program_ids = select(EarlyAccessProgram.id).where(EarlyAccessProgram.disabled.is_(False))
    claimed_program_ids = (
        db_session.execute(
            delete(EarlyAccessInvitedEmail)
            .where(
                EarlyAccessInvitedEmail.email == email,
                EarlyAccessInvitedEmail.program_id.in_(not_disabled_program_ids),
            )
            .returning(EarlyAccessInvitedEmail.program_id)
        )
        .scalars()
        .all()
    )
    if not claimed_program_ids:
        return []

    now = datetime.now(timezone.utc)
    for program_id in claimed_program_ids:
        db_session.add(
            EarlyAccessEnrollment(
                id=generate_unique_id(),
                program_id=program_id,
                user_id=user_id,
                enrolled_at=now,
                source="invited_email",
            )
        )
        grant_program_flags(user_id, program_id, db_session)
    db_session.flush()

    logger.info("user %s claimed %d early access invite(s)", user_id, len(claimed_program_ids))
    return list(claimed_program_ids)
