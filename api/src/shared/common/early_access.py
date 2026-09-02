"""Early access program grants (product-tasks#213).

Lives in `shared/common` because both the User Service (the `get_user` claim hook) and the
Operations API function (the CSV import) need `grant_program_flags` / `apply_invited_email_grants`,
and `common` is in both functions' `include_api_folders`. Must not import the Brevo SDK, for the
same reason `feature_flags.py` was split out: some functions that include `common` (e.g.
`batch_process_dataset`) do not depend on it.

Email verification is deliberately not checked here — see EARLY-ACCESS-PLAN.md section 5.
`app_user.email_verified` is not kept in sync anywhere in the codebase today, so enforcing it
here would require building a live sync as a side effect of this feature. Grants are made on a
matching, authenticated email alone; keeping `email_verified` current is a separate issue.
"""

import logging
from datetime import datetime, timezone
from typing import Final

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from shared.database.database import generate_unique_id
from shared.users_database_gen.sqlacodegen_models import (
    EarlyAccessEnrollment,
    EarlyAccessInvitedEmail,
    EarlyAccessProgram,
    EarlyAccessProgramFeatureFlag,
    UserFeatureFlag,
)

logger = logging.getLogger(__name__)

guest_no_early_access: Final[str] = "Guest users do not have early access grants."
early_access_program_not_found: Final[str] = "Early access program '{}' not found."
unknown_feature_flags: Final[str] = "Unknown feature flag(s): {}."


def grant_program_flags(db_session, user_id: str, program_id: str) -> bool:
    """Grant every feature flag `program_id` currently configures to `user_id`.

    No-ops if the program is disabled or has no configured flags — a disabled program hands out
    nothing, whether the caller is the invited-email claim path or the CSV import's immediate
    grant for an already-existing account.

    ``DO NOTHING``, not ``DO UPDATE``: an operator-set `user_feature_flag` row always wins over a
    program grant, self-service (invited-email claim) or bulk (CSV import), per decision 3 in
    EARLY-ACCESS-PLAN.md.

    Returns True if a grant was attempted (program enabled and has flags), False otherwise. This
    says nothing about whether any row was actually inserted — ``DO NOTHING`` can silently no-op
    per flag, and that's the intended behaviour, not a failure to report.
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


def apply_invited_email_grants(db_session, user_id: str, email: str) -> list[str]:
    """Claim every outstanding, non-disabled invited-email row for `email` on behalf of `user_id`.

    Runs on every `get_user` call, not just account creation — a user with no pending invite the
    first time they sign in must still be able to claim one added, or still outstanding, later.
    The common case (no pending invite) is a single indexed lookup on `idx_eaie_email` that
    deletes nothing.

    For each claimed program: creates the durable `early_access_enrollment` audit row
    (`source='invited_email'`) and calls `grant_program_flags`. The enrollment insert's
    ``ON CONFLICT DO NOTHING`` is a safety net, not a cap check — an `early_access_invited_email`
    row cannot outlive its claim, so a genuine double-claim race is not expected, and there is no
    enrollment cap to enforce (see EARLY-ACCESS-PLAN.md section 1, `max_enrollments` removal).

    A row tied to a currently-disabled program is left untouched (not deleted), so re-enabling
    the program later still lets it be claimed on a subsequent call.

    Returns the list of program_ids claimed (empty if none were pending).
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
        db_session.execute(
            pg_insert(EarlyAccessEnrollment.__table__)
            .values(
                id=generate_unique_id(),
                program_id=program_id,
                user_id=user_id,
                enrolled_at=now,
                source="invited_email",
            )
            .on_conflict_do_nothing(index_elements=["program_id", "user_id"])
        )
        grant_program_flags(db_session, user_id, program_id)

    logger.info("user %s claimed %d early access invite(s)", user_id, len(claimed_program_ids))
    return list(claimed_program_ids)
