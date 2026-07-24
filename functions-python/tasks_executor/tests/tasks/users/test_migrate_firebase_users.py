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
import os
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
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    NotificationSubscription,
)

BREVO_MODULE = "tasks.users.migrate_firebase_users.get_contact_subscription_status"


def _added_of_type(session, cls):
    """Return the single object of *cls* passed to session.add(), or None."""
    matches = [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], cls)
    ]
    return matches[0] if matches else None


def _added_app_user(session) -> AppUser:
    return _added_of_type(session, AppUser)


def _added_subscription(session) -> NotificationSubscription:
    return _added_of_type(session, NotificationSubscription)


_DEFAULT = object()  # sentinel for _make_db_session's existing_sub


def _make_subscription(user_id, sub_id="sub-existing", active=True):
    """Build an existing api.announcements subscription row for the DB mock."""
    return NotificationSubscription(
        id=sub_id,
        user_id=user_id,
        notification_type_id="api.announcements",
        active=active,
    )


def _make_app_user(
    uid,
    email=None,
    migrated_at=_DEFAULT,
    brevo_synced_at=None,
    full_name=None,
    legacy_org_name=None,
):
    """Build an existing app_user row. brevo_synced_at drives the write-back
    idempotency check (None = contact not yet synced)."""
    if migrated_at is _DEFAULT:
        migrated_at = datetime.now(timezone.utc)
    return AppUser(
        id=uid,
        email=email or f"{uid}@example.com",
        migrated_at=migrated_at,
        brevo_synced_at=brevo_synced_at,
        full_name=full_name,
        legacy_org_name=legacy_org_name,
    )


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


