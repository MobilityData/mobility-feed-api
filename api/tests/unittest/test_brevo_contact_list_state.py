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


def test_subscribed_member_with_subscription_id():
    state = _state(_contact(list_ids=[42, 7], attributes={"MDB_SUBSCRIPTION_ID": "sub-1"}))

    assert state.status == BrevoSubscriptionStatus.SUBSCRIBED
    assert state.in_list is True
    assert state.list_unsubscribed is False
    assert state.email_blacklisted is False
    assert state.mdb_subscription_id == "sub-1"


def test_contact_not_on_the_list():
    state = _state(_contact(list_ids=[7], attributes={}))

    assert state.status == BrevoSubscriptionStatus.SUBSCRIBED
    assert state.in_list is False
    assert state.mdb_subscription_id is None


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
    assert state.mdb_subscription_id is None


def test_other_api_errors_propagate():
    api = MagicMock()
    api.get_contact_info.side_effect = sib_api_v3_sdk.rest.ApiException(status=500)
    with patch.object(brevo, "_get_contacts_api", return_value=api):
        with pytest.raises(sib_api_v3_sdk.rest.ApiException):
            brevo.get_contact_list_state("a@b.com", 42)
