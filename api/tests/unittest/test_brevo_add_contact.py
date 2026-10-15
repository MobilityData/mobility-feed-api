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
from unittest.mock import MagicMock, patch

from shared.common import brevo


def _sent_contact(api_mock):
    """Return the CreateContact object passed to create_contact()."""
    return api_mock.create_contact.call_args[0][0]


def test_add_contact_sets_only_subscription_id_by_default():
    api = MagicMock()
    with patch.object(brevo, "_get_contacts_api", return_value=api):
        brevo.add_contact_to_list("a@b.com", 42, "sub-1")

    contact = _sent_contact(api)
    assert contact.attributes == {"MDB_SUBSCRIPTION_ID": "sub-1"}
    assert contact.list_ids == [42]
    assert contact.update_enabled is True


def test_add_contact_includes_firstname_and_organization_when_provided():
    api = MagicMock()
    with patch.object(brevo, "_get_contacts_api", return_value=api):
        brevo.add_contact_to_list("a@b.com", 42, "sub-1", first_name="Jane Doe", organization="Acme Transit")

    assert _sent_contact(api).attributes == {
        "MDB_SUBSCRIPTION_ID": "sub-1",
        "FIRSTNAME": "Jane Doe",
        "ORGANIZATION": "Acme Transit",
    }


def test_add_contact_omits_none_attributes():
    api = MagicMock()
    with patch.object(brevo, "_get_contacts_api", return_value=api):
        brevo.add_contact_to_list("a@b.com", 42, "sub-1", first_name=None, organization="Acme Transit")

    attributes = _sent_contact(api).attributes
    assert "FIRSTNAME" not in attributes  # None is omitted, not blanked
    assert attributes["ORGANIZATION"] == "Acme Transit"
    assert attributes["MDB_SUBSCRIPTION_ID"] == "sub-1"
