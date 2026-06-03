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
    api_key = os.getenv("BREVO_API_KEY")
    if not api_key:
        raise RuntimeError("BREVO_API_KEY environment variable is not set")

    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key["api-key"] = api_key
    api = sib_api_v3_sdk.ContactsApi(sib_api_v3_sdk.ApiClient(configuration))

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
