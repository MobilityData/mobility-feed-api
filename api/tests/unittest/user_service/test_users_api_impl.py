import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi import HTTPException

from middleware.request_context import _request_context
from shared.db_models.app_user_impl import AppUserImpl
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    FeatureFlag,
    UserFeatureFlag,
)
from user_service.impl.users_api_impl import UsersApiImpl

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


def _mock_query_first(session, return_value):
    """Make session.query().options().filter_by().first() return return_value."""
    mock_q = MagicMock()
    mock_q.options.return_value = mock_q
    mock_q.filter_by.return_value = mock_q
    mock_q.first.return_value = return_value
    session.query.return_value = mock_q
    return mock_q


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


if __name__ == "__main__":
    unittest.main()


class TestSubscriptionStubs(unittest.TestCase):
    def setUp(self):
        self.api = UsersApiImpl()
        _set_context()

    def test_get_user_subscriptions_returns_501(self):
        with self.assertRaises(HTTPException) as ctx:
            self.api.get_user_subscriptions()
        self.assertEqual(ctx.exception.status_code, 501)

    def test_create_user_subscription_returns_501(self):
        from user_service_gen.models.create_notification_subscription_request import (
            CreateNotificationSubscriptionRequest,
        )

        with self.assertRaises(HTTPException) as ctx:
            self.api.create_user_subscription(CreateNotificationSubscriptionRequest(notification_id="type-1"))
        self.assertEqual(ctx.exception.status_code, 501)

    def test_update_user_subscription_returns_501(self):
        from user_service_gen.models.update_notification_subscription_request import (
            UpdateNotificationSubscriptionRequest,
        )

        with self.assertRaises(HTTPException) as ctx:
            self.api.update_user_subscription("sub-id", UpdateNotificationSubscriptionRequest(active=True))
        self.assertEqual(ctx.exception.status_code, 501)

    def test_delete_user_subscription_returns_501(self):
        with self.assertRaises(HTTPException) as ctx:
            self.api.delete_user_subscription("sub-id")
        self.assertEqual(ctx.exception.status_code, 501)


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

    def test_from_orm_includes_feature_flags(self):
        now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        flag = FeatureFlag(
            id="beta_editor",
            name="Beta Editor",
            description="Enables the beta editor",
            value_type="boolean",
            default_value=False,
            created_at=now,
        )
        user_flag = UserFeatureFlag(user_id="uid-2", feature_flag_id=flag.id, assigned_at=now)
        user_flag.feature_flag = flag
        user = AppUser(id="uid-2", email="b@b.com", created_at=now, updated_at=now)
        user.user_feature_flags = [user_flag]

        profile = AppUserImpl.from_orm(user)

        self.assertEqual(len(profile.features), 1)
        self.assertEqual(profile.features[0].id, "beta_editor")
        self.assertEqual(profile.features[0].name, "Beta Editor")
        self.assertEqual(profile.features[0].value_type, "boolean")
        self.assertEqual(profile.features[0].value.actual_instance, False)

    def test_from_orm_empty_feature_flags(self):
        now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        user = AppUser(id="uid-3", email="c@b.com", created_at=now, updated_at=now)
        user.user_feature_flags = []

        profile = AppUserImpl.from_orm(user)

        self.assertEqual(profile.features, [])

    def test_from_orm_none_feature_flags_treated_as_empty(self):
        now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        user = AppUser(id="uid-4", email="d@b.com", created_at=now, updated_at=now)
        # Simulate a user where feature_flags hasn't been loaded (set to empty list as selectinload would return)
        user.user_feature_flags = []

        profile = AppUserImpl.from_orm(user)

        self.assertEqual(profile.features, [])
