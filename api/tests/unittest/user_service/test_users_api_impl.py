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
        # The get_user hook calls the real apply_invited_email_grants against db_session
        # unless patched; on a plain MagicMock session that raises (not a query, so
        # _mock_query_first's dispatch doesn't cover it) and would be silently swallowed by
        # the hook's own broad except. Patch it explicitly so these tests exercise get_user's
        # own logic deterministically, not the exception-swallowing path.
        patcher = patch("user_service.impl.users_api_impl.apply_invited_email_grants", return_value=[])
        self.mock_apply_invited_email_grants = patcher.start()
        self.addCleanup(patcher.stop)

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
        self.mock_apply_invited_email_grants.assert_called_once_with(self.mock_session, "uid-123", "user@example.com")

    def test_claim_expires_user_feature_flags_when_something_was_claimed(self):
        user = _make_user()
        _mock_query_first(self.mock_session, user)
        _set_context()
        self.mock_apply_invited_email_grants.return_value = ["program-1"]

        self.api.get_user(db_session=self.mock_session)

        # An existing user's user_feature_flags was already eagerly loaded above; a claim
        # just written via a Core insert wouldn't otherwise show up without this.
        self.mock_session.expire.assert_called_once_with(user, ["user_feature_flags"])

    def test_claim_does_not_expire_user_feature_flags_when_nothing_was_claimed(self):
        user = _make_user()
        _mock_query_first(self.mock_session, user)
        _set_context()
        self.mock_apply_invited_email_grants.return_value = []

        self.api.get_user(db_session=self.mock_session)

        self.mock_session.expire.assert_not_called()

    def test_claim_failure_does_not_break_get_user(self):
        user = _make_user()
        _mock_query_first(self.mock_session, user)
        _set_context()
        self.mock_apply_invited_email_grants.side_effect = RuntimeError("boom")

        result = self.api.get_user(db_session=self.mock_session)

        self.assertEqual(result.id, "uid-123")

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

    def test_opt_in_creates_subscription_and_syncs_brevo(self):
        """Flipping the flag false→true creates the announcements subscription and
        writes the contact to Brevo (the disconnect this fix closes)."""
        user = _make_user(is_registered_to_receive_api_announcements=False)
        user_q = _mock_query_first(self.mock_session, user)
        user_q.filter.return_value.one_or_none.return_value = None  # no existing sub
        _set_context()

        req = self._make_request(is_registered_to_receive_api_announcements=True)
        with patch.object(helpers, "add_contact_to_list") as add, patch.object(
            helpers, "get_announcements_list_id", return_value=42
        ):
            result = self.api.update_user(req, db_session=self.mock_session)

        self.assertTrue(user.is_registered_to_receive_api_announcements)
        self.assertTrue(result.is_registered_to_receive_api_announcements)
        add.assert_called_once()  # Brevo write-back happened
        self.assertEqual(add.call_args[0][:2], ("user@example.com", 42))
        self.mock_session.add.assert_called_once()  # subscription row created

    def test_opt_out_deactivates_subscription_and_removes_from_brevo(self):
        """Flipping the flag true→false removes the contact from Brevo and clears
        the flag."""
        user = _make_user(is_registered_to_receive_api_announcements=True)
        user_q = _mock_query_first(self.mock_session, user)
        existing_sub = MagicMock(active=True)
        user_q.filter.return_value.one_or_none.return_value = existing_sub
        _set_context()

        req = self._make_request(is_registered_to_receive_api_announcements=False)
        with patch.object(helpers, "remove_contact_from_list") as rem, patch.object(
            helpers, "get_announcements_list_id", return_value=42
        ):
            result = self.api.update_user(req, db_session=self.mock_session)

        rem.assert_called_once_with("user@example.com", 42)
        self.assertFalse(existing_sub.active)
        self.assertFalse(user.is_registered_to_receive_api_announcements)
        self.assertFalse(result.is_registered_to_receive_api_announcements)

    def test_flag_unchanged_does_not_touch_brevo(self):
        """Re-sending the same flag value (or updating other fields) makes no
        Brevo call."""
        user = _make_user(is_registered_to_receive_api_announcements=True)
        _mock_query_first(self.mock_session, user)
        _set_context()

        req = self._make_request(is_registered_to_receive_api_announcements=True)
        with patch.object(helpers, "add_contact_to_list") as add, patch.object(
            helpers, "remove_contact_from_list"
        ) as rem:
            self.api.update_user(req, db_session=self.mock_session)

        add.assert_not_called()
        rem.assert_not_called()

    def test_opt_in_brevo_failure_raises_502(self):
        """A Brevo failure while flipping the flag surfaces as 502 (and, in real
        DB use, rolls the whole update back)."""
        import sib_api_v3_sdk

        user = _make_user(is_registered_to_receive_api_announcements=False)
        user_q = _mock_query_first(self.mock_session, user)
        user_q.filter.return_value.one_or_none.return_value = None
        _set_context()

        req = self._make_request(is_registered_to_receive_api_announcements=True)
        with patch.object(
            helpers, "add_contact_to_list", side_effect=sib_api_v3_sdk.rest.ApiException(status=500)
        ), patch.object(helpers, "get_announcements_list_id", return_value=42):
            with self.assertRaises(HTTPException) as ctx:
                self.api.update_user(req, db_session=self.mock_session)

        self.assertEqual(ctx.exception.status_code, 502)

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
        # These tests exercise create/update logic, not the feature-flag gate; enable it.
        gate_patcher = patch.object(UsersApiImpl, "_require_notifications_enabled", return_value=None)
        gate_patcher.start()
        self.addCleanup(gate_patcher.stop)
        # Feed existence is checked against the (separate) feeds DB; treat all feeds as valid here.
        feed_patcher = patch("user_service.impl.users_api_impl.find_unknown_feed_ids", return_value=[])
        feed_patcher.start()
        self.addCleanup(feed_patcher.stop)
        # Feed metadata is resolved from the feeds DB; default to none resolved in these tests.
        meta_patcher = patch("user_service.impl.users_api_impl.resolve_feed_metadata", return_value={})
        meta_patcher.start()
        self.addCleanup(meta_patcher.stop)

    def _make_sub(self, **kwargs):
        from shared.users_database_gen.sqlacodegen_models import NotificationSubscription as Orm

        defaults = dict(
            id="sub-1",
            user_id="uid-123",
            notification_type_id="feed.published",
            active=True,
            created_at=FIXED_NOW,
        )
        defaults.update(kwargs)
        return Orm(**defaults)

    # ── list ──
    def test_get_user_subscriptions_returns_user_subs(self):
        sub = self._make_sub()
        query = self.mock_session.query.return_value
        # The list query eager-loads feeds via .options(selectinload(...)).
        query.options.return_value.filter.return_value.order_by.return_value.all.return_value = [sub]

        result = self.api.get_user_subscriptions(db_session=self.mock_session)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "sub-1")
        self.assertEqual(result[0].notification_id, "feed.published")
        # A non feed-scoped subscription reports no feeds.
        self.assertIsNone(result[0].feeds)

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

    # ── create: feed-scoped (issue #1778) ──
    def test_create_feed_scoped_persists_feed_ids(self):
        from shared.users_database_gen.sqlacodegen_models import NotificationType

        self.mock_session.get.side_effect = lambda model, key: (
            NotificationType(id="feed.url_updated") if model is NotificationType else _make_user()
        )
        self.mock_session.query.return_value.filter.return_value.one_or_none.return_value = None

        result = self.api.create_user_subscription(
            CreateNotificationSubscriptionRequest(notification_id="feed.url_updated", feed_ids=["mdb-2", "mdb-1"]),
            db_session=self.mock_session,
        )

        self.mock_session.add.assert_called_once()
        added_sub = self.mock_session.add.call_args[0][0]
        # Both feeds are attached to the new subscription's join collection.
        self.assertEqual({f.feed_stable_id for f in added_sub.notification_subscription_feeds}, {"mdb-1", "mdb-2"})
        # Response feeds are sorted by id and deduped.
        self.assertEqual([f.feed_id for f in result.feeds], ["mdb-1", "mdb-2"])

    def test_create_feed_scoped_returns_resolved_feed_metadata(self):
        from shared.users_database_gen.sqlacodegen_models import NotificationType

        self.mock_session.get.side_effect = lambda model, key: (
            NotificationType(id="feed.url_updated") if model is NotificationType else _make_user()
        )
        self.mock_session.query.return_value.filter.return_value.one_or_none.return_value = None

        metadata = {"mdb-1": {"data_type": "gtfs", "provider": "MTA", "feed_name": "Subway"}}
        with patch("user_service.impl.users_api_impl.resolve_feed_metadata", return_value=metadata):
            result = self.api.create_user_subscription(
                CreateNotificationSubscriptionRequest(notification_id="feed.url_updated", feed_ids=["mdb-1", "mdb-2"]),
                db_session=self.mock_session,
            )

        by_id = {f.feed_id: f for f in result.feeds}
        self.assertEqual(set(by_id), {"mdb-1", "mdb-2"})
        self.assertEqual(
            (by_id["mdb-1"].data_type, by_id["mdb-1"].provider, by_id["mdb-1"].feed_name), ("gtfs", "MTA", "Subway")
        )
        # A feed with no resolved metadata (e.g. deleted) still appears with null fields.
        self.assertEqual(
            (by_id["mdb-2"].data_type, by_id["mdb-2"].provider, by_id["mdb-2"].feed_name), (None, None, None)
        )

    def test_create_feed_scoped_dedupes_feed_ids(self):
        from shared.users_database_gen.sqlacodegen_models import NotificationType

        self.mock_session.get.side_effect = lambda model, key: (
            NotificationType(id="feed.coverage") if model is NotificationType else _make_user()
        )
        self.mock_session.query.return_value.filter.return_value.one_or_none.return_value = None

        result = self.api.create_user_subscription(
            CreateNotificationSubscriptionRequest(notification_id="feed.coverage", feed_ids=["mdb-1", "mdb-1"]),
            db_session=self.mock_session,
        )

        self.assertEqual([f.feed_id for f in result.feeds], ["mdb-1"])

    def test_create_feed_scoped_rejects_unknown_feed_ids(self):
        from shared.users_database_gen.sqlacodegen_models import NotificationType

        self.mock_session.get.side_effect = lambda model, key: (
            NotificationType(id="feed.url_updated") if model is NotificationType else _make_user()
        )
        self.mock_session.query.return_value.filter.return_value.one_or_none.return_value = None

        with patch("user_service.impl.users_api_impl.find_unknown_feed_ids", return_value=["mdba-100"]):
            with self.assertRaises(HTTPException) as ctx:
                self.api.create_user_subscription(
                    CreateNotificationSubscriptionRequest(notification_id="feed.url_updated", feed_ids=["mdba-100"]),
                    db_session=self.mock_session,
                )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("mdba-100", ctx.exception.detail)
        self.mock_session.add.assert_not_called()

    def test_create_feed_scoped_requires_feed_ids(self):
        from shared.users_database_gen.sqlacodegen_models import NotificationType

        self.mock_session.get.side_effect = lambda model, key: (
            NotificationType(id="feed.url_availability") if model is NotificationType else _make_user()
        )

        for req in (
            CreateNotificationSubscriptionRequest(notification_id="feed.url_availability"),
            CreateNotificationSubscriptionRequest(notification_id="feed.url_availability", feed_ids=[]),
        ):
            with self.assertRaises(HTTPException) as ctx:
                self.api.create_user_subscription(req, db_session=self.mock_session)
            self.assertEqual(ctx.exception.status_code, 400)
        self.mock_session.add.assert_not_called()

    def test_create_non_scoped_rejects_feed_ids(self):
        from shared.users_database_gen.sqlacodegen_models import NotificationType

        self.mock_session.get.side_effect = lambda model, key: (
            NotificationType(id="feed.published") if model is NotificationType else _make_user()
        )

        with self.assertRaises(HTTPException) as ctx:
            self.api.create_user_subscription(
                CreateNotificationSubscriptionRequest(notification_id="feed.published", feed_ids=["mdb-1"]),
                db_session=self.mock_session,
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.mock_session.add.assert_not_called()

    def test_create_feed_scoped_merges_into_existing_feeds(self):
        from shared.users_database_gen.sqlacodegen_models import (
            NotificationType,
            NotificationSubscriptionFeed as FeedOrm,
        )

        existing = self._make_sub(notification_type_id="feed.url_updated", active=False)
        existing.notification_subscription_feeds.append(FeedOrm(feed_stable_id="mdb-old"))
        self.mock_session.get.side_effect = lambda model, key: (
            NotificationType(id="feed.url_updated") if model is NotificationType else _make_user()
        )
        self.mock_session.query.return_value.filter.return_value.one_or_none.return_value = existing

        result = self.api.create_user_subscription(
            CreateNotificationSubscriptionRequest(notification_id="feed.url_updated", feed_ids=["mdb-new"]),
            db_session=self.mock_session,
        )

        self.mock_session.add.assert_not_called()
        self.assertTrue(existing.active)
        # The existing feed is kept and the new one is merged in, not replaced.
        self.assertEqual({f.feed_stable_id for f in existing.notification_subscription_feeds}, {"mdb-old", "mdb-new"})
        self.assertEqual([f.feed_id for f in result.feeds], ["mdb-new", "mdb-old"])

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

    # ── update: remove_feed_ids ──
    def test_update_remove_feed_ids_removes_specified_feed(self):
        from shared.users_database_gen.sqlacodegen_models import NotificationSubscriptionFeed as FeedOrm

        sub = self._make_sub(notification_type_id="feed.url_updated")
        sub.notification_subscription_feeds.extend([FeedOrm(feed_stable_id="mdb-1"), FeedOrm(feed_stable_id="mdb-2")])
        self.mock_session.get.return_value = sub

        result = self.api.update_user_subscription(
            "sub-1",
            UpdateNotificationSubscriptionRequest(remove_feed_ids=["mdb-1"]),
            db_session=self.mock_session,
        )

        self.assertEqual({f.feed_stable_id for f in sub.notification_subscription_feeds}, {"mdb-2"})
        self.assertEqual([f.feed_id for f in result.feeds], ["mdb-2"])

    def test_update_remove_feed_ids_is_noop_for_id_not_present(self):
        from shared.users_database_gen.sqlacodegen_models import NotificationSubscriptionFeed as FeedOrm

        sub = self._make_sub(notification_type_id="feed.url_updated")
        sub.notification_subscription_feeds.append(FeedOrm(feed_stable_id="mdb-1"))
        self.mock_session.get.return_value = sub

        result = self.api.update_user_subscription(
            "sub-1",
            UpdateNotificationSubscriptionRequest(remove_feed_ids=["mdb-999"]),
            db_session=self.mock_session,
        )

        self.assertEqual({f.feed_stable_id for f in sub.notification_subscription_feeds}, {"mdb-1"})
        self.assertEqual([f.feed_id for f in result.feeds], ["mdb-1"])

    def test_update_remove_feed_ids_rejects_non_feed_scoped_type(self):
        sub = self._make_sub(notification_type_id="api.announcements")
        self.mock_session.get.return_value = sub

        with self.assertRaises(HTTPException) as ctx:
            self.api.update_user_subscription(
                "sub-1",
                UpdateNotificationSubscriptionRequest(remove_feed_ids=["mdb-1"]),
                db_session=self.mock_session,
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_update_remove_feed_ids_deletes_subscription_when_emptied(self):
        from shared.users_database_gen.sqlacodegen_models import NotificationSubscriptionFeed as FeedOrm

        sub = self._make_sub(notification_type_id="feed.url_updated")
        sub.notification_subscription_feeds.append(FeedOrm(feed_stable_id="mdb-1"))
        self.mock_session.get.return_value = sub

        result = self.api.update_user_subscription(
            "sub-1",
            UpdateNotificationSubscriptionRequest(remove_feed_ids=["mdb-1"]),
            db_session=self.mock_session,
        )

        # A feed-scoped subscription can't exist with no feeds, so removing the last feed
        # deletes it entirely instead of leaving an empty subscription behind.
        self.mock_session.delete.assert_called_once_with(sub)
        self.assertEqual(result.id, "sub-1")
        self.assertIsNone(result.feeds)

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


def _make_feed_row(feed_stable_id, subscription_id="sub-1", **kwargs):
    from shared.users_database_gen.sqlacodegen_models import NotificationSubscriptionFeed as FeedRowOrm

    defaults = dict(subscription_id=subscription_id, feed_stable_id=feed_stable_id, created_at=FIXED_NOW)
    defaults.update(kwargs)
    return FeedRowOrm(**defaults)


def _mock_feed_group_rows(session, rows):
    """Wire the `.join().filter().order_by().all()` chain used by the unfiltered (list) query."""
    session.query.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = rows


def _mock_feed_group_rows_filtered(session, rows):
    """Wire the `.join().filter().filter().order_by().all()` chain used by the feed_stable_id-filtered query."""
    chain = session.query.return_value.join.return_value.filter.return_value.filter.return_value
    chain.order_by.return_value.all.return_value = rows


class TestSubscriptionFeedGroups(unittest.TestCase):
    """GET /v1/user/subscriptions/feeds and GET /v1/user/subscriptions/feeds/{id}."""

    def setUp(self):
        self.api = UsersApiImpl()
        self.mock_session = MagicMock()
        _set_context()
        meta_patcher = patch("user_service.impl.users_api_impl.resolve_feed_metadata", return_value={})
        meta_patcher.start()
        self.addCleanup(meta_patcher.stop)

    def _make_sub(self, **kwargs):
        from shared.users_database_gen.sqlacodegen_models import NotificationSubscription as Orm

        defaults = dict(
            id="sub-1",
            user_id="uid-123",
            notification_type_id="feed.url_updated",
            active=True,
            created_at=FIXED_NOW,
        )
        defaults.update(kwargs)
        return Orm(**defaults)

    # ── list ──
    def test_get_user_subscription_feeds_empty(self):
        _mock_feed_group_rows(self.mock_session, [])

        result = self.api.get_user_subscription_feeds(db_session=self.mock_session)

        self.assertEqual(result, [])

    def test_get_user_subscription_feeds_single_feed(self):
        sub = self._make_sub()
        row = _make_feed_row("mdb-1", subscription_id=sub.id)
        _mock_feed_group_rows(self.mock_session, [(row, sub)])

        result = self.api.get_user_subscription_feeds(db_session=self.mock_session)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].feed_id, "mdb-1")
        self.assertEqual(len(result[0].subscriptions), 1)
        self.assertEqual(result[0].subscriptions[0].id, "sub-1")
        self.assertEqual(result[0].subscriptions[0].notification_id, "feed.url_updated")

    def test_get_user_subscription_feeds_groups_by_feed(self):
        sub1 = self._make_sub(id="sub-1")
        sub2 = self._make_sub(id="sub-2", notification_type_id="feed.coverage")
        rows = [
            (_make_feed_row("mdb-1", subscription_id="sub-1"), sub1),
            (_make_feed_row("mdb-2", subscription_id="sub-2"), sub2),
        ]
        _mock_feed_group_rows(self.mock_session, rows)

        result = self.api.get_user_subscription_feeds(db_session=self.mock_session)

        self.assertEqual([g.feed_id for g in result], ["mdb-1", "mdb-2"])
        self.assertEqual(result[0].subscriptions[0].id, "sub-1")
        self.assertEqual(result[1].subscriptions[0].id, "sub-2")

    def test_get_user_subscription_feeds_subscription_targets_multiple_feeds(self):
        sub = self._make_sub()
        rows = [
            (_make_feed_row("mdb-1", subscription_id=sub.id), sub),
            (_make_feed_row("mdb-2", subscription_id=sub.id), sub),
        ]
        _mock_feed_group_rows(self.mock_session, rows)

        result = self.api.get_user_subscription_feeds(db_session=self.mock_session)

        self.assertEqual([g.feed_id for g in result], ["mdb-1", "mdb-2"])
        self.assertEqual(result[0].subscriptions[0].id, sub.id)
        self.assertEqual(result[1].subscriptions[0].id, sub.id)

    def test_get_user_subscription_feeds_includes_inactive(self):
        sub = self._make_sub(active=False)
        row = _make_feed_row("mdb-1", subscription_id=sub.id)
        _mock_feed_group_rows(self.mock_session, [(row, sub)])

        result = self.api.get_user_subscription_feeds(db_session=self.mock_session)

        self.assertFalse(result[0].subscriptions[0].active)

    def test_get_user_subscription_feeds_resolves_feed_metadata(self):
        sub = self._make_sub()
        row = _make_feed_row("mdb-1", subscription_id=sub.id)
        _mock_feed_group_rows(self.mock_session, [(row, sub)])

        with patch(
            "user_service.impl.users_api_impl.resolve_feed_metadata",
            return_value={"mdb-1": {"data_type": "gtfs", "provider": "Test Transit", "feed_name": "Test Feed"}},
        ):
            result = self.api.get_user_subscription_feeds(db_session=self.mock_session)

        self.assertEqual(result[0].data_type, "gtfs")
        self.assertEqual(result[0].provider, "Test Transit")
        self.assertEqual(result[0].feed_name, "Test Feed")

    def test_get_user_subscription_feeds_guest_403(self):
        _set_context(is_guest=True)
        with self.assertRaises(HTTPException) as ctx:
            self.api.get_user_subscription_feeds(db_session=self.mock_session)
        self.assertEqual(ctx.exception.status_code, 403)

    # ── by id ──
    def test_get_user_subscription_feed_by_id_returns_group(self):
        sub = self._make_sub()
        row = _make_feed_row("mdb-1", subscription_id=sub.id)
        _mock_feed_group_rows_filtered(self.mock_session, [(row, sub)])

        result = self.api.get_user_subscription_feed_by_id("mdb-1", db_session=self.mock_session)

        self.assertEqual(result.feed_id, "mdb-1")
        self.assertEqual(len(result.subscriptions), 1)
        self.assertEqual(result.subscriptions[0].id, "sub-1")

    def test_get_user_subscription_feed_by_id_404_when_no_rows(self):
        _mock_feed_group_rows_filtered(self.mock_session, [])

        with self.assertRaises(HTTPException) as ctx:
            self.api.get_user_subscription_feed_by_id("mdb-999", db_session=self.mock_session)

        self.assertEqual(ctx.exception.status_code, 404)

    def test_get_user_subscription_feed_by_id_guest_403(self):
        _set_context(is_guest=True)
        with self.assertRaises(HTTPException) as ctx:
            self.api.get_user_subscription_feed_by_id("mdb-1", db_session=self.mock_session)
        self.assertEqual(ctx.exception.status_code, 403)