def _make_db_session(
    existing_user=None, has_announcements_sub=True, existing_sub=_DEFAULT
):
    session = MagicMock()
    session.get.return_value = existing_user
    # Controls _get_announcements_subscription(): .first() returns the existing
    # subscription row (or None). A brand-new user (existing_user is None) never
    # has one. For an existing user, has_announcements_sub picks whether a
    # subscription row exists; pass existing_sub to override with a specific row
    # (e.g. to assert the id written back to Brevo). The write-back idempotency
    # state now lives on the app_user (brevo_synced_at), not the subscription.
    if existing_sub is _DEFAULT:
        if existing_user is not None and has_announcements_sub:
            existing_sub = _make_subscription(existing_user.id)
        else:
            existing_sub = None
    session.query.return_value.filter.return_value.first.return_value = existing_sub
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
        added: AppUser = _added_app_user(session)
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

        added: AppUser = _added_app_user(session)
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

        added: AppUser = _added_app_user(session)
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

        added: AppUser = _added_app_user(session)
        self.assertIsNone(added.is_registered_to_receive_api_announcements)

    # --- Announcements subscription association ---

    def test_new_user_gets_enabled_announcements_subscription_when_subscribed(self):
        user = _make_auth_user("uid-sub", email="sub@example.com")
        session = _make_db_session()

        stats = self._run(
            [user],
            {},
            session,
            brevo_status=BrevoSubscriptionStatus.SUBSCRIBED,
            dry_run=False,
        )

        sub = _added_subscription(session)
        self.assertIsNotNone(sub)
        self.assertEqual(sub.user_id, "uid-sub")
        self.assertEqual(sub.notification_type_id, "api.announcements")
        self.assertTrue(sub.active)
        self.assertEqual(stats["announcements_enabled"], 1)
        self.assertEqual(stats["announcements_disabled"], 0)

    def test_new_user_gets_disabled_announcements_subscription_when_unsubscribed(self):
        user = _make_auth_user("uid-unsub", email="unsub@example.com")
        session = _make_db_session()

        stats = self._run(
            [user],
            {},
            session,
            brevo_status=BrevoSubscriptionStatus.UNSUBSCRIBED,
            dry_run=False,
        )

        sub = _added_subscription(session)
        self.assertIsNotNone(sub)
        self.assertFalse(sub.active)
        self.assertEqual(stats["announcements_enabled"], 0)
        self.assertEqual(stats["announcements_disabled"], 1)

    def test_new_user_not_found_gets_enabled_announcements_subscription(self):
        user = _make_auth_user("uid-nf", email="nf@example.com")
        session = _make_db_session()

        stats = self._run(
            [user],
            {},
            session,
            brevo_status=BrevoSubscriptionStatus.NOT_FOUND,
            dry_run=False,
        )

        sub = _added_subscription(session)
        self.assertTrue(sub.active)
        self.assertEqual(stats["announcements_enabled"], 1)

    # --- Existing, already-synced users are skipped ---

    def test_existing_synced_user_skipped_no_db_write_no_brevo(self):
        """Existing user that already has a subscription and brevo_synced_at set
        → skipped entirely: no DB write, no Brevo call."""
        user = _make_auth_user("uid5")
        existing = _make_app_user(
            "uid5", email="e@example.com", brevo_synced_at=datetime.now(timezone.utc)
        )
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

    # --- Announcements subscription backfill for existing users ---

    def test_existing_user_without_sub_is_backfilled_enabled(self):
        """Existing user lacking an announcements subscription → one is created
        (enabled), without modifying the app_user row."""
        user = _make_auth_user("uid-bf", email="bf@example.com")
        existing = AppUser(
            id="uid-bf", email="bf@example.com", migrated_at=datetime.now(timezone.utc)
        )
        session = _make_db_session(existing, has_announcements_sub=False)

        stats = self._run(
            [user],
            {},
            session,
            brevo_status=BrevoSubscriptionStatus.SUBSCRIBED,
            dry_run=False,
            only_not_migrated=False,
        )

        self.assertIsNone(_added_app_user(session))  # existing row untouched
        sub = _added_subscription(session)
        self.assertIsNotNone(sub)
        self.assertEqual(sub.user_id, "uid-bf")
        self.assertEqual(sub.notification_type_id, "api.announcements")
        self.assertTrue(sub.active)
        self.assertEqual(stats["inserted"], 0)
        self.assertEqual(stats["announcements_enabled"], 1)

    def test_already_migrated_user_without_sub_backfilled_and_counted_skipped(self):
        """only_not_migrated=True: an already-migrated user is counted as skipped
        for the row migration but still gets the announcements subscription."""
        user = _make_auth_user("uid-bf2", email="bf2@example.com")
        existing = AppUser(
            id="uid-bf2",
            email="bf2@example.com",
            migrated_at=datetime.now(timezone.utc),
        )
        session = _make_db_session(existing, has_announcements_sub=False)

        stats = self._run(
            [user],
            {},
            session,
            brevo_status=BrevoSubscriptionStatus.UNSUBSCRIBED,
            dry_run=False,
            only_not_migrated=True,
        )

        sub = _added_subscription(session)
        self.assertIsNotNone(sub)
        self.assertFalse(sub.active)
        self.assertIsNone(_added_app_user(session))
        self.assertEqual(stats["skipped"], 1)
        self.assertEqual(stats["inserted"], 0)
        self.assertEqual(stats["announcements_disabled"], 1)

    def test_existing_synced_user_with_sub_no_backfill_no_brevo(self):
        """Existing user that already has the subscription and is brevo-synced →
        no-op (no Brevo call, no subscription created)."""
        user = _make_auth_user("uid-has", email="has@example.com")
        existing = _make_app_user(
            "uid-has",
            email="has@example.com",
            brevo_synced_at=datetime.now(timezone.utc),
        )
        session = _make_db_session(existing, has_announcements_sub=True)

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
            stats = migrate_firebase_users(
                db_session=session, dry_run=False, only_not_migrated=False
            )

        mock_brevo.assert_not_called()
        self.assertIsNone(_added_subscription(session))
        self.assertEqual(stats["announcements_enabled"], 0)
        self.assertEqual(stats["announcements_disabled"], 0)

    # --- Brevo contact write-back (MDB_SUBSCRIPTION_ID / brevo_synced_at) ---

    def _run_writeback(
        self,
        user_records,
        db_session,
        brevo_status,
        list_id="42",
        dry_run=False,
        add_side_effect=None,
        **kwargs,
    ):
        """Run the task with add_contact_to_list patched and the Brevo list id set.

        Returns (stats, mock_add_contact_to_list).
        """
        ds_client = _make_ds_client({})
        env = {"BREVO_API_ANNOUNCEMENTS_LIST_ID": list_id} if list_id else {}
        with (
            patch("tasks.users.migrate_firebase_users._get_firebase_app"),
            patch("tasks.users.migrate_firebase_users.datastore") as mock_datastore,
            patch(
                "tasks.users.migrate_firebase_users._iter_users",
                return_value=iter(user_records),
            ),
            patch(BREVO_MODULE, return_value=brevo_status),
            patch(
                "tasks.users.migrate_firebase_users.add_contact_to_list",
                side_effect=add_side_effect,
            ) as mock_add,
            patch.dict(os.environ, env, clear=False),
        ):
            mock_datastore.Client.return_value = ds_client
            stats = migrate_firebase_users(
                db_session=db_session, dry_run=dry_run, **kwargs
            )
        return stats, mock_add

    def test_new_subscribed_user_written_back_and_stamped(self):
        """New subscribed user → subscription created, MDB_SUBSCRIPTION_ID written
        once with the new subscription id, app_user.brevo_synced_at stamped."""
        user = _make_auth_user("uid-wb1", email="wb1@example.com")
        session = _make_db_session()

        stats, mock_add = self._run_writeback(
            [user], session, BrevoSubscriptionStatus.SUBSCRIBED
        )

        sub = _added_subscription(session)
        self.assertIsNotNone(sub)
        # New user has no Datastore profile here, so name/org are forwarded as None.
        mock_add.assert_called_once_with(
            "wb1@example.com", 42, sub.id, first_name=None, organization=None
        )
        added_user = _added_app_user(session)
        self.assertIsNotNone(added_user.brevo_synced_at)
        self.assertEqual(stats["brevo_synced"], 1)
        self.assertEqual(stats["brevo_sync_failed"], 0)

    def test_existing_unsynced_user_written_back_without_new_row(self):
        """Existing user with brevo_synced_at=None → no new subscription row,
        contact written back with the existing subscription id, and the existing
        app_user row stamped in place."""
        user = _make_auth_user("uid-wb2", email="wb2@example.com")
        existing = _make_app_user(
            "uid-wb2",
            email="wb2@example.com",
            brevo_synced_at=None,
            full_name="Jane Doe",
            legacy_org_name="Acme Transit",
        )
        sub = _make_subscription("uid-wb2", sub_id="sub-wb2")
        session = _make_db_session(existing, existing_sub=sub)

        stats, mock_add = self._run_writeback(
            [user],
            session,
            BrevoSubscriptionStatus.SUBSCRIBED,
            only_not_migrated=False,
        )

        self.assertIsNone(_added_subscription(session))  # no new subscription row
        self.assertIsNone(_added_app_user(session))  # existing row not re-inserted
        # Full name → FIRSTNAME, legacy org → ORGANIZATION are forwarded to Brevo.
        mock_add.assert_called_once_with(
            "wb2@example.com",
            42,
            "sub-wb2",
            first_name="Jane Doe",
            organization="Acme Transit",
        )
        self.assertIsNotNone(existing.brevo_synced_at)  # stamped in place
        self.assertEqual(stats["brevo_synced"], 1)

    def test_already_synced_user_is_skipped(self):
        """Existing user already synced (app_user.brevo_synced_at set) with a
        subscription → skipped entirely: no write-back, no new subscription row."""
        user = _make_auth_user("uid-wb3", email="wb3@example.com")
        existing = _make_app_user(
            "uid-wb3",
            email="wb3@example.com",
            brevo_synced_at=datetime.now(timezone.utc),
        )
        session = _make_db_session(existing, has_announcements_sub=True)

        stats, mock_add = self._run_writeback(
            [user],
            session,
            BrevoSubscriptionStatus.SUBSCRIBED,
            only_not_migrated=False,
        )

        mock_add.assert_not_called()
        self.assertIsNone(_added_subscription(session))
        self.assertEqual(stats["brevo_synced"], 0)

    def test_unsubscribed_existing_user_not_written_back(self):
        """Existing unsynced user whose contact is UNSUBSCRIBED on Brevo → never
        re-added to the list; app_user.brevo_synced_at stays None."""
        user = _make_auth_user("uid-wb4", email="wb4@example.com")
        existing = _make_app_user(
            "uid-wb4", email="wb4@example.com", brevo_synced_at=None
        )
        sub = _make_subscription("uid-wb4", sub_id="sub-wb4")
        session = _make_db_session(existing, existing_sub=sub)

        stats, mock_add = self._run_writeback(
            [user],
            session,
            BrevoSubscriptionStatus.UNSUBSCRIBED,
            only_not_migrated=False,
        )

        mock_add.assert_not_called()
        self.assertIsNone(existing.brevo_synced_at)
        self.assertEqual(stats["brevo_synced"], 0)

    def test_writeback_failure_is_counted_and_not_stamped(self):
        """add_contact_to_list raising → counted as brevo_sync_failed,
        app_user.brevo_synced_at left None (retried next run), task does not abort."""
        user = _make_auth_user("uid-wb5", email="wb5@example.com")
        existing = _make_app_user(
            "uid-wb5", email="wb5@example.com", brevo_synced_at=None
        )
        sub = _make_subscription("uid-wb5", sub_id="sub-wb5")
        session = _make_db_session(existing, existing_sub=sub)

        stats, mock_add = self._run_writeback(
            [user],
            session,
            BrevoSubscriptionStatus.SUBSCRIBED,
            add_side_effect=Exception("Brevo down"),
            only_not_migrated=False,
        )

        mock_add.assert_called_once()
        self.assertIsNone(existing.brevo_synced_at)
        self.assertEqual(stats["brevo_synced"], 0)
        self.assertEqual(stats["brevo_sync_failed"], 1)

    def test_dry_run_does_not_write_back_but_counts(self):
        """dry_run=True → no add_contact_to_list call and no stamping, but the
        would-be sync is counted."""
        user = _make_auth_user("uid-wb6", email="wb6@example.com")
        session = _make_db_session()

        stats, mock_add = self._run_writeback(
            [user], session, BrevoSubscriptionStatus.SUBSCRIBED, dry_run=True
        )

        mock_add.assert_not_called()
        session.add.assert_not_called()
        self.assertEqual(stats["brevo_synced"], 1)

    def test_missing_list_id_skips_write_back(self):
        """No BREVO_API_ANNOUNCEMENTS_LIST_ID configured → write-back skipped,
        subscription still created."""
        user = _make_auth_user("uid-wb7", email="wb7@example.com")
        session = _make_db_session()

        stats, mock_add = self._run_writeback(
            [user], session, BrevoSubscriptionStatus.SUBSCRIBED, list_id=None
        )

        mock_add.assert_not_called()
        self.assertEqual(stats["brevo_synced"], 0)
        self.assertIsNotNone(_added_subscription(session))

    def test_write_back_is_idempotent_across_runs(self):
        """Second run over an already-synced user is a no-op: the write happens
        once, then app_user.brevo_synced_at short-circuits subsequent runs."""
        user = _make_auth_user("uid-wb8", email="wb8@example.com")
        existing = _make_app_user(
            "uid-wb8", email="wb8@example.com", brevo_synced_at=None
        )
        sub = _make_subscription("uid-wb8", sub_id="sub-wb8")
        session = _make_db_session(existing, existing_sub=sub)

        ds_client = _make_ds_client({})
        with (
            patch("tasks.users.migrate_firebase_users._get_firebase_app"),
            patch("tasks.users.migrate_firebase_users.datastore") as mock_datastore,
            patch(
                "tasks.users.migrate_firebase_users._iter_users",
                side_effect=lambda user_ids: iter([user]),
            ),
            patch(BREVO_MODULE, return_value=BrevoSubscriptionStatus.SUBSCRIBED),
            patch("tasks.users.migrate_firebase_users.add_contact_to_list") as mock_add,
            patch.dict(
                os.environ, {"BREVO_API_ANNOUNCEMENTS_LIST_ID": "42"}, clear=False
            ),
        ):
            mock_datastore.Client.return_value = ds_client
            stats1 = migrate_firebase_users(
                db_session=session, dry_run=False, only_not_migrated=False
            )
            stats2 = migrate_firebase_users(
                db_session=session, dry_run=False, only_not_migrated=False
            )

        self.assertEqual(mock_add.call_count, 1)
        self.assertEqual(stats1["brevo_synced"], 1)
        self.assertEqual(stats2["brevo_synced"], 0)

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
        added: AppUser = _added_app_user(session)
        self.assertIsNone(added.is_registered_to_receive_api_announcements)
        # Failed Brevo check is treated as "not unsubscribed" → subscription enabled.
        sub = _added_subscription(session)
        self.assertTrue(sub.active)
        self.assertEqual(stats["announcements_enabled"], 1)

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
