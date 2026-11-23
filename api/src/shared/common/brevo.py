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

import json
import logging
import os
from dataclasses import dataclass
from enum import Enum

import sib_api_v3_sdk
import urllib3

logger = logging.getLogger(__name__)

# (connect, read) timeout in seconds for every Brevo API call. Without this the SDK uses no
# timeout, so when Brevo is unreachable the underlying urllib3 retries hang for a long time while
# holding the caller's DB connection from the pool, which can exhaust the pool and make requests
# appear "stuck". A short connect timeout makes the failure fast and bounded.
BREVO_REQUEST_TIMEOUT = (3.05, 10)

# Do not retry on connection failures. The Brevo call runs inside an async FastAPI route (which
# executes on the event loop), so a long retry loop would block the whole API, not just this
# request. With no retries, an unreachable Brevo fails within ~the connect timeout above.
_BREVO_RETRIES = urllib3.Retry(total=0, connect=0, read=0, redirect=0, status=0)


class BrevoSubscriptionStatus(Enum):
    SUBSCRIBED = "subscribed"
    UNSUBSCRIBED = "unsubscribed"
    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class BrevoContactListState:
    """What Brevo holds for one contact with respect to one list."""

    status: BrevoSubscriptionStatus
    in_list: bool = False
    email_blacklisted: bool = False
    list_unsubscribed: bool = False


@dataclass(frozen=True)
class BrevoTransactionalBlock:
    """A contact on Brevo's transactional blocklist: Brevo drops every transactional email to it.

    Set, for example, when the user clicks "unsubscribe" in a transactional email. This list is
    separate from the contact's campaign blacklist and list memberships.
    """

    sender_email: str | None = None
    reason_code: str | None = None
    reason_message: str | None = None
    blocked_at: str | None = None


# Page size for the blocked contacts listing; Brevo allows at most 100.
_BLOCKED_CONTACTS_PAGE_SIZE = 100


def _configure(api):
    # Disable urllib3 retries so a connection failure fails fast instead of looping.
    api.api_client.rest_client.pool_manager.connection_pool_kw["retries"] = _BREVO_RETRIES
    return api


def _api_client() -> "sib_api_v3_sdk.ApiClient":
    """Build a Brevo ApiClient. Raises RuntimeError if BREVO_API_KEY is unset."""
    api_key = os.getenv("BREVO_API_KEY")
    if not api_key:
        raise RuntimeError("BREVO_API_KEY environment variable is not set")
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key["api-key"] = api_key
    return sib_api_v3_sdk.ApiClient(configuration)


def _get_transactional_api() -> "sib_api_v3_sdk.TransactionalEmailsApi":
    """Build a Brevo TransactionalEmailsApi client. Raises RuntimeError if BREVO_API_KEY is unset."""
    return _configure(sib_api_v3_sdk.TransactionalEmailsApi(_api_client()))


def _get_contacts_api() -> "sib_api_v3_sdk.ContactsApi":
    """Build a Brevo ContactsApi client. Raises RuntimeError if BREVO_API_KEY is unset."""
    return _configure(sib_api_v3_sdk.ContactsApi(_api_client()))


def get_announcements_list_id() -> int:
    """Return the Brevo API-announcements list id from BREVO_API_ANNOUNCEMENTS_LIST_ID."""
    raw = os.getenv("BREVO_API_ANNOUNCEMENTS_LIST_ID")
    if not raw:
        raise RuntimeError("BREVO_API_ANNOUNCEMENTS_LIST_ID environment variable is not set")
    return int(raw)


def add_contact_to_list(
    email: str,
    list_id: int,
    *,
    first_name: str | None = None,
    organization: str | None = None,
    resubscribe: bool = False,
) -> None:
    """Create/update a Brevo contact, add it to the list, and set its attributes.

    When provided, sets the standard FIRSTNAME attribute (from the user's full name) and the
    ORGANIZATION attribute (from the user's legacy organization name). For simplicity, the Brevo
    `FIRSTNAME` contact field is populated with the full name.
    Attributes whose value is None are omitted so we never overwrite an existing Brevo value with a blank.

    ``resubscribe`` also clears the contact's global email blacklist (set when the user clicked
    "unsubscribe" in a Brevo email). Only pass True for an explicit opt-in by the user: without it
    Brevo keeps blocking the contact, and the daily reconcile_announcements_from_brevo job would
    turn the subscription back off. Left unset, the blacklist is not sent and stays as it is.

    Uses create_contact with update_enabled so it works whether or not the
    contact already exists.
    """
    attributes = {}
    if first_name is not None:
        attributes["FIRSTNAME"] = first_name
    if organization is not None:
        attributes["ORGANIZATION"] = organization
    api = _get_contacts_api()
    api.create_contact(
        sib_api_v3_sdk.CreateContact(
            email=email,
            attributes=attributes or None,
            list_ids=[list_id],
            update_enabled=True,
            email_blacklisted=False if resubscribe else None,
        ),
        _request_timeout=BREVO_REQUEST_TIMEOUT,
    )