class TestSubscriptionGate(unittest.TestCase):
    """The isNotificationsEnabled feature flag gates POST/PATCH subscriptions."""

    def setUp(self):
        self.api = UsersApiImpl()
        self.mock_session = MagicMock()
        _set_context()

    def _configure_gate(self, *, default=False, disabled=False, has_override=False, override_value=None):
        from shared.users_database_gen.sqlacodegen_models import (
            FeatureFlag,
            NotificationType,
            UserFeatureFlag,
        )

        flag = FeatureFlag(id="isNotificationsEnabled", value_type="boolean", default_value=default, disabled=disabled)
        override = (
            UserFeatureFlag(user_id="uid-123", feature_flag_id="isNotificationsEnabled", value=override_value)
            if has_override
            else None
        )

        def _get(model, key):
            if model is FeatureFlag:
                return flag
            if model is UserFeatureFlag:
                return override
            if model is NotificationType:
                return NotificationType(id="feed.published")
            return _make_user()

        self.mock_session.get.side_effect = _get
        self.mock_session.query.return_value.filter.return_value.one_or_none.return_value = None

    def _create(self):
        return self.api.create_user_subscription(
            CreateNotificationSubscriptionRequest(notification_id="feed.published"), db_session=self.mock_session
        )

    def test_create_denied_when_default_false(self):
        self._configure_gate(default=False)
        with self.assertRaises(HTTPException) as ctx:
            self._create()
        self.assertEqual(ctx.exception.status_code, 403)
        self.mock_session.add.assert_not_called()

    def test_create_allowed_when_default_true(self):
        self._configure_gate(default=True)
        result = self._create()
        self.assertEqual(result.notification_id, "feed.published")
        self.mock_session.add.assert_called_once()

    def test_create_allowed_with_user_override_true(self):
        self._configure_gate(default=False, has_override=True, override_value=True)
        self.assertEqual(self._create().notification_id, "feed.published")

    def test_create_denied_with_user_override_false(self):
        self._configure_gate(default=True, has_override=True, override_value=False)
        with self.assertRaises(HTTPException) as ctx:
            self._create()
        self.assertEqual(ctx.exception.status_code, 403)

    def test_create_allowed_when_flag_disabled_but_granted(self):
        # `disabled` only hides the flag from the consumer profile; it must NOT block a granted
        # user from subscribing (backend-only concern).
        self._configure_gate(default=False, disabled=True, has_override=True, override_value=True)
        self.assertEqual(self._create().notification_id, "feed.published")
        self.mock_session.add.assert_called_once()

    def test_create_denied_when_flag_missing(self):
        from shared.users_database_gen.sqlacodegen_models import FeatureFlag, NotificationType

        def _get(model, key):
            if model is FeatureFlag:
                return None
            if model is NotificationType:
                return NotificationType(id="feed.published")
            return _make_user()

        self.mock_session.get.side_effect = _get
        with self.assertRaises(HTTPException) as ctx:
            self._create()
        self.assertEqual(ctx.exception.status_code, 403)

    def test_update_denied_when_default_false(self):
        self._configure_gate(default=False)
        with self.assertRaises(HTTPException) as ctx:
            self.api.update_user_subscription(
                "sub-1", UpdateNotificationSubscriptionRequest(active=False), db_session=self.mock_session
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.mock_session.delete.assert_not_called()

    def test_delete_denied_when_default_false(self):
        self._configure_gate(default=False)
        with self.assertRaises(HTTPException) as ctx:
            self.api.delete_user_subscription("sub-1", db_session=self.mock_session)
        self.assertEqual(ctx.exception.status_code, 403)
        self.mock_session.delete.assert_not_called()


class TestAdminSummaryGate(unittest.TestCase):
    """admin.event_summary additionally requires the isAdminSummarySubscriptionEnabled flag."""

    ADMIN_TYPE = "admin.event_summary"

    def setUp(self):
        self.api = UsersApiImpl()
        self.mock_session = MagicMock()
        _set_context()

    def _configure(self, *, notifications=True, admin=True, sub=None):
        """Wire get() to resolve both gate flags (enabled per args) and, optionally, a subscription."""
        from shared.users_database_gen.sqlacodegen_models import (
            FeatureFlag,
            NotificationSubscription as Orm,
            NotificationType,
            UserFeatureFlag,
        )

        flags = {
            "isNotificationsEnabled": FeatureFlag(
                id="isNotificationsEnabled", value_type="boolean", default_value=notifications, disabled=False
            ),
            "isAdminSummarySubscriptionEnabled": FeatureFlag(
                id="isAdminSummarySubscriptionEnabled", value_type="boolean", default_value=admin, disabled=False
            ),
        }

        def _get(model, key):
            if model is FeatureFlag:
                return flags.get(key)
            if model is UserFeatureFlag:
                return None
            if model is NotificationType:
                return NotificationType(id=key)
            if model is Orm:
                return sub
            return _make_user()

        self.mock_session.get.side_effect = _get
        self.mock_session.query.return_value.filter.return_value.one_or_none.return_value = None

    def _create(self, notification_id):
        return self.api.create_user_subscription(
            CreateNotificationSubscriptionRequest(notification_id=notification_id), db_session=self.mock_session
        )

    def test_create_admin_allowed_when_admin_flag_true(self):
        self._configure(notifications=True, admin=True)
        self.assertEqual(self._create(self.ADMIN_TYPE).notification_id, self.ADMIN_TYPE)

    def test_create_admin_denied_when_admin_flag_false(self):
        self._configure(notifications=True, admin=False)
        with self.assertRaises(HTTPException) as ctx:
            self._create(self.ADMIN_TYPE)
        self.assertEqual(ctx.exception.status_code, 403)
        self.mock_session.add.assert_not_called()

    def test_create_admin_denied_when_notifications_flag_false(self):
        # The general gate runs first, so it fails even with the admin flag on.
        self._configure(notifications=False, admin=True)
        with self.assertRaises(HTTPException) as ctx:
            self._create(self.ADMIN_TYPE)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_create_non_admin_type_ignores_admin_flag(self):
        # A non-admin type is unaffected by the admin flag being off.
        self._configure(notifications=True, admin=False)
        self.assertEqual(self._create("feed.published").notification_id, "feed.published")

    def test_update_admin_denied_when_admin_flag_false(self):
        from shared.users_database_gen.sqlacodegen_models import NotificationSubscription as Orm

        sub = Orm(
            id="sub-1",
            user_id="uid-123",
            notification_type_id=self.ADMIN_TYPE,
            active=True,
            created_at=FIXED_NOW,
        )
        self._configure(notifications=True, admin=False, sub=sub)
        with self.assertRaises(HTTPException) as ctx:
            self.api.update_user_subscription(
                "sub-1", UpdateNotificationSubscriptionRequest(active=False), db_session=self.mock_session
            )
        self.assertEqual(ctx.exception.status_code, 403)


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
