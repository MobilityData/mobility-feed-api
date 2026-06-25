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
"""Idempotent task that migrates Firebase users into the users.app_user PostgreSQL table.

Field mapping:
  app_user.id                    <- Firebase Auth uid
  app_user.email                 <- Firebase Auth email
  app_user.email_verified        <- Firebase Auth email_verified
  app_user.created_at            <- Firebase Auth user_metadata.creation_timestamp
  app_user.full_name             <- Datastore kind 'web_api_users' (queried by uid property).fullName
  app_user.legacy_org_name       <- Datastore kind 'web_api_users' (queried by uid property).organization
  app_user.registration_completed_at <- Datastore kind 'web_api_users'
    (queried by uid property).registrationCompletionTime
  app_user.is_registered_to_receive_api_announcements <- Brevo is the source of truth:
    SUBSCRIBED   → True
    UNSUBSCRIBED → False
    NOT_FOUND    → field not set (left at DB default false for new rows, untouched for existing)
  app_user.migrated_at           <- now() (set by this task)

Announcements subscription (notification_subscription table):
  Every migrated user is associated with the ``api.announcements`` notification
  type. New users get the subscription created alongside their app_user row;
  existing users (including already-migrated ones) are backfilled a subscription
  if they don't already have one. The subscription is created enabled
  (``active=True``) for all users EXCEPT those explicitly UNSUBSCRIBED on Brevo,
  who get a disabled (``active=False``) subscription. Users not found on Brevo (or
  whose Brevo check failed) are treated as not unsubscribed and therefore enabled.
  This step is idempotent: users that already have the subscription are untouched.

NOT set by migration (managed by the API layer):
  app_user.updated_at
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Generator

import firebase_admin
from firebase_admin import auth
from google.cloud import datastore
from sqlalchemy.orm import Session

from shared.common.brevo import (
    BrevoSubscriptionStatus,
    get_contact_subscription_status,
)
from shared.database.database import generate_unique_id
from shared.database.users_database import with_users_db_session
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    NotificationSubscription,
)

logger = logging.getLogger(__name__)

# Primary key of the api.announcements row in the notification_type table.
# Defined locally because shared.notifications is not exposed to this module.
API_ANNOUNCEMENTS_TYPE_ID = "api.announcements"


def _get_firebase_app() -> firebase_admin.App:
    """Return the default Firebase app, initializing it once if needed."""
    try:
        return firebase_admin.get_app()
    except ValueError:
        return firebase_admin.initialize_app()


def _ms_to_datetime(ms: int | None) -> datetime:
    """Convert a Firebase millisecond timestamp to a timezone-aware datetime."""
    if ms is None:
        return datetime.now(timezone.utc)
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)


def _parse_datastore_timestamp(value) -> datetime | None:
    """Convert a Datastore timestamp value to a timezone-aware datetime, or None.

    Handles:
    - timezone-aware datetime (returned by Datastore for datetime properties)
    - naive datetime (adds UTC)
    - ISO 8601 string (stored via new Date().toJSON() in the TS user-api)
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            logger.warning("Cannot parse Datastore timestamp string: %r", value)
            return None
    logger.warning("Unrecognised Datastore timestamp type: %s", type(value))
    return None


def is_guest_user(user_record: auth.UserRecord) -> bool:
    # Anonymous users generally have no provider_data entries
    # (or no provider other than anonymous).
    providers = [p.provider_id for p in (user_record.provider_data or [])]
    return len(providers) == 0 or all(p in {"anonymous", "firebase"} for p in providers)


def _iter_users(user_ids: list[str] | None) -> Generator[auth.UserRecord, None, None]:
    """Yield Firebase Auth UserRecord objects.

    If *user_ids* is provided only those specific users are fetched.
    Otherwise all users are paginated from Firebase Auth.
    """
    if user_ids is not None:
        for uid in user_ids:
            try:
                user = auth.get_user(uid)
                if is_guest_user(user):
                    continue
                yield user
            except auth.UserNotFoundError:
                logger.warning("Firebase user not found, skipping: %s", uid)
    else:
        page = auth.list_users()
        while page:
            for user_record in page.users:
                if is_guest_user(user_record):
                    continue
                yield user_record
            page = page.get_next_page()


