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
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import sib_api_v3_sdk

from shared.common import brevo
from shared.common.brevo import BrevoSubscriptionStatus


def _contact(list_ids=None, list_unsubscribed=None, email_blacklisted=False, attributes=None):
    return SimpleNamespace(
        list_ids=list_ids,
        list_unsubscribed=list_unsubscribed,
        email_blacklisted=email_blacklisted,
        attributes=attributes,
    )


def _state(contact):
    api = MagicMock()
    api.get_contact_info.return_value = contact
    with patch.object(brevo, "_get_contacts_api", return_value=api):
        return brevo.get_contact_list_state("a@b.com", 42)


def test_subscribed_member():
    state = _state(_contact(list_ids=[42, 7], attributes={}))

    assert state.status == BrevoSubscriptionStatus.SUBSCRIBED
    assert state.in_list is True
    assert state.list_unsubscribed is False
    assert state.email_blacklisted is False


def test_contact_not_on_the_list():
    state = _state(_contact(list_ids=[7], attributes={}))

    assert state.status == BrevoSubscriptionStatus.SUBSCRIBED
    assert state.in_list is False


def test_unsubscribed_from_the_list():
    state = _state(_contact(list_ids=[], list_unsubscribed=[42]))

    assert state.status == BrevoSubscriptionStatus.UNSUBSCRIBED
    assert state.list_unsubscribed is True
    assert state.in_list is False


def test_blacklisted_contact():
    state = _state(_contact(list_ids=[42], email_blacklisted=True))

    assert state.status == BrevoSubscriptionStatus.UNSUBSCRIBED
    assert state.email_blacklisted is True
    assert state.in_list is True


def test_missing_contact_is_not_found():
    api = MagicMock()
    api.get_contact_info.side_effect = sib_api_v3_sdk.rest.ApiException(status=404)
    with patch.object(brevo, "_get_contacts_api", return_value=api):
        state = brevo.get_contact_list_state("a@b.com", 42)

    assert state.status == BrevoSubscriptionStatus.NOT_FOUND
    assert state.in_list is False


def test_other_api_errors_propagate():
    api = MagicMock()
    api.get_contact_info.side_effect = sib_api_v3_sdk.rest.ApiException(status=500)
    with patch.object(brevo, "_get_contacts_api", return_value=api):
        with pytest.raises(sib_api_v3_sdk.rest.ApiException):
            brevo.get_contact_list_state("a@b.com", 42)


def test_subscription_status_without_a_list_ignores_list_unsubscribes():
    api = MagicMock()
    api.get_contact_info.return_value = _contact(list_ids=[], list_unsubscribed=[42])
    with patch.object(brevo, "_get_contacts_api", return_value=api):
        assert brevo.get_contact_subscription_status("a@b.com") == BrevoSubscriptionStatus.SUBSCRIBED
        assert brevo.get_contact_subscription_status("a@b.com", 42) == BrevoSubscriptionStatus.UNSUBSCRIBED


def test_subscription_status_not_found():
    api = MagicMock()
    api.get_contact_info.side_effect = sib_api_v3_sdk.rest.ApiException(status=404)
    with patch.object(brevo, "_get_contacts_api", return_value=api):
        assert brevo.get_contact_subscription_status("a@b.com", 42) == BrevoSubscriptionStatus.NOT_FOUND


def _blocked(email, code="unsubscribedViaEmail"):
    return {
        "email": email,
        "senderEmail": "noreply@example.com",
        "reason": {"code": code, "message": "Unsubscribed via email"},
        "blockedAt": "2026-11-23T08:00:00.000Z",
    }


def _page(count, contacts):
    """A raw (_preload_content=False) blocked contacts response."""
    return SimpleNamespace(data=json.dumps({"count": count, "contacts": contacts}).encode())


def _block(pages):
    api = MagicMock()
    api.get_transac_blocked_contacts.side_effect = pages
    with patch.object(brevo, "_get_transactional_api", return_value=api):
        return brevo.get_transactional_block("A@B.com"), api


def test_transactional_block_found_on_a_later_page():
    first = _page(101, [_blocked(f"x{i}@b.com") for i in range(100)])
    second = _page(101, [_blocked("a@b.com")])

    block, api = _block([first, second])

    assert block.reason_code == "unsubscribedViaEmail"
    assert block.reason_message == "Unsubscribed via email"
    assert block.sender_email == "noreply@example.com"
    assert block.blocked_at == "2026-11-23T08:00:00.000Z"
    assert api.get_transac_blocked_contacts.call_args_list[1].kwargs["offset"] == 100


def test_transactional_block_none_when_not_listed():
    block, api = _block([_page(1, [_blocked("other@b.com")])])

    assert block is None
    api.get_transac_blocked_contacts.assert_called_once()


def test_transactional_block_none_when_list_is_empty():
    block, _ = _block([_page(0, None)])

    assert block is None


def test_transactional_block_tolerates_entries_the_sdk_would_reject():
    odd = {"email": "x@b.com", "reason": {"code": "someNewCode"}}
    block, _ = _block([_page(2, [odd, {"email": "a@b.com", "reason": {"code": "someNewCode"}}])])

    assert block.reason_code == "someNewCode"
    assert block.sender_email is None
    assert block.blocked_at is None


def test_unblock_transactional_contact():
    api = MagicMock()
    with patch.object(brevo, "_get_transactional_api", return_value=api):
        brevo.unblock_transactional_contact("a@b.com")

    assert api.smtp_blocked_contacts_email_delete.call_args.args == ("a@b.com",)
