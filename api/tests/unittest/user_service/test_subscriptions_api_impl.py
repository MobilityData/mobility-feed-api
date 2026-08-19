import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

import user_service.impl.subscription_helpers as helpers
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    NotificationSubscription as NotificationSubscriptionOrm,
    NotificationSubscriptionFeed as NotificationSubscriptionFeedOrm,
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
        )

        result = self.api.get_subscription("sub-1", db_session=self.mock_session)

        self.mock_session.get.assert_called_once_with(NotificationSubscriptionOrm, "sub-1")
        self.assertEqual(result.id, "sub-1")
        self.assertEqual(result.user_id, "uid-123")
        self.assertEqual(result.notification_id, "api.announcements")
        self.assertFalse(result.active)
        self.assertEqual(result.created_at, FIXED_NOW)

    def test_get_does_not_touch_brevo(self):
        self.mock_session.get.return_value = _make_sub(notification_type_id="api.announcements")

        with patch.object(helpers, "remove_contact_from_list") as rem, patch.object(
            helpers, "add_contact_to_list"
        ) as add:
            self.api.get_subscription("sub-1", db_session=self.mock_session)

        rem.assert_not_called()
        add.assert_not_called()

    def test_returns_feed_ids_for_feed_scoped_subscription(self):
        sub = _make_sub(notification_type_id="feed.url_updated")
        sub.notification_subscription_feeds.append(NotificationSubscriptionFeedOrm(feed_stable_id="mdb-9"))
        sub.notification_subscription_feeds.append(NotificationSubscriptionFeedOrm(feed_stable_id="mdb-2"))
        self.mock_session.get.return_value = sub

        metadata = {"mdb-9": {"data_type": "gtfs", "provider": "P9", "feed_name": "F9"}}
        with patch("user_service.impl.subscriptions_api_impl.resolve_feed_metadata", return_value=metadata):
            result = self.api.get_subscription("sub-1", db_session=self.mock_session)

        # feeds come from the join table, sorted by id.
        self.assertEqual([f.feed_id for f in result.feeds], ["mdb-2", "mdb-9"])
        # feeds carries resolved metadata per feed (null where unresolved).
        by_id = {f.feed_id: f for f in result.feeds}
        self.assertEqual(by_id["mdb-9"].data_type, "gtfs")
        self.assertEqual(by_id["mdb-9"].provider, "P9")
        self.assertIsNone(by_id["mdb-2"].data_type)

    def test_missing_returns_404(self):
        self.mock_session.get.return_value = None
        with self.assertRaises(HTTPException) as ctx:
            self.api.get_subscription("missing", db_session=self.mock_session)
        self.assertEqual(ctx.exception.status_code, 404)


