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

import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from feeds_operations.impl.current_user import current_app_user
from shared.users_database_gen.sqlacodegen_models import AppUser

MODULE = "feeds_operations.impl.current_user"


def _session(result):
    session = MagicMock()
    q = session.query.return_value
    q.options.return_value = q
    q.filter.return_value = q
    q.one_or_none.return_value = result
    return session


class TestCurrentAppUser(unittest.TestCase):
    def _call(self, email, result):
        session = _session(result)
        with patch(f"{MODULE}.get_request_context", return_value={"user_email": email}):
            return current_app_user(session), session

    def test_returns_the_user_with_the_signed_in_email(self):
        user = AppUser(id="uid-1", email="Someone@MobilityData.org")

        result, session = self._call("someone@mobilitydata.org", user)

        self.assertIs(result, user)
        session.query.assert_called_once_with(AppUser)

    def test_matches_case_insensitively(self):
        _, session = self._call("Someone@MobilityData.org", AppUser(id="uid-1"))

        criterion = session.query.return_value.filter.call_args.args[0]
        self.assertEqual(criterion.right.value, "someone@mobilitydata.org")

    def test_strips_the_iap_prefix(self):
        _, session = self._call(
            "accounts.google.com:someone@mobilitydata.org", AppUser(id="uid-1")
        )

        criterion = session.query.return_value.filter.call_args.args[0]
        self.assertEqual(criterion.right.value, "someone@mobilitydata.org")

    def test_no_email_is_401(self):
        with self.assertRaises(HTTPException) as ctx:
            self._call(None, None)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_no_user_with_the_email_is_404(self):
        with self.assertRaises(HTTPException) as ctx:
            self._call("nobody@mobilitydata.org", None)
        self.assertEqual(ctx.exception.status_code, 404)