def _has_announcements_subscription(db_session: Session, user_id: str) -> bool:
    """Return True if the user already has an api.announcements subscription."""
    return (
        db_session.query(NotificationSubscription.id)
        .filter(
            NotificationSubscription.user_id == user_id,
            NotificationSubscription.notification_type_id == API_ANNOUNCEMENTS_TYPE_ID,
        )
        .first()
        is not None
    )


def migrate_firebase_users(
    dry_run: bool = True,
    limit: int | None = None,
    user_ids: list[str] | None = None,
    only_not_migrated: bool = True,
    db_session: Session | None = None,
) -> dict:
    """Core migration logic. Only INSERTs new users; existing rows are never modified.

    Args:
        dry_run: When True (default), reads and counts without any DB writes.
        limit: Maximum number of users to process (not skip) per run. None means no limit.
        user_ids: If provided, only these Firebase UIDs are processed.
        only_not_migrated: When True (default), skip users whose app_user row already exists
            with migrated_at set.
        db_session: Injected by the @with_users_db_session decorator.

    Returns:
        Summary dict with counts: total, inserted, skipped, no_email_skipped,
        brevo_subscribed, brevo_unsubscribed, brevo_not_found, brevo_failed,
        announcements_enabled, announcements_disabled, dry_run.
    """
    _get_firebase_app()
    ds_client = datastore.Client()

    list_id_raw = os.getenv("BREVO_API_ANNOUNCEMENTS_LIST_ID")
    announcements_list_id: int | None = None
    if list_id_raw:
        try:
            announcements_list_id = int(list_id_raw)
        except ValueError:
            logger.warning(
                "Invalid BREVO_API_ANNOUNCEMENTS_LIST_ID value %r — "
                "list-specific unsubscribe check will be skipped",
                list_id_raw,
            )

    results = {
        "total": 0,
        "inserted": 0,
        "skipped": 0,
        "no_email_skipped": 0,
        "brevo_subscribed": 0,
        "brevo_unsubscribed": 0,
        "brevo_not_found": 0,
        "brevo_failed": 0,
        "announcements_enabled": 0,
        "announcements_disabled": 0,
        "dry_run": dry_run,
    }
    processed = 0

    for user_record in _iter_users(user_ids):
        if limit is not None and processed >= limit:
            break

        results["total"] += 1

        if not user_record.email:
            logger.warning("Skipping user with no email: uid=%s", user_record.uid)
            results["no_email_skipped"] += 1
            continue

        existing: AppUser | None = db_session.get(AppUser, user_record.uid)

        # Already-migrated users are counted as skipped for the user-row
        # migration, but we still ensure their announcements subscription
        # exists below (the subscription backfill ignores only_not_migrated).
        if (
            existing is not None
            and only_not_migrated
            and existing.migrated_at is not None
        ):
            results["skipped"] += 1

        # Idempotency: every user must end up with exactly one announcements
        # subscription. New users always need one; existing users only if absent.
        needs_announcements_sub = (
            existing is None
            or not _has_announcements_subscription(db_session, user_record.uid)
        )

        # Nothing to do for an existing user that already has the subscription.
        if existing is not None and not needs_announcements_sub:
            continue

        # Datastore profile lookup is only needed when inserting a new app_user.
        doc_data: dict = {}
        if existing is None:
            query = ds_client.query(kind="web_api_users")
            query.add_filter("uid", "=", user_record.uid)
            entities = list(query.fetch(limit=1))
            entity = entities[0] if entities else None
            if entity is None:
                logger.warning("No Datastore entity found for uid=%s", user_record.uid)
            doc_data = dict(entity) if entity else {}
            if doc_data:
                logger.debug(
                    "Datastore entity keys for uid=%s: %s",
                    user_record.uid,
                    list(doc_data.keys()),
                )
            elif entity is not None:
                logger.warning(
                    "Datastore entity exists but is empty for uid=%s, profile fields will be null",
                    user_record.uid,
                )

        # Brevo is the source of truth for subscription status. Queried whenever
        # we will create the announcements subscription (new user or backfill).
        # In dry_run mode we still query Brevo so the counts are accurate.
        brevo_status: BrevoSubscriptionStatus | None = None
        try:
            brevo_status = get_contact_subscription_status(
                user_record.email, announcements_list_id
            )
            if brevo_status == BrevoSubscriptionStatus.SUBSCRIBED:
                results["brevo_subscribed"] += 1
            elif brevo_status == BrevoSubscriptionStatus.UNSUBSCRIBED:
                results["brevo_unsubscribed"] += 1
            else:
                results["brevo_not_found"] += 1
        except Exception:  # noqa: BLE001
            logger.warning(
                "Brevo check failed for uid=%s",
                user_record.uid,
            )
            results["brevo_failed"] += 1

        # The announcements subscription is enabled unless the user is explicitly
        # unsubscribed on Brevo (NOT_FOUND or a failed Brevo check are treated as
        # "not unsubscribed").
        announcements_active = brevo_status != BrevoSubscriptionStatus.UNSUBSCRIBED
        announcements_key = (
            "announcements_enabled"
            if announcements_active
            else "announcements_disabled"
        )

        if not dry_run:
            if existing is None:
                new_user = AppUser(
                    id=user_record.uid,
                    email=user_record.email,
                    email_verified=user_record.email_verified,
                    created_at=_ms_to_datetime(
                        user_record.user_metadata.creation_timestamp
                        if user_record.user_metadata
                        else None
                    ),
                    full_name=doc_data.get("fullName"),
                    legacy_org_name=doc_data.get("organization"),
                    registration_completed_at=_parse_datastore_timestamp(
                        doc_data.get("registrationCompletionTime")
                    ),
                    migrated_at=datetime.now(timezone.utc),
                )
                if (
                    brevo_status is not None
                    and brevo_status != BrevoSubscriptionStatus.NOT_FOUND
                ):
                    new_user.is_registered_to_receive_api_announcements = (
                        brevo_status == BrevoSubscriptionStatus.SUBSCRIBED
                    )
                db_session.add(new_user)
            db_session.add(
                NotificationSubscription(
                    id=generate_unique_id(),
                    user_id=user_record.uid,
                    notification_type_id=API_ANNOUNCEMENTS_TYPE_ID,
                    active=announcements_active,
                    created_at=datetime.now(timezone.utc),
                )
            )
            db_session.flush()
            if existing is None:
                results["inserted"] += 1
            results[announcements_key] += 1
        else:
            if existing is None:
                results["inserted"] += 1
            results[announcements_key] += 1

        processed += 1

    logger.info(
        "migration_completed",
        extra={
            "json_fields": {
                "task": "migrate_firebase_users",
                **results,
            }
        },
    )
    return results