class TestPublicDeleteSubscription(unittest.TestCase):
    def setUp(self):
        self.api = SubscriptionsApiImpl()
        self.mock_session = MagicMock()
        # Delete is gated by the owner's isNotificationsEnabled flag; enable it for these tests.
        gate_patcher = patch("user_service.impl.subscriptions_api_impl.feature_flag_enabled", return_value=True)
        gate_patcher.start()
        self.addCleanup(gate_patcher.stop)

    def test_delete_denied_when_flag_off(self):
        sub = _make_sub(notification_type_id="feed.published")
        self.mock_session.get.return_value = sub

        with patch("user_service.impl.subscriptions_api_impl.feature_flag_enabled", return_value=False):
            with self.assertRaises(HTTPException) as ctx:
                self.api.delete_subscription("sub-1", db_session=self.mock_session)

        self.assertEqual(ctx.exception.status_code, 403)
        self.mock_session.delete.assert_not_called()

    def test_delete_non_announcement_no_brevo(self):
        sub = _make_sub(notification_type_id="feed.published")
        self.mock_session.get.return_value = sub

        with patch.object(helpers, "remove_contact_from_list") as rem:
            self.api.delete_subscription("sub-1", db_session=self.mock_session)

        rem.assert_not_called()
        # ORM delete is used; passive_deletes lets the DB ON DELETE CASCADE remove notification_log rows.
        self.mock_session.delete.assert_called_once_with(sub)

    def test_delete_announcement_disables_instead_of_delete(self):
        sub = _make_sub(notification_type_id="api.announcements")
        self.mock_session.get.side_effect = lambda model, key: (
            sub if model is NotificationSubscriptionOrm else _make_user()
        )

        with patch.object(helpers, "remove_contact_from_list") as rem, patch.object(
            helpers, "get_announcements_list_id", return_value=42
        ):
            self.api.delete_subscription("sub-1", db_session=self.mock_session)

        rem.assert_called_once_with("user@example.com", 42)
        self.mock_session.delete.assert_not_called()
        self.assertFalse(sub.active)
        sub = _make_sub(notification_type_id="api.announcements")
        self.mock_session.get.side_effect = lambda model, key: (sub if model is NotificationSubscriptionOrm else None)

        with patch.object(helpers, "remove_contact_from_list") as rem:
            self.api.delete_subscription("sub-1", db_session=self.mock_session)

        rem.assert_not_called()
        self.mock_session.delete.assert_not_called()
        self.assertFalse(sub.active)

    def test_delete_missing_returns_404(self):
        self.mock_session.get.return_value = None
        with self.assertRaises(HTTPException) as ctx:
            self.api.delete_subscription("missing", db_session=self.mock_session)
        self.assertEqual(ctx.exception.status_code, 404)
        self.mock_session.delete.assert_not_called()

    def test_delete_invalid_scope_returns_400(self):
        with self.assertRaises(HTTPException) as ctx:
            self.api.delete_subscription("sub-1", scope="All", db_session=self.mock_session)
        self.assertEqual(ctx.exception.status_code, 400)
        # Rejected before any lookup: a malformed scope must not fall back to 'one' silently.
        self.mock_session.get.assert_not_called()
        self.mock_session.delete.assert_not_called()

    def test_delete_invalid_scope_takes_precedence_over_missing_id(self):
        self.mock_session.get.return_value = None
        with self.assertRaises(HTTPException) as ctx:
            self.api.delete_subscription("missing", scope="everything", db_session=self.mock_session)
        self.assertEqual(ctx.exception.status_code, 400)
        self.mock_session.get.assert_not_called()

    def _wire_scope_all(self, subs, user):
        """Point the initial get() at the first sub, AppUser lookups at ``user``, and the
        'all subscriptions for this user' query at ``subs``."""

        def _get(model, key):
            return subs[0] if model is NotificationSubscriptionOrm else user

        self.mock_session.get.side_effect = _get
        self.mock_session.query.return_value.filter.return_value.all.return_value = subs

    def test_delete_all_deletes_normal_and_disables_announcement(self):
        feed_sub = _make_sub(id="sub-feed", notification_type_id="feed.url_updated")
        rt_sub = _make_sub(id="sub-rt", notification_type_id="gtfs_rt.feed_down")
        ann_sub = _make_sub(id="sub-ann", notification_type_id="api.announcements")
        self._wire_scope_all([feed_sub, rt_sub, ann_sub], _make_user())

        with patch.object(helpers, "remove_contact_from_list") as rem, patch.object(
            helpers, "get_announcements_list_id", return_value=42
        ):
            self.api.delete_subscription("sub-feed", scope="all", db_session=self.mock_session)

        # Every non-announcement subscription is hard-deleted.
        deleted = {c.args[0] for c in self.mock_session.delete.call_args_list}
        self.assertEqual(deleted, {feed_sub, rt_sub})
        # The announcement subscription is disabled (never deleted) and removed from Brevo.
        self.assertNotIn(ann_sub, deleted)
        self.assertFalse(ann_sub.active)
        rem.assert_called_once_with("user@example.com", 42)

    def test_delete_all_without_announcement_skips_brevo(self):
        feed_sub = _make_sub(id="sub-feed", notification_type_id="feed.url_updated")
        self._wire_scope_all([feed_sub], _make_user())

        with patch.object(helpers, "remove_contact_from_list") as rem:
            self.api.delete_subscription("sub-feed", scope="all", db_session=self.mock_session)

        self.mock_session.delete.assert_called_once_with(feed_sub)
        rem.assert_not_called()

    def test_delete_all_missing_returns_404(self):
        self.mock_session.get.return_value = None
        with self.assertRaises(HTTPException) as ctx:
            self.api.delete_subscription("missing", scope="all", db_session=self.mock_session)
        self.assertEqual(ctx.exception.status_code, 404)
        self.mock_session.query.assert_not_called()
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

    def test_delete_announcement_brevo_connection_error_502(self):
        import urllib3

        sub = _make_sub(notification_type_id="api.announcements")
        self.mock_session.get.side_effect = lambda model, key: (
            sub if model is NotificationSubscriptionOrm else _make_user()
        )

        with patch.object(
            helpers,
            "remove_contact_from_list",
            side_effect=urllib3.exceptions.MaxRetryError(None, "url", reason="unreachable"),
        ), patch.object(helpers, "get_announcements_list_id", return_value=42):
            with self.assertRaises(HTTPException) as ctx:
                self.api.delete_subscription("sub-1", db_session=self.mock_session)

        self.assertEqual(ctx.exception.status_code, 502)
        self.mock_session.delete.assert_not_called()
