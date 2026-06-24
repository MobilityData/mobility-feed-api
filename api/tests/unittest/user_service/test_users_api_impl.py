import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from middleware.request_context import _request_context
from shared.db_models.app_user_impl import AppUserImpl
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    FeatureFlag,
    UserFeatureFlag,
)
import user_service.impl.subscription_helpers as helpers
from user_service.impl.users_api_impl import UsersApiImpl
from user_service_gen.models.create_notification_subscription_request import CreateNotificationSubscriptionRequest
from user_service_gen.models.update_notification_subscription_request import UpdateNotificationSubscriptionRequest

FIXED_NOW = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def _make_user(**kwargs) -> AppUser:
    defaults = dict(
        id="uid-123",
        email="user@example.com",
        full_name="Jane Doe",
        is_registered_to_receive_api_announcements=False,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    defaults.update(kwargs)
    user = AppUser(**{k: v for k, v in defaults.items() if k != "feature_flags"})
    user.user_feature_flags = defaults.get("feature_flags", [])
    return user


def _mock_query_first(session, return_value, flags=None):
    """Dispatch session.query per model.

    AppUser query → .options().filter_by().first() returns `return_value`.
    FeatureFlag query → .order_by().all() returns `flags` (default []).
    """
    flags = flags if flags is not None else []
    user_q = MagicMock()
    user_q.options.return_value = user_q
    user_q.filter_by.return_value = user_q
    user_q.first.return_value = return_value

    flags_q = MagicMock()
    flags_q.filter.return_value = flags_q
    flags_q.order_by.return_value = flags_q
    flags_q.all.return_value = flags

    session.query.side_effect = lambda model: (flags_q if model is FeatureFlag else user_q)
    return user_q


def _set_context(user_id="uid-123", user_email="user@example.com", is_guest=False):
    _request_context.set({"user_id": user_id, "user_email": user_email, "is_guest": is_guest})


class TestGetUserMe(unittest.TestCase):
    def setUp(self):
        self.api = UsersApiImpl()
        self.mock_session = MagicMock()

    def test_returns_existing_user(self):
        user = _make_user()
        _mock_query_first(self.mock_session, user)
        _set_context()

        result = self.api.get_user(db_session=self.mock_session)

        self.mock_session.add.assert_not_called()
        self.assertEqual(result.id, "uid-123")
        self.assertEqual(result.email, "user@example.com")
        self.assertEqual(result.full_name, "Jane Doe")
        self.assertFalse(result.is_registered_to_receive_api_announcements)

    def test_upserts_new_user_on_first_call(self):
        _mock_query_first(self.mock_session, None)
        _set_context()

        result = self.api.get_user(db_session=self.mock_session)

        self.mock_session.add.assert_called_once()
        self.mock_session.flush.assert_called_once()
        added_user: AppUser = self.mock_session.add.call_args[0][0]
        self.assertEqual(added_user.id, "uid-123")
        self.assertEqual(added_user.email, "user@example.com")
        self.assertEqual(result.id, "uid-123")

    def test_raises_401_when_user_id_missing(self):
        _request_context.set({"user_id": None, "user_email": "user@example.com"})

        with self.assertRaises(HTTPException) as ctx:
            self.api.get_user(db_session=self.mock_session)

        self.assertEqual(ctx.exception.status_code, 401)

    def test_raises_401_when_context_empty(self):
        _request_context.set({})

        with self.assertRaises(HTTPException) as ctx:
            self.api.get_user(db_session=self.mock_session)

        self.assertEqual(ctx.exception.status_code, 401)

    def test_guest(self):
        _set_context(is_guest=True, user_id="uid-123")

        result = self.api.get_user(db_session=self.mock_session)

        self.mock_session.get.assert_not_called()
        self.mock_session.add.assert_not_called()
        self.assertEqual(result.id, "uid-123")

    def test_returns_active_flags_with_resolved_values(self):
        flag = FeatureFlag(
            id="beta_editor",
            name="Beta Editor",
            value_type="boolean",
            default_value=False,
            disabled=False,
            created_at=FIXED_NOW,
        )
        user = _make_user()
        _mock_query_first(self.mock_session, user, flags=[flag])
        _set_context()

        result = self.api.get_user(db_session=self.mock_session)

        self.assertEqual([f.id for f in result.features], ["beta_editor"])
        self.assertEqual(result.features[0].value, False)

    def test_disabled_flags_filtered_out_of_query(self):
        user = _make_user()
        _mock_query_first(self.mock_session, user, flags=[])
        _set_context()

        self.api.get_user(db_session=self.mock_session)

        # The user-facing query must exclude disabled flags.
        flags_q = self.mock_session.query(FeatureFlag)
        flags_q.filter.assert_called()


class TestUpdateUserMe(unittest.TestCase):
    def setUp(self):
        self.api = UsersApiImpl()
        self.mock_session = MagicMock()

    def _make_request(self, **kwargs):
        from user_service_gen.models.update_user_request import UpdateUserRequest

        return UpdateUserRequest(**kwargs)

    def test_updates_full_name(self):
        user = _make_user(full_name="Old Name")
        _mock_query_first(self.mock_session, user)
        _set_context()

        req = self._make_request(full_name="New Name")
        result = self.api.update_user(req, db_session=self.mock_session)

        self.assertEqual(user.full_name, "New Name")
        self.mock_session.flush.assert_called_once()
        self.assertEqual(result.full_name, "New Name")

    def test_updates_api_announcements_flag(self):
        user = _make_user(is_registered_to_receive_api_announcements=False)
        _mock_query_first(self.mock_session, user)
        _set_context()

        req = self._make_request(is_registered_to_receive_api_announcements=True)
        result = self.api.update_user(req, db_session=self.mock_session)

        self.assertTrue(user.is_registered_to_receive_api_announcements)
        self.assertTrue(result.is_registered_to_receive_api_announcements)

    def test_partial_update_leaves_other_fields_unchanged(self):
        user = _make_user(full_name="Unchanged", is_registered_to_receive_api_announcements=True)
        _mock_query_first(self.mock_session, user)
        _set_context()

        req = self._make_request(full_name="Updated")
        self.api.update_user(req, db_session=self.mock_session)

        self.assertTrue(user.is_registered_to_receive_api_announcements)

    def test_raises_404_when_user_not_found(self):
        _mock_query_first(self.mock_session, None)
        _set_context()

        req = self._make_request(full_name="Ghost")
        with self.assertRaises(HTTPException) as ctx:
            self.api.update_user(req, db_session=self.mock_session)

        self.assertEqual(ctx.exception.status_code, 404)

    def test_raises_401_when_user_id_missing(self):
        _request_context.set({"user_id": None, "user_email": "x@x.com"})

        req = self._make_request(full_name="X")
        with self.assertRaises(HTTPException) as ctx:
            self.api.update_user(req, db_session=self.mock_session)

        self.assertEqual(ctx.exception.status_code, 401)

    def test_guest_raises_403_on_update(self):
        _set_context(is_guest=True)

        req = self._make_request(full_name="Guest")
        with self.assertRaises(HTTPException) as ctx:
            self.api.update_user(req, db_session=self.mock_session)

        self.assertEqual(ctx.exception.status_code, 403)
        self.mock_session.query.assert_not_called()


class TestSubscriptions(unittest.TestCase):
    def setUp(self):
        self.api = UsersApiImpl()
        self.mock_session = MagicMock()
        _set_context()

    def _make_sub(self, **kwargs):
        from shared.users_database_gen.sqlacodegen_models import NotificationSubscription as Orm

        defaults = dict(
            id="sub-1",
            user_id="uid-123",
            notification_type_id="feed.published",
            active=True,
            created_at=FIXED_NOW,
            last_notified_at=None,
        )
        defaults.update(kwargs)
        return Orm(**defaults)

    # ── list ──
    def test_get_user_subscriptions_returns_user_subs(self):
        sub = self._make_sub()
        query = self.mock_session.query.return_value
        query.filter.return_value.order_by.return_value.all.return_value = [sub]

        result = self.api.get_user_subscriptions(db_session=self.mock_session)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "sub-1")
        self.assertEqual(result[0].notification_id, "feed.published")

    def test_get_user_subscriptions_guest_403(self):
        _set_context(is_guest=True)
        with self.assertRaises(HTTPException) as ctx:
            self.api.get_user_subscriptions(db_session=self.mock_session)
        self.assertEqual(ctx.exception.status_code, 403)

    # ── create ──
    def test_create_unknown_type_400(self):
        self.mock_session.get.return_value = None  # NotificationType lookup
        with self.assertRaises(HTTPException) as ctx:
            self.api.create_user_subscription(
                CreateNotificationSubscriptionRequest(notification_id="nope"), db_session=self.mock_session
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_create_non_announcement_no_brevo(self):
        from shared.users_database_gen.sqlacodegen_models import NotificationType

        self.mock_session.get.side_effect = lambda model, key: (
            NotificationType(id="feed.published") if model is NotificationType else _make_user()
        )
        self.mock_session.query.return_value.filter.return_value.one_or_none.return_value = None

        with patch.object(helpers, "add_contact_to_list") as add:
            result = self.api.create_user_subscription(
                CreateNotificationSubscriptionRequest(notification_id="feed.published"), db_session=self.mock_session
            )

        add.assert_not_called()
        self.mock_session.add.assert_called_once()
        self.assertTrue(result.active)
        self.assertEqual(result.notification_id, "feed.published")

    def test_create_announcement_syncs_brevo(self):
        from shared.users_database_gen.sqlacodegen_models import NotificationType

        self.mock_session.get.side_effect = lambda model, key: (
            NotificationType(id="api.announcements") if model is NotificationType else _make_user()
        )
        self.mock_session.query.return_value.filter.return_value.one_or_none.return_value = None

        with patch.object(helpers, "add_contact_to_list") as add, patch.object(
            helpers, "get_announcements_list_id", return_value=42
        ):
            result = self.api.create_user_subscription(
                CreateNotificationSubscriptionRequest(notification_id="api.announcements"), db_session=self.mock_session
            )

        add.assert_called_once()
        self.assertEqual(add.call_args[0][0], "user@example.com")
        self.assertEqual(add.call_args[0][1], 42)
        self.assertEqual(result.notification_id, "api.announcements")

    def test_create_idempotent_reactivates_existing(self):
        from shared.users_database_gen.sqlacodegen_models import NotificationType

        existing = self._make_sub(notification_type_id="feed.published", active=False)
        self.mock_session.get.side_effect = lambda model, key: (
            NotificationType(id="feed.published") if model is NotificationType else _make_user()
        )
        self.mock_session.query.return_value.filter.return_value.one_or_none.return_value = existing

        result = self.api.create_user_subscription(
            CreateNotificationSubscriptionRequest(notification_id="feed.published"), db_session=self.mock_session
        )

        self.assertTrue(existing.active)
        self.mock_session.add.assert_not_called()
        self.assertEqual(result.id, "sub-1")

    # ── update ──
    def test_update_deactivate_announcement_removes_brevo(self):
        sub = self._make_sub(notification_type_id="api.announcements", active=True)
        self.mock_session.get.side_effect = lambda model, key: (
            sub if "Subscription" in model.__name__ else _make_user()
        )

        with patch.object(helpers, "remove_contact_from_list") as rem, patch.object(
            helpers, "get_announcements_list_id", return_value=42
        ):
            result = self.api.update_user_subscription(
                "sub-1", UpdateNotificationSubscriptionRequest(active=False), db_session=self.mock_session
            )

        rem.assert_called_once_with("user@example.com", 42)
        self.assertFalse(result.active)

    def test_update_not_owned_404(self):
        other = self._make_sub(user_id="someone-else")
        self.mock_session.get.return_value = other
        with self.assertRaises(HTTPException) as ctx:
            self.api.update_user_subscription(
                "sub-1", UpdateNotificationSubscriptionRequest(active=False), db_session=self.mock_session
            )
        self.assertEqual(ctx.exception.status_code, 404)

    # ── delete ──
    def test_delete_announcement_disables_instead_of_delete(self):
        sub = self._make_sub(notification_type_id="api.announcements")
        self.mock_session.get.side_effect = lambda model, key: (
            sub if "Subscription" in model.__name__ else _make_user()
        )

        with patch.object(helpers, "remove_contact_from_list") as rem, patch.object(
            helpers, "get_announcements_list_id", return_value=42
        ):
            self.api.delete_user_subscription("sub-1", db_session=self.mock_session)

        rem.assert_called_once_with("user@example.com", 42)
        self.mock_session.delete.assert_not_called()
        self.assertFalse(sub.active)

    def test_delete_announcement_brevo_connection_error_502(self):
        import urllib3

        sub = self._make_sub(notification_type_id="api.announcements")
        self.mock_session.get.side_effect = lambda model, key: (
            sub if "Subscription" in model.__name__ else _make_user()
        )

        with patch.object(
            helpers,
            "remove_contact_from_list",
            side_effect=urllib3.exceptions.MaxRetryError(None, "url", reason="unreachable"),
        ), patch.object(helpers, "get_announcements_list_id", return_value=42):
            with self.assertRaises(HTTPException) as ctx:
                self.api.delete_user_subscription("sub-1", db_session=self.mock_session)

        self.assertEqual(ctx.exception.status_code, 502)
        self.mock_session.delete.assert_not_called()
        self.assertTrue(sub.active)

    def test_delete_non_announcement_no_brevo(self):
        sub = self._make_sub(notification_type_id="feed.published")
        self.mock_session.get.return_value = sub

        with patch.object(helpers, "remove_contact_from_list") as rem:
            self.api.delete_user_subscription("sub-1", db_session=self.mock_session)

        rem.assert_not_called()
        # ORM delete is used; passive_deletes lets the DB ON DELETE CASCADE remove notification_log rows.
        self.mock_session.delete.assert_called_once_with(sub)

    def test_delete_not_found_404(self):
        self.mock_session.get.return_value = None
        with self.assertRaises(HTTPException) as ctx:
            self.api.delete_user_subscription("missing", db_session=self.mock_session)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_brevo_failure_raises_502(self):
        import sib_api_v3_sdk
        from shared.users_database_gen.sqlacodegen_models import NotificationType

        self.mock_session.get.side_effect = lambda model, key: (
            NotificationType(id="api.announcements") if model is NotificationType else _make_user()
        )
        self.mock_session.query.return_value.filter.return_value.one_or_none.return_value = None

        with patch.object(
            helpers, "add_contact_to_list", side_effect=sib_api_v3_sdk.rest.ApiException(status=500)
        ), patch.object(helpers, "get_announcements_list_id", return_value=42):
            with self.assertRaises(HTTPException) as ctx:
                self.api.create_user_subscription(
                    CreateNotificationSubscriptionRequest(notification_id="api.announcements"),
                    db_session=self.mock_session,
                )
        self.assertEqual(ctx.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()


class TestAppUserImpl(unittest.TestCase):
    def test_from_orm_none_returns_none(self):
        self.assertIsNone(AppUserImpl.from_orm(None))

    def test_from_orm_maps_all_fields(self):
        now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        user = AppUser(
            id="uid-1",
            email="a@b.com",
            full_name="Alice",
            legacy_org_name="Acme Transit",
            email_verified=True,
            is_registered_to_receive_api_announcements=True,
            created_at=now,
            updated_at=now,
        )
        profile = AppUserImpl.from_orm(user)
        self.assertEqual(profile.id, "uid-1")
        self.assertEqual(profile.email, "a@b.com")
        self.assertEqual(profile.full_name, "Alice")
        self.assertEqual(profile.legacy_org_name, "Acme Transit")
        self.assertTrue(profile.email_verified)
        self.assertTrue(profile.is_registered_to_receive_api_announcements)
        self.assertEqual(profile.created_at, now)
        self.assertEqual(profile.updated_at, now)

    def test_from_orm_resolves_user_override_and_default(self):
        now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        flag = FeatureFlag(
            id="beta_editor",
            name="Beta Editor",
            description="Enables the beta editor",
            value_type="boolean",
            default_value=False,
            created_at=now,
        )
        user_flag = UserFeatureFlag(user_id="uid-2", feature_flag_id=flag.id, value=True, assigned_at=now)
        user_flag.feature_flag = flag
        user = AppUser(id="uid-2", email="b@b.com", created_at=now, updated_at=now)
        user.user_feature_flags = [user_flag]

        profile = AppUserImpl.from_orm(user, [flag])

        self.assertEqual(len(profile.features), 1)
        self.assertEqual(profile.features[0].id, "beta_editor")
        self.assertEqual(profile.features[0].name, "Beta Editor")
        self.assertEqual(profile.features[0].value_type, "boolean")
        # User override (True) wins over the default (False)
        self.assertEqual(profile.features[0].value, True)

    def test_from_orm_returns_all_flags_with_defaults_when_user_has_none(self):
        now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        flag = FeatureFlag(
            id="beta_editor",
            name="Beta Editor",
            value_type="boolean",
            default_value=False,
            created_at=now,
        )
        user = AppUser(id="uid-3", email="c@b.com", created_at=now, updated_at=now)
        user.user_feature_flags = []

        profile = AppUserImpl.from_orm(user, [flag])

        # Flag is returned even though the user has no override; value is the default
        self.assertEqual(len(profile.features), 1)
        self.assertEqual(profile.features[0].id, "beta_editor")
        self.assertEqual(profile.features[0].value, False)

    def test_from_orm_empty_when_no_flags_exist(self):
        now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        user = AppUser(id="uid-4", email="d@b.com", created_at=now, updated_at=now)
        user.user_feature_flags = []

        profile = AppUserImpl.from_orm(user, [])

        self.assertEqual(profile.features, [])