@with_users_db_session
def migrate_firebase_users_handler(
    payload: dict | None = None, db_session: Session | None = None
) -> dict:
    """tasks_executor entry point.

    Payload keys (all optional):
        dry_run (bool, default True): No writes.
        limit (int, default None): Max users to process per run.
        user_ids (list[str], default None): Process only these UIDs.
        only_not_migrated (bool, default True): Skip already-migrated users.
    """
    payload = payload or {}
    logger.info("migrate_firebase_users_handler called with payload=%s", payload)

    dry_run, limit, user_ids, only_not_migrated = get_parameters(payload)

    return migrate_firebase_users(
        dry_run=dry_run,
        limit=limit,
        user_ids=user_ids,
        only_not_migrated=only_not_migrated,
        db_session=db_session,
    )


def get_parameters(payload: dict) -> tuple[bool, int | None, list[str] | None, bool]:
    """Extract and validate parameters from the payload."""
    dry_run = payload.get("dry_run", True)
    dry_run = dry_run if isinstance(dry_run, bool) else str(dry_run).lower() == "true"
    limit = payload.get("limit", None)
    if limit is not None:
        limit = int(limit)
    user_ids = payload.get("user_ids", None)
    only_not_migrated = payload.get("only_not_migrated", True)
    only_not_migrated = (
        only_not_migrated
        if isinstance(only_not_migrated, bool)
        else str(only_not_migrated).lower() == "true"
    )
    return dry_run, limit, user_ids, only_not_migrated
