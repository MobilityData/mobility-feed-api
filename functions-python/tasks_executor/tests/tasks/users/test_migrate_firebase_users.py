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
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from tasks.users.migrate_firebase_users import (
    migrate_firebase_users,
    migrate_firebase_users_handler,
    _ms_to_datetime,
    _parse_datastore_timestamp,
)
from shared.common.brevo import BrevoSubscriptionStatus
from shared.users_database_gen.sqlacodegen_models import AppUser

BREVO_MODULE = "tasks.users.migrate_firebase_users.get_contact_subscription_status"


def _make_auth_user(
    uid, email="user@example.com", email_verified=True, created_ms=1_000_000_000_000
):
    user = MagicMock()
    user.uid = uid
    user.email = email
    user.email_verified = email_verified
    user.user_metadata = MagicMock()
    user.user_metadata.creation_timestamp = created_ms
    provider = MagicMock()
    provider.provider_id = "password"
    user.provider_data = [provider]
    return user


def _make_db_session(existing_user=None):
    session = MagicMock()
    session.get.return_value = existing_user
    return session


def _make_ds_client(entities: dict):
    """Return a mock Datastore client where query.fetch() looks up by uid property."""
    ds_client = MagicMock()

    def _make_query(kind):
        query = MagicMock()
        uid_filter = {}

        def _add_filter(prop, op, val):
            uid_filter["uid"] = val

        query.add_filter.side_effect = _add_filter
        query.fetch.side_effect = lambda limit=None: iter(
            [entities[uid_filter["uid"]]] if uid_filter.get("uid") in entities else []
        )
        return query

    ds_client.query.side_effect = _make_query
    return ds_client


class TestHelpers(unittest.TestCase):
    def test_ms_to_datetime_converts_correctly(self):
        self.assertEqual(_ms_to_datetime(0), datetime(1970, 1, 1, tzinfo=timezone.utc))

    def test_ms_to_datetime_none_returns_now(self):
        self.assertIsNotNone(_ms_to_datetime(None).tzinfo)

    def test_parse_datastore_timestamp_none(self):
        self.assertIsNone(_parse_datastore_timestamp(None))

    def test_parse_datastore_timestamp_aware_datetime(self):
        dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        self.assertEqual(_parse_datastore_timestamp(dt), dt)

    def test_parse_datastore_timestamp_naive_datetime(self):
        self.assertIsNotNone(_parse_datastore_timestamp(datetime(2024, 1, 1)).tzinfo)

    def test_parse_datastore_timestamp_iso_string(self):
        """registrationCompletionTime is stored as new Date().toJSON() — an ISO string."""
        result = _parse_datastore_timestamp("2023-06-01T12:00:00.000Z")
        self.assertEqual(result, datetime(2023, 6, 1, 12, 0, 0, tzinfo=timezone.utc))

    def test_parse_datastore_timestamp_invalid_string(self):
        self.assertIsNone(_parse_datastore_timestamp("not-a-date"))


class TestHandlerDefaults(unittest.TestCase):
    @patch("tasks.users.migrate_firebase_users.migrate_firebase_users")
    def test_handler_passes_defaults(self, mock_migrate):
        mock_migrate.return_value = {"total": 0, "dry_run": True}
        result = migrate_firebase_users_handler.__wrapped__(
            payload=None, db_session=MagicMock()
        )
        mock_migrate.assert_called_once_with(
            dry_run=True,
            limit=None,
            user_ids=None,
            only_not_migrated=True,
            db_session=mock_migrate.call_args.kwargs["db_session"],
        )
        self.assertTrue(result["dry_run"])

    @patch("tasks.users.migrate_firebase_users.migrate_firebase_users")
    def test_handler_passes_explicit_params(self, mock_migrate):
        mock_migrate.return_value = {"total": 5}
        payload = {
            "dry_run": False,
            "limit": 10,
            "user_ids": ["uid1"],
            "only_not_migrated": False,
        }
        migrate_firebase_users_handler.__wrapped__(
            payload=payload, db_session=MagicMock()
        )
        kw = mock_migrate.call_args.kwargs
        self.assertFalse(kw["dry_run"])
        self.assertEqual(kw["limit"], 10)
        self.assertFalse(kw["only_not_migrated"])


