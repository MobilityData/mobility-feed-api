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
"""Idempotent task that reconciles Brevo-originated unsubscribes back into our DB.

This is the *reverse* direction of the forward opt-in path. When a user changes
their api.announcements subscription on OUR side (the update_user / subscription
endpoints, routed through ``set_announcements_optin``) or when
``migrate_firebase_users`` seeds it, flag + subscription + Brevo are kept
consistent. But when a user clicks "unsubscribe" inside a Brevo email, Brevo sets
``email_blacklisted`` (global) or adds the list to ``list_unsubscribed`` — and
nothing propagates that back to us, so ``app_user.is_registered_to_receive_api_announcements``
and the ``notification_subscription.active`` row stay stale-``True``.

This task closes that gap. It is deliberately **turn-OFF only**:
  - For every user with an ACTIVE ``api.announcements`` subscription, it reads the
    Brevo contact status via ``get_contact_subscription_status(email, list_id)``.
  - When Brevo reports UNSUBSCRIBED (either the global ``email_blacklisted`` flag
    or the announcements list appearing in ``list_unsubscribed``), it sets
    ``app_user.is_registered_to_receive_api_announcements = False`` and deactivates
    the subscription (``active = False``).
  - SUBSCRIBED / NOT_FOUND are left untouched. This task NEVER re-subscribes or
    adds anyone to the list — the forward/opt-in direction is already owned by the
    API layer and ``migrate_firebase_users``.

Why only active subscriptions: a user already turned off is already consistent
with a Brevo unsubscribe, so re-checking them is wasted Brevo API calls. Once this
task deactivates a subscription it drops out of the active set, so subsequent runs
skip it — the task is naturally idempotent and restartable.

``dry_run`` (default True) queries Brevo for accurate counts but performs no DB
writes. ``limit`` caps how many active subscriptions are examined per run.
"""

from __future__ import annotations

import logging
import os

from sqlalchemy.orm import Session

from shared.common.brevo import (
    BrevoSubscriptionStatus,
    get_contact_subscription_status,
)
from shared.database.users_database import with_users_db_session
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    NotificationSubscription,
)

logger = logging.getLogger(__name__)

# Primary key of the api.announcements row in the notification_type table.
# Defined locally because shared.notifications is not exposed to this module
# (mirrors migrate_firebase_users.API_ANNOUNCEMENTS_TYPE_ID).
API_ANNOUNCEMENTS_TYPE_ID = "api.announcements"


def _resolve_announcements_list_id() -> int | None:
    """Return the numeric Brevo announcements list id, or None if unset/invalid.

    Passing the list id makes ``get_contact_subscription_status`` treat BOTH a
    global ``email_blacklisted`` and a list-level unsubscribe as UNSUBSCRIBED.
    When the id is missing/invalid we fall back to None (global blacklist only)
    and log a warning rather than aborting the whole batch.
    """
    raw = os.getenv("BREVO_API_ANNOUNCEMENTS_LIST_ID")
    if not raw:
        logger.warning(
            "BREVO_API_ANNOUNCEMENTS_LIST_ID is not set — only the global "
            "email_blacklisted flag will be honored (list-level unsubscribes ignored)."
        )
        return None
    try:
        return int(raw)
    except ValueError:
        logger.warning(
            "Invalid BREVO_API_ANNOUNCEMENTS_LIST_ID value %r — only the global "
            "email_blacklisted flag will be honored (list-level unsubscribes ignored).",
            raw,
        )
        return None


def _fetch_active_announcements_subscriptions(
    db_session: Session, limit: int | None
) -> list[tuple[NotificationSubscription, AppUser]]:
    """Return (subscription, app_user) pairs for every ACTIVE api.announcements
    subscription, joined to the owning user so we have the email in one query.

    Ordered by created_at for deterministic pagination when a ``limit`` is given.
    """
    query = (
        db_session.query(NotificationSubscription, AppUser)
        .join(AppUser, AppUser.id == NotificationSubscription.user_id)
        .filter(
            NotificationSubscription.notification_type_id == API_ANNOUNCEMENTS_TYPE_ID,
            NotificationSubscription.active.is_(True),
        )
        .order_by(NotificationSubscription.created_at)
    )
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def reconcile_announcements_from_brevo(
    dry_run: bool = True,
    limit: int | None = None,
    db_session: Session | None = None,
) -> dict:
    """Core reconciliation logic. Turn-OFF only: never re-subscribes anyone.

    Args:
        dry_run: When True (default), reads and counts without any DB writes.
            Brevo is still queried so the counts are accurate.
        limit: Maximum number of active announcements subscriptions to examine
            per run. None means no limit.
        db_session: Injected by the @with_users_db_session decorator.

    Returns:
        Summary dict with counts: checked, reconciled_unsubscribed,
        still_subscribed, not_found, brevo_failed, skipped_no_email, dry_run.
    """
    announcements_list_id = _resolve_announcements_list_id()

    results = {
        "checked": 0,
        "reconciled_unsubscribed": 0,
        "still_subscribed": 0,
        "not_found": 0,
        "brevo_failed": 0,
        "skipped_no_email": 0,
        "dry_run": dry_run,
    }

    rows = _fetch_active_announcements_subscriptions(db_session, limit)

    for subscription, user in rows:
        # Defensive: the join guarantees a user, but a row with no email cannot be
        # looked up on Brevo. Count it and move on.
        if user is None or not user.email:
            results["skipped_no_email"] += 1
            continue

        results["checked"] += 1

        # A single Brevo failure must not abort the batch.
        try:
            status = get_contact_subscription_status(user.email, announcements_list_id)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Brevo status check failed for user_id=%s (retried next run)",
                user.id,
            )
            results["brevo_failed"] += 1
            continue

        if status == BrevoSubscriptionStatus.UNSUBSCRIBED:
            results["reconciled_unsubscribed"] += 1
            logger.info(
                "Reconciling Brevo unsubscribe for user_id=%s: deactivating "
                "api.announcements subscription %s",
                user.id,
                subscription.id,
            )
            if not dry_run:
                user.is_registered_to_receive_api_announcements = False
                subscription.active = False
                db_session.flush()
        elif status == BrevoSubscriptionStatus.SUBSCRIBED:
            results["still_subscribed"] += 1
        else:  # NOT_FOUND — never re-add; a non-contact simply stays enabled.
            results["not_found"] += 1

    logger.info(
        "reconcile_announcements_completed",
        extra={
            "json_fields": {
                "task": "reconcile_announcements_from_brevo",
                **results,
            }
        },
    )
    return results


@with_users_db_session
def reconcile_announcements_from_brevo_handler(
    payload: dict | None = None, db_session: Session | None = None
) -> dict:
    """tasks_executor entry point.

    Payload keys (all optional):
        dry_run (bool, default True): No DB writes; Brevo still queried for counts.
        limit (int, default None): Max active subscriptions to examine per run.
    """
    payload = payload or {}
    logger.info(
        "reconcile_announcements_from_brevo_handler called with payload=%s", payload
    )

    dry_run, limit = get_parameters(payload)

    return reconcile_announcements_from_brevo(
        dry_run=dry_run,
        limit=limit,
        db_session=db_session,
    )


def get_parameters(payload: dict) -> tuple[bool, int | None]:
    """Extract and validate parameters from the payload."""
    dry_run = payload.get("dry_run", True)
    dry_run = dry_run if isinstance(dry_run, bool) else str(dry_run).lower() == "true"
    limit = payload.get("limit", None)
    if limit is not None:
        limit = int(limit)
    return dry_run, limit
