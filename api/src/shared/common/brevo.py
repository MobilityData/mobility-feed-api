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
"""Shared Brevo API helpers.

Usage:
    from shared.common.brevo import BrevoSubscriptionStatus, get_contact_subscription_status

    status = get_contact_subscription_status(email, list_id)
    if status == BrevoSubscriptionStatus.SUBSCRIBED:
        ...
"""

from __future__ import annotations

import logging
import os
from enum import Enum

import sib_api_v3_sdk

logger = logging.getLogger(__name__)


class BrevoSubscriptionStatus(Enum):
    SUBSCRIBED = "subscribed"
    UNSUBSCRIBED = "unsubscribed"
    NOT_FOUND = "not_found"


def _get_contacts_api() -> "sib_api_v3_sdk.ContactsApi":
    """Build a Brevo ContactsApi client. Raises RuntimeError if BREVO_API_KEY is unset."""
    api_key = os.getenv("BREVO_API_KEY")
    if not api_key:
        raise RuntimeError("BREVO_API_KEY environment variable is not set")
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key["api-key"] = api_key
    return sib_api_v3_sdk.ContactsApi(sib_api_v3_sdk.ApiClient(configuration))


def get_announcements_list_id() -> int:
    """Return the Brevo API-announcements list id from BREVO_API_ANNOUNCEMENTS_LIST_ID."""
    raw = os.getenv("BREVO_API_ANNOUNCEMENTS_LIST_ID")
    if not raw:
        raise RuntimeError("BREVO_API_ANNOUNCEMENTS_LIST_ID environment variable is not set")
    return int(raw)


def add_contact_to_list(email: str, list_id: int, subscription_id: str) -> None:
    """Create/update a Brevo contact, add it to the list, and set MDB_SUBSCRIPTION_ID.

    Uses create_contact with update_enabled so it works whether or not the
    contact already exists.
    """
    api = _get_contacts_api()
    api.create_contact(
        sib_api_v3_sdk.CreateContact(
            email=email,
            attributes={"MDB_SUBSCRIPTION_ID": subscription_id},
            list_ids=[list_id],
            update_enabled=True,
        )
    )


def remove_contact_from_list(email: str, list_id: int) -> None:
    """Remove a Brevo contact from the list. No-op if the contact is not on the list."""
    api = _get_contacts_api()
    try:
        api.remove_contact_from_list(list_id, sib_api_v3_sdk.RemoveContactFromList(emails=[email]))
    except sib_api_v3_sdk.rest.ApiException as exc:
        # 400 "Contact already removed from list" / 404 contact-not-found are idempotent no-ops.
        if exc.status in (400, 404):
            logger.info("Contact %s not on list %s, nothing to remove", email, list_id)
            return
        raise


def get_contact_subscription_status(
    email: str,
    list_id: int | None = None,
) -> BrevoSubscriptionStatus:
    """Return the Brevo subscription status for a contact.

    A contact is considered UNSUBSCRIBED if:
    - email_blacklisted is True (globally unsubscribed from all campaigns), or
    - list_id is provided and appears in the contact's list_unsubscribed.

    A contact is SUBSCRIBED if it exists in Brevo and is not unsubscribed.
    NOT_FOUND is returned when the contact does not exist in Brevo.

    Raises RuntimeError if BREVO_API_KEY is not set.
    Raises sib_api_v3_sdk.rest.ApiException on unexpected API errors.
    """
    api = _get_contacts_api()

    try:
        contact = api.get_contact_info(email)
    except sib_api_v3_sdk.rest.ApiException as exc:
        if exc.status == 404:
            return BrevoSubscriptionStatus.NOT_FOUND
        raise

    if contact.email_blacklisted:
        return BrevoSubscriptionStatus.UNSUBSCRIBED
    if list_id is not None and contact.list_unsubscribed and list_id in contact.list_unsubscribed:
        return BrevoSubscriptionStatus.UNSUBSCRIBED
    return BrevoSubscriptionStatus.SUBSCRIBED