def remove_contact_from_list(email: str, list_id: int) -> None:
    """Remove a Brevo contact from the list. No-op if the contact is not on the list."""
    api = _get_contacts_api()
    try:
        api.remove_contact_from_list(
            list_id,
            sib_api_v3_sdk.RemoveContactFromList(emails=[email]),
            _request_timeout=BREVO_REQUEST_TIMEOUT,
        )
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

    The status rule lives in ``get_contact_list_state``; this is its ``status`` alone.

    Raises RuntimeError if BREVO_API_KEY is not set.
    Raises sib_api_v3_sdk.rest.ApiException on unexpected API errors.
    """
    return get_contact_list_state(email, list_id).status


def get_contact_list_state(email: str, list_id: int | None = None) -> BrevoContactListState:
    """Return a contact's membership of a list and its unsubscribe flags.

    Read-only. ``status`` is:
    - UNSUBSCRIBED if email_blacklisted is True (globally unsubscribed from all
      campaigns), or list_id is provided and appears in the contact's list_unsubscribed;
    - SUBSCRIBED if the contact exists and is not unsubscribed. This does not mean it
      is on the list: check ``in_list`` for that;
    - NOT_FOUND when the contact does not exist in Brevo.
    The other fields expose the raw values ``status`` is derived from, so a caller can
    tell "unsubscribed from this list" apart from "never added to it". With no list_id,
    the list fields are False.

    Raises RuntimeError if BREVO_API_KEY is not set.
    Raises sib_api_v3_sdk.rest.ApiException on unexpected API errors.
    """
    api = _get_contacts_api()

    try:
        contact = api.get_contact_info(email, _request_timeout=BREVO_REQUEST_TIMEOUT)
    except sib_api_v3_sdk.rest.ApiException as exc:
        if exc.status == 404:
            return BrevoContactListState(status=BrevoSubscriptionStatus.NOT_FOUND)
        raise

    email_blacklisted = bool(contact.email_blacklisted)
    list_unsubscribed = list_id in (contact.list_unsubscribed or [])
    return BrevoContactListState(
        status=(
            BrevoSubscriptionStatus.UNSUBSCRIBED
            if email_blacklisted or list_unsubscribed
            else BrevoSubscriptionStatus.SUBSCRIBED
        ),
        in_list=list_id in (contact.list_ids or []),
        email_blacklisted=email_blacklisted,
        list_unsubscribed=list_unsubscribed,
    )


def get_transactional_block(email: str) -> BrevoTransactionalBlock | None:
    """Return the contact's entry on Brevo's transactional blocklist, or None when not blocked.

    Brevo cannot filter the blocklist by email, so this pages through it (100 entries per call)
    until the contact is found. Read-only.

    The raw JSON is read instead of the SDK models: those reject an entry with a missing field or
    a reason code the SDK does not know, which would fail the whole page.

    Raises RuntimeError if BREVO_API_KEY is not set.
    Raises sib_api_v3_sdk.rest.ApiException on unexpected API errors.
    """
    api = _get_transactional_api()
    wanted = email.strip().lower()
    offset = 0
    while True:
        response = api.get_transac_blocked_contacts(
            limit=_BLOCKED_CONTACTS_PAGE_SIZE,
            offset=offset,
            _request_timeout=BREVO_REQUEST_TIMEOUT,
            _preload_content=False,
        )
        page = json.loads(response.data or b"{}")
        contacts = page.get("contacts") or []
        for contact in contacts:
            if (contact.get("email") or "").strip().lower() == wanted:
                reason = contact.get("reason") or {}
                return BrevoTransactionalBlock(
                    sender_email=contact.get("senderEmail"),
                    reason_code=reason.get("code"),
                    reason_message=reason.get("message"),
                    blocked_at=contact.get("blockedAt"),
                )
        offset += len(contacts)
        if not contacts or offset >= (page.get("count") or 0):
            return None


def unblock_transactional_contact(email: str) -> bool:
    """Remove the contact from Brevo's transactional blocklist, so transactional emails reach it again.

    Only call this when the user asked to receive those emails again: a block is usually the
    user's own "unsubscribe" click. Returns False when the contact was not blocked (Brevo
    answers 404), so it can be called on every opt-in without looking the block up first.

    Raises RuntimeError if BREVO_API_KEY is not set.
    Raises sib_api_v3_sdk.rest.ApiException on other API errors.
    """
    api = _get_transactional_api()
    try:
        api.smtp_blocked_contacts_email_delete(email, _request_timeout=BREVO_REQUEST_TIMEOUT)
    except sib_api_v3_sdk.rest.ApiException as exc:
        if exc.status == 404:
            return False
        raise
    return True