class TestMigrateFirebaseUsers(unittest.TestCase):
    """Unit tests for migrate_firebase_users() — only INSERTs new users."""

    def _run(
        self,
        user_records,
        datastore_data,
        db_session,
        brevo_status=BrevoSubscriptionStatus.NOT_FOUND,
        **kwargs,
    ):
        ds_client = _make_ds_client(datastore_data)
        with (
            patch("tasks.users.migrate_firebase_users._get_firebase_app"),
            patch("tasks.users.migrate_firebase_users.datastore") as mock_datastore,
            patch(
                "tasks.users.migrate_firebase_users._iter_users",
                return_value=iter(user_records),
            ),
            patch(BREVO_MODULE, return_value=brevo_status),
        ):
            mock_datastore.Client.return_value = ds_client
            return migrate_firebase_users(db_session=db_session, **kwargs)

    # --- INSERT path ---

    def test_new_user_full_data_inserted(self):
        """New user is inserted with all Datastore fields mapped."""
        user = _make_auth_user("uid1", email="alice@example.com")
        reg_time = datetime(2023, 6, 1, tzinfo=timezone.utc)
        ds_data = {
            "uid1": {
                "fullName": "Alice",
                "organization": "Transit Corp",
                "registrationCompletionTime": reg_time,
            }
        }
        session = _make_db_session()

        stats = self._run([user], ds_data, session, dry_run=False)

        self.assertEqual(stats["inserted"], 1)
        added: AppUser = session.add.call_args[0][0]
        self.assertEqual(added.id, "uid1")
        self.assertEqual(added.email, "alice@example.com")
        self.assertEqual(added.full_name, "Alice")
        self.assertEqual(added.legacy_org_name, "Transit Corp")
        self.assertEqual(added.registration_completed_at, reg_time)
        self.assertIsNotNone(added.migrated_at)

    def test_new_user_brevo_subscribed_sets_true(self):
        """New user subscribed in Brevo → field=True on insert."""
        user = _make_auth_user("uid2", email="b@example.com")
        session = _make_db_session()

        self._run(
            [user],
            {},
            session,
            brevo_status=BrevoSubscriptionStatus.SUBSCRIBED,
            dry_run=False,
        )

        added: AppUser = session.add.call_args[0][0]
        self.assertTrue(added.is_registered_to_receive_api_announcements)

    def test_new_user_brevo_unsubscribed_sets_false(self):
        """New user unsubscribed in Brevo → field=False on insert."""
        user = _make_auth_user("uid3", email="c@example.com")
        session = _make_db_session()

        self._run(
            [user],
            {},
            session,
            brevo_status=BrevoSubscriptionStatus.UNSUBSCRIBED,
            dry_run=False,
        )

        added: AppUser = session.add.call_args[0][0]
        self.assertFalse(added.is_registered_to_receive_api_announcements)

    def test_new_user_brevo_not_found_field_not_set(self):
        """New user not in Brevo → field not set (None, DB default applies)."""
        user = _make_auth_user("uid4", email="d@example.com")
        session = _make_db_session()

        self._run(
            [user],
            {},
            session,
            brevo_status=BrevoSubscriptionStatus.NOT_FOUND,
            dry_run=False,
        )

        added: AppUser = session.add.call_args[0][0]
        self.assertIsNone(added.is_registered_to_receive_api_announcements)

    # --- Existing users are never updated ---

    def test_existing_user_skipped_no_db_write_no_brevo(self):
        """Existing user (any state) → skipped, no DB write, no Brevo call."""
        user = _make_auth_user("uid5")
        existing = AppUser(id="uid5", email="e@example.com", migrated_at=None)
        session = _make_db_session(existing)

        ds_client = _make_ds_client({})
        with (
            patch("tasks.users.migrate_firebase_users._get_firebase_app"),
            patch("tasks.users.migrate_firebase_users.datastore") as mock_datastore,
            patch(
                "tasks.users.migrate_firebase_users._iter_users",
                return_value=iter([user]),
            ),
            patch(BREVO_MODULE) as mock_brevo,
        ):
            mock_datastore.Client.return_value = ds_client
            stats = migrate_firebase_users(db_session=session, dry_run=False)

        session.add.assert_not_called()
        session.flush.assert_not_called()
        mock_brevo.assert_not_called()
        self.assertEqual(stats["inserted"], 0)

    def test_existing_migrated_user_counted_as_skipped(self):
        """Existing user with migrated_at set → counted in skipped when only_not_migrated=True."""
        user = _make_auth_user("uid6")
        existing = AppUser(
            id="uid6", email="f@example.com", migrated_at=datetime.now(timezone.utc)
        )
        session = _make_db_session(existing)

        stats = self._run([user], {}, session, dry_run=False, only_not_migrated=True)

        self.assertEqual(stats["skipped"], 1)
        self.assertEqual(stats["inserted"], 0)

    def test_existing_user_not_counted_as_skipped_when_flag_off(self):
        """Existing user with only_not_migrated=False → not counted in skipped (just bypassed)."""
        user = _make_auth_user("uid7")
        existing = AppUser(
            id="uid7", email="g@example.com", migrated_at=datetime.now(timezone.utc)
        )
        session = _make_db_session(existing)

        stats = self._run([user], {}, session, dry_run=False, only_not_migrated=False)

        self.assertEqual(stats["skipped"], 0)
        self.assertEqual(stats["inserted"], 0)

    # --- Brevo failure on new user ---

    def test_brevo_failure_on_new_user_does_not_abort(self):
        """Brevo API error on new user → migration continues, field not set."""
        user = _make_auth_user("uid8", email="h@example.com")
        session = _make_db_session()

        ds_client = _make_ds_client({})
        with (
            patch("tasks.users.migrate_firebase_users._get_firebase_app"),
            patch("tasks.users.migrate_firebase_users.datastore") as mock_datastore,
            patch(
                "tasks.users.migrate_firebase_users._iter_users",
                return_value=iter([user]),
            ),
            patch(BREVO_MODULE, side_effect=Exception("Brevo down")),
        ):
            mock_datastore.Client.return_value = ds_client
            stats = migrate_firebase_users(db_session=session, dry_run=False)

        self.assertEqual(stats["brevo_failed"], 1)
        self.assertEqual(stats["inserted"], 1)
        added: AppUser = session.add.call_args[0][0]
        self.assertIsNone(added.is_registered_to_receive_api_announcements)

    # --- dry_run ---

    def test_dry_run_no_db_writes_brevo_still_queried(self):
        """dry_run=True: no DB writes, but Brevo is still queried for accurate counts."""
        user = _make_auth_user("uid9")
        session = _make_db_session()

        ds_client = _make_ds_client({})
        with (
            patch("tasks.users.migrate_firebase_users._get_firebase_app"),
            patch("tasks.users.migrate_firebase_users.datastore") as mock_datastore,
            patch(
                "tasks.users.migrate_firebase_users._iter_users",
                return_value=iter([user]),
            ),
            patch(
                BREVO_MODULE, return_value=BrevoSubscriptionStatus.SUBSCRIBED
            ) as mock_brevo,
        ):
            mock_datastore.Client.return_value = ds_client
            stats = migrate_firebase_users(db_session=session, dry_run=True)

        self.assertTrue(stats["dry_run"])
        self.assertEqual(stats["inserted"], 1)
        self.assertEqual(stats["brevo_subscribed"], 1)
        session.add.assert_not_called()
        session.flush.assert_not_called()
        mock_brevo.assert_called_once()

    # --- misc ---

    def test_user_without_email_is_skipped(self):
        user = _make_auth_user("uid10", email=None)
        user.email = None
        session = _make_db_session()

        stats = self._run([user], {}, session, dry_run=False)

        self.assertEqual(stats["no_email_skipped"], 1)
        session.add.assert_not_called()

    def test_limit_stops_after_n_processed(self):
        users = [
            _make_auth_user(f"uid{i}", email=f"u{i}@example.com") for i in range(5)
        ]
        session = _make_db_session()

        stats = self._run(users, {}, session, dry_run=True, limit=1)

        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["inserted"], 1)

    def test_user_ids_param_uses_get_user(self):
        ds_client = _make_ds_client({})
        with (
            patch("tasks.users.migrate_firebase_users._get_firebase_app"),
            patch("tasks.users.migrate_firebase_users.datastore") as mock_datastore,
            patch("tasks.users.migrate_firebase_users.auth") as mock_auth,
            patch(BREVO_MODULE, return_value=BrevoSubscriptionStatus.NOT_FOUND),
        ):
            mock_datastore.Client.return_value = ds_client
            user = _make_auth_user("uid11", email="j@example.com")
            mock_auth.get_user.return_value = user
            mock_auth.UserNotFoundError = Exception
            session = _make_db_session()
            stats = migrate_firebase_users(
                dry_run=True, user_ids=["uid11"], db_session=session
            )

        mock_auth.get_user.assert_called_once_with("uid11")
        self.assertEqual(stats["inserted"], 1)


if __name__ == "__main__":
    unittest.main()
