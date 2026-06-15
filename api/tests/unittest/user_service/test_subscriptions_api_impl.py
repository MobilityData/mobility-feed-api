import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

import user_service.impl.subscription_helpers as helpers
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    NotificationSubscription as NotificationSubscriptionOrm,
)
from user_service.impl.subscriptions_api_impl import SubscriptionsApiImpl

FIXED_NOW = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def _make_sub(**kwargs):
    defaults = dict(
        id="sub-1",
        user_id="uid-123",
        notification_type_id="feed.published",
        active=True,
        created_at=FIXED_NOW,
        last_notified_at=None,
    )
    defaults.update(kwargs)
    return NotificationSubscriptionOrm(**defaults)


def _make_user(email="user@example.com"):
    return AppUser(id="uid-123", email=email, created_at=FIXED_NOW, updated_at=FIXED_NOW)


class TestPublicGetSubscription(unittest.TestCase):
    def setUp(self):
        self.api = SubscriptionsApiImpl()
        self.mock_session = MagicMock()

    def test_returns_subscription(self):
        self.mock_session.get.return_value = _make_sub(
            notification_type_id="api.announcements",
            active=False,
            last_notified_at=FIXED_NOW,
        )

        result = self.api.get_subscription("sub-1", db_session=self.mock_session)

        self.mock_session.get.assert_called_once_with(NotificationSubscriptionOrm, "sub-1")
        self.assertEqual(result.id, "sub-1")
        self.assertEqual(result.user_id, "uid-123")
        self.assertEqual(result.notification_id, "api.announcements")
        self.assertFalse(result.active)
        self.assertEqual(result.last_notified_at, FIXED_NOW)
        self.assertEqual(result.created_at, FIXED_NOW)

    def test_get_does_not_touch_brevo(self):
        self.mock_session.get.return_value = _make_sub(notification_type_id="api.announcements")

        with patch.object(helpers, "remove_contact_from_list") as rem, patch.object(
            helpers, "add_contact_to_list"
        ) as add:
            self.api.get_subscription("sub-1", db_session=self.mock_session)

        rem.assert_not_called()
        add.assert_not_called()

    def test_missing_returns_404(self):
        self.mock_session.get.return_value = None
        with self.assertRaises(HTTPException) as ctx:
            self.api.get_subscription("missing", db_session=self.mock_session)
        self.assertEqual(ctx.exception.status_code, 404)


class TestPublicDeleteSubscription(unittest.TestCase):
    def setUp(self):
        self.api = SubscriptionsApiImpl()
        self.mock_session = MagicMock()

    def test_delete_non_announcement_no_brevo(self):
        sub = _make_sub(notification_type_id="feed.published")
        self.mock_session.get.return_value = sub

        with patch.object(helpers, "remove_contact_from_list") as rem:
            self.api.delete_subscription("sub-1", db_session=self.mock_session)

        rem.assert_not_called()
        self.mock_session.delete.assert_called_once_with(sub)

    def test_delete_announcement_removes_brevo(self):
        sub = _make_sub(notification_type_id="api.announcements")
        self.mock_session.get.side_effect = lambda model, key: (
            sub if model is NotificationSubscriptionOrm else _make_user()
        )

        with patch.object(helpers, "remove_contact_from_list") as rem, patch.object(
            helpers, "get_announcements_list_id", return_value=42
        ):
            self.api.delete_subscription("sub-1", db_session=self.mock_session)

        rem.assert_called_once_with("user@example.com", 42)
        self.mock_session.delete.assert_called_once_with(sub)

    def test_delete_announcement_missing_user_skips_brevo(self):
        sub = _make_sub(notification_type_id="api.announcements")
        self.mock_session.get.side_effect = lambda model, key: (sub if model is NotificationSubscriptionOrm else None)

        with patch.object(helpers, "remove_contact_from_list") as rem:
            self.api.delete_subscription("sub-1", db_session=self.mock_session)

        rem.assert_not_called()
        self.mock_session.delete.assert_called_once_with(sub)

    def test_delete_missing_returns_404(self):
        self.mock_session.get.return_value = None
        with self.assertRaises(HTTPException) as ctx:
            self.api.delete_subscription("missing", db_session=self.mock_session)
        self.assertEqual(ctx.exception.status_code, 404)
        self.mock_session.delete.assert_not_called()

    def test_delete_announcement_brevo_failure_502(self):
        import sib_api_v3_sdk

        sub = _make_sub(notification_type_id="api.announcements")
        self.mock_session.get.side_effect = lambda model, key: (
            sub if model is NotificationSubscriptionOrm else _make_user()
        )

        with patch.object(
            helpers, "remove_contact_from_list", side_effect=sib_api_v3_sdk.rest.ApiException(status=500)
        ), patch.object(helpers, "get_announcements_list_id", return_value=42):
            with self.assertRaises(HTTPException) as ctx:
                self.api.delete_subscription("sub-1", db_session=self.mock_session)

        self.assertEqual(ctx.exception.status_code, 502)
        self.mock_session.delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
