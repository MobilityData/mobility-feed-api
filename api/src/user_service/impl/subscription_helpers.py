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
"""Helpers shared between the authenticated (users) and public (subscriptions) APIs."""

import logging
from datetime import datetime, timezone

from fastapi import HTTPException

import sib_api_v3_sdk
import urllib3
from sqlalchemy.orm import Session
from shared.common.brevo import (
    add_contact_to_list,
    get_announcements_list_id,
    remove_contact_from_list,
)
from shared.database.database import generate_unique_id
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    NotificationSubscription as NotificationSubscriptionOrm,
)

logger = logging.getLogger(__name__)

ANNOUNCEMENTS_NOTIFICATION_TYPE_ID = "api.announcements"


def sync_announcements(
    email: str,
    subscribe: bool,
    subscription_id: str | None = None,
    *,
    first_name: str | None = None,
    organization: str | None = None,
) -> None:
    """Sync an api.announcements subscription with Brevo, mapping provider errors to 502.
    For simplicity, the Brevo `FIRSTNAME` contact field is populated with the full name.
    """
    try:
        if subscribe:
            add_contact_to_list(
                email,
                get_announcements_list_id(),
                subscription_id,
                first_name=first_name,
                organization=organization,
            )
        else:
            remove_contact_from_list(email, get_announcements_list_id())
    except (
        RuntimeError,
        sib_api_v3_sdk.rest.ApiException,
        urllib3.exceptions.HTTPError,
        OSError,
    ) as exc:
        # urllib3.exceptions.HTTPError / OSError cover connection failures and timeouts (e.g. Brevo
        # unreachable), so the request fails fast with a 502 instead of hanging on retries.
        logger.error("Brevo sync failed for %s: %s", email, exc)
        raise HTTPException(status_code=502, detail="Failed to sync subscription with email provider.")


def set_announcements_optin(
    db_session: Session,
    user: AppUser,
    subscribe: bool,
    *,
    subscription: NotificationSubscriptionOrm | None = None,
    release_connection_before_brevo: bool = False,
) -> NotificationSubscriptionOrm | None:
    """Reconcile a user's api.announcements opt-in across all three representations
    that must agree: the notification_subscription row, Brevo list membership, and
    app_user.is_registered_to_receive_api_announcements. Idempotent.

    subscribe=True  → create/reactivate the subscription, add the contact to the
                      Brevo list with its MDB_SUBSCRIPTION_ID, set the flag True.
    subscribe=False → deactivate the subscription (api.announcements is never
                      deleted, only disabled), remove the contact from the Brevo
                      list, set the flag False.
    Returns the subscription row (None only when unsubscribing a user that has no
    subscription row).

    ``subscription``: the caller's already-loaded announcements subscription, if it
    has one (endpoints that address a subscription by id). When omitted the row is
    looked up by user + type (there is at most one announcements subscription per
    user).

    ``release_connection_before_brevo`` commits the pending transaction before the
    Brevo call so a slow/unreachable provider does not hold a pooled DB connection.
    Only pass True when there are no pending writes you would want rolled back if
    the Brevo call fails (e.g. the delete endpoints, which only read beforehand).
    On the subscribe path the connection is always held so the whole change stays
    atomic (a Brevo failure rolls the new subscription + flag back).
    """
    existing = subscription
    if existing is None:
        existing = (
            db_session.query(NotificationSubscriptionOrm)
            .filter(
                NotificationSubscriptionOrm.user_id == user.id,
                NotificationSubscriptionOrm.notification_type_id == ANNOUNCEMENTS_NOTIFICATION_TYPE_ID,
            )
            .one_or_none()
        )

    if subscribe:
        sub = existing or NotificationSubscriptionOrm(
            id=generate_unique_id(),
            user_id=user.id,
            notification_type_id=ANNOUNCEMENTS_NOTIFICATION_TYPE_ID,
            created_at=datetime.now(timezone.utc),
        )
        sub.active = True
        if existing is None:
            db_session.add(sub)
        sync_announcements(
            user.email,
            subscribe=True,
            subscription_id=sub.id,
            first_name=user.full_name,
            organization=user.legacy_org_name,
        )
        user.is_registered_to_receive_api_announcements = True
        return sub

    # Unsubscribe. Capture the email before any commit so we never trigger a
    # reload of the (possibly expired) user just to read it during the Brevo call.
    email = user.email
    if release_connection_before_brevo:
        db_session.commit()
    sync_announcements(email, subscribe=False)
    if existing is not None:
        existing.active = False
    user.is_registered_to_receive_api_announcements = False
    return existing
