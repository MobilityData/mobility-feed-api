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
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import sib_api_v3_sdk
from fastapi import HTTPException

from feeds_operations.impl.notifications_api_impl import (
    NotificationsApiImpl,
    _brevo_sync_issues,
)
from shared.common.brevo import BrevoContactListState, BrevoSubscriptionStatus
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    NotificationEvent,
    NotificationEventFeed,
    NotificationLog,
    NotificationSubscription,
    NotificationSubscriptionFeed,
)

FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
MODULE = "feeds_operations.impl.notifications_api_impl"


def _make_event(event_id="evt-1", feeds=None, **kwargs) -> NotificationEvent:
    event = NotificationEvent(
        id=event_id,
        notification_type_id=kwargs.get("notification_type_id", "feed.url_updated"),
        event_subtype=kwargs.get("event_subtype", "url_replaced"),
        source=kwargs.get("source", "operations_api"),
        payload=kwargs.get("payload", {"old_url": "http://a", "new_url": "http://b"}),
        created_at=FIXED_NOW,
    )
    event.notification_event_feeds = [
        NotificationEventFeed(
            id=f"{event_id}-{stable_id}",
            notification_event_id=event_id,
            feed_stable_id=stable_id,
            role=role,
        )
        for stable_id, role in (feeds if feeds is not None else [("mdb-1", "subject")])
    ]
    return event


def _make_log(log_id="log-1", status="sent", **kwargs) -> NotificationLog:
    return NotificationLog(
        id=log_id,
        notification_event_id=kwargs.get("notification_event_id", "evt-1"),
        subscription_id=kwargs.get("subscription_id", "sub-1"),
        channel="email",
        status=status,
        retry_count=kwargs.get("retry_count", 0),
        error_message=kwargs.get("error_message"),
        sent_at=FIXED_NOW,
    )


def _make_subscription(
    sub_id="sub-1",
    notification_type_id="feed.url_updated",
    active=True,
    feed_ids=None,
) -> NotificationSubscription:
    sub = NotificationSubscription(
        id=sub_id,
        user_id="uid-1",
        notification_type_id=notification_type_id,
        active=active,
        cadence="weekly",
        digest=True,
        filter_params=None,
        created_at=FIXED_NOW,
        active_since=FIXED_NOW,
    )
    sub.notification_subscription_feeds = [
        NotificationSubscriptionFeed(subscription_id=sub_id, feed_stable_id=f)
        for f in (feed_ids or [])
    ]
    return sub


def _make_user(opt_in=True) -> AppUser:
    return AppUser(
        id="uid-1",
        email="user@example.com",
        is_registered_to_receive_api_announcements=opt_in,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _chain(result):
    """A query mock whose builder methods return itself and whose terminals return `result`."""
    q = MagicMock()
    for name in (
        "options",
        "filter",
        "filter_by",
        "order_by",
        "offset",
        "limit",
        "outerjoin",
    ):
        getattr(q, name).return_value = q
    items = result if isinstance(result, list) else ([result] if result else [])
    q.all.return_value = items
    q.count.return_value = len(items)
    q.first.return_value = items[0] if items else None
    return q


def _brevo(status=BrevoSubscriptionStatus.SUBSCRIBED, in_list=True, **kwargs):
    return BrevoContactListState(
        status=status,
        in_list=in_list,
        email_blacklisted=kwargs.get("email_blacklisted", False),
        list_unsubscribed=kwargs.get("list_unsubscribed", False),
        mdb_subscription_id=kwargs.get("mdb_subscription_id", "sub-a"),
    )


class TestListNotificationEvents(unittest.TestCase):
    def setUp(self):
        self.api = NotificationsApiImpl()
        self.session = MagicMock()

    def test_returns_paginated_events_with_feeds(self):
        event = _make_event(feeds=[("mdb-2", "target"), ("mdb-1", "subject")])
        self.session.query.return_value = _chain([event])

        result = self.api.list_notification_events(db_session=self.session)

        self.assertEqual(result.total, 1)
        self.assertEqual(result.limit, 100)
        self.assertEqual(result.offset, 0)
        self.assertEqual(result.events[0].id, "evt-1")
        self.assertEqual(result.events[0].payload["new_url"], "http://b")
        # Sorted by role then stable ID, so the output is stable.
        self.assertEqual(
            [(f.feed_stable_id, f.role) for f in result.events[0].feeds],
            [("mdb-1", "subject"), ("mdb-2", "target")],
        )

    def test_applies_every_filter(self):
        q = _chain([])
        self.session.query.return_value = q

        self.api.list_notification_events(
            notification_type_id="feed.url_updated",
            event_subtype="url_replaced",
            source="operations_api",
            feed_stable_id="mdb-1",
            created_after="2026-01-01T00:00:00Z",
            created_before="2026-02-01T00:00:00Z",
            limit=10,
            offset=5,
            db_session=self.session,
        )

        self.assertEqual(q.filter.call_count, 6)
        q.offset.assert_called_with(5)
        q.limit.assert_called_with(10)

    def test_rejects_invalid_date(self):
        self.session.query.return_value = _chain([])

        with self.assertRaises(HTTPException) as ctx:
            self.api.list_notification_events(
                created_after="yesterday", db_session=self.session
            )
        self.assertEqual(ctx.exception.status_code, 400)


class TestGetNotificationEvent(unittest.TestCase):
    def setUp(self):
        self.api = NotificationsApiImpl()
        self.session = MagicMock()

    def test_returns_event_with_logs(self):
        event = _make_event()
        rows = [(_make_log(), "uid-1", "feed.url_updated")]
        self.session.query.side_effect = [_chain(event), _chain(rows)]

        result = self.api.get_notification_event("evt-1", db_session=self.session)

        self.assertEqual(result.id, "evt-1")
        self.assertEqual(len(result.logs), 1)
        self.assertEqual(result.logs[0].user_id, "uid-1")
        self.assertEqual(result.logs[0].notification_type_id, "feed.url_updated")

    def test_not_found(self):
        self.session.query.return_value = _chain(None)

        with self.assertRaises(HTTPException) as ctx:
            self.api.get_notification_event("missing", db_session=self.session)
        self.assertEqual(ctx.exception.status_code, 404)


class TestListNotificationLogs(unittest.TestCase):
    def setUp(self):
        self.api = NotificationsApiImpl()
        self.session = MagicMock()

    def test_returns_logs_with_subscription_owner(self):
        rows = [
            (
                _make_log(status="failed", retry_count=2, error_message="boom"),
                "uid-1",
                "feed.url_updated",
            )
        ]
        self.session.query.return_value = _chain(rows)

        result = self.api.list_notification_logs(db_session=self.session)

        self.assertEqual(result.total, 1)
        log = result.logs[0]
        self.assertEqual(log.status, "failed")
        self.assertEqual(log.retry_count, 2)
        self.assertEqual(log.error_message, "boom")
        self.assertEqual(log.user_id, "uid-1")

    def test_applies_every_filter(self):
        q = _chain([])
        self.session.query.return_value = q

        self.api.list_notification_logs(
            status="permanently_failed",
            subscription_id="sub-1",
            user_id="uid-1",
            notification_event_id="evt-1",
            notification_type_id="feed.url_updated",
            sent_after="2026-01-01T00:00:00+00:00",
            sent_before="2026-01-02T00:00:00+00:00",
            db_session=self.session,
        )

        self.assertEqual(q.filter.call_count, 7)

    def test_rejects_unknown_status(self):
        with self.assertRaises(HTTPException) as ctx:
            self.api.list_notification_logs(status="bounced", db_session=self.session)
        self.assertEqual(ctx.exception.status_code, 400)
        self.session.query.assert_not_called()


class TestGetOperationsUserSubscriptions(unittest.TestCase):
    def setUp(self):
        self.api = NotificationsApiImpl()
        self.session = MagicMock()

    def test_returns_subscriptions_with_feed_ids(self):
        self.session.get.return_value = _make_user()
        sub = _make_subscription(feed_ids=["mdb-9", "mdb-1"])
        self.session.query.return_value = _chain([sub])

        result = self.api.get_operations_user_subscriptions(
            "uid-1", db_session=self.session
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "sub-1")
        self.assertEqual(result[0].feed_ids, ["mdb-1", "mdb-9"])
        self.assertEqual(result[0].cadence, "weekly")
        self.assertTrue(result[0].digest)

    def test_user_not_found(self):
        self.session.get.return_value = None

        with self.assertRaises(HTTPException) as ctx:
            self.api.get_operations_user_subscriptions(
                "missing", db_session=self.session
            )
        self.assertEqual(ctx.exception.status_code, 404)


class TestBrevoSyncIssues(unittest.TestCase):
    def test_in_sync_when_subscribed_everywhere(self):
        self.assertEqual(_brevo_sync_issues("sub-a", True, 1, True, _brevo()), [])

    def test_in_sync_when_opted_out_everywhere(self):
        brevo = _brevo(
            status=BrevoSubscriptionStatus.UNSUBSCRIBED,
            in_list=False,
            list_unsubscribed=True,
        )
        self.assertEqual(_brevo_sync_issues("sub-a", False, 1, False, brevo), [])

    def test_in_sync_when_never_opted_in_and_no_contact(self):
        brevo = BrevoContactListState(status=BrevoSubscriptionStatus.NOT_FOUND)
        issues = _brevo_sync_issues(None, None, 0, False, brevo)
        self.assertEqual(issues, ["No api.announcements subscription row."])

    def test_flag_disagrees_with_row(self):
        issues = _brevo_sync_issues("sub-a", True, 1, False, _brevo())
        self.assertIn(
            "Subscription active is True but the app_user opt-in flag is False.", issues
        )

    def test_duplicate_rows(self):
        issues = _brevo_sync_issues("sub-a", True, 2, True, _brevo())
        self.assertIn("2 api.announcements subscription rows; expected one.", issues)

    def test_opted_in_but_unsubscribed_in_brevo(self):
        brevo = _brevo(
            status=BrevoSubscriptionStatus.UNSUBSCRIBED, list_unsubscribed=True
        )
        issues = _brevo_sync_issues("sub-a", True, 1, True, brevo)
        self.assertEqual(
            issues,
            [
                "Opted in but the contact unsubscribed from the announcements list in Brevo."
            ],
        )

    def test_opted_in_but_blacklisted(self):
        brevo = _brevo(
            status=BrevoSubscriptionStatus.UNSUBSCRIBED, email_blacklisted=True
        )
        issues = _brevo_sync_issues("sub-a", True, 1, True, brevo)
        self.assertIn(
            "Opted in but the Brevo contact is blacklisted (unsubscribed from all campaigns).",
            issues,
        )

    def test_opted_in_but_no_contact(self):
        brevo = BrevoContactListState(status=BrevoSubscriptionStatus.NOT_FOUND)
        issues = _brevo_sync_issues("sub-a", True, 1, True, brevo)
        self.assertEqual(issues, ["Opted in but Brevo has no contact for this email."])

    def test_opted_in_but_not_on_list(self):
        issues = _brevo_sync_issues("sub-a", True, 1, True, _brevo(in_list=False))
        self.assertEqual(
            issues, ["Opted in but the contact is not on the announcements list."]
        )

    def test_opted_out_but_still_on_list(self):
        issues = _brevo_sync_issues("sub-a", False, 1, False, _brevo())
        self.assertEqual(
            issues,
            [
                "Opted out but the contact is still subscribed to the announcements list in Brevo."
            ],
        )

    def test_subscription_id_attribute_mismatch(self):
        issues = _brevo_sync_issues(
            "sub-a", True, 1, True, _brevo(mdb_subscription_id="sub-old")
        )
        self.assertEqual(
            issues,
            ["Brevo MDB_SUBSCRIPTION_ID is sub-old but the subscription ID is sub-a."],
        )

    def test_subscription_id_attribute_unset(self):
        issues = _brevo_sync_issues(
            "sub-a", True, 1, True, _brevo(mdb_subscription_id=None)
        )
        self.assertEqual(
            issues,
            ["Brevo MDB_SUBSCRIPTION_ID is unset but the subscription ID is sub-a."],
        )

    def test_flag_decides_when_there_is_no_row(self):
        issues = _brevo_sync_issues(None, None, 0, True, _brevo(in_list=False))
        self.assertIn(
            "Opted in but the contact is not on the announcements list.", issues
        )


@patch(f"{MODULE}.get_announcements_list_id", return_value=7)
@patch(f"{MODULE}.get_contact_list_state")
class TestGetOperationsUserBrevoSync(unittest.TestCase):
    def setUp(self):
        self.api = NotificationsApiImpl()
        self.session = MagicMock()

    def test_reports_in_sync(self, mock_state, _list_id):
        self.session.get.return_value = _make_user(opt_in=True)
        sub = _make_subscription(
            sub_id="sub-a", notification_type_id="api.announcements"
        )
        self.session.query.return_value = _chain([sub])
        mock_state.return_value = _brevo()

        result = self.api.get_operations_user_brevo_sync(
            "uid-1", db_session=self.session
        )

        mock_state.assert_called_once_with("user@example.com", 7)
        self.session.commit.assert_called_once()
        self.assertTrue(result.in_sync)
        self.assertEqual(result.issues, [])
        self.assertEqual(result.subscription_id, "sub-a")
        self.assertTrue(result.subscription_active)
        self.assertEqual(result.brevo.status, "subscribed")
        self.assertEqual(result.brevo.mdb_subscription_id, "sub-a")

    def test_reports_drift(self, mock_state, _list_id):
        self.session.get.return_value = _make_user(opt_in=True)
        sub = _make_subscription(
            sub_id="sub-a", notification_type_id="api.announcements"
        )
        self.session.query.return_value = _chain([sub])
        mock_state.return_value = _brevo(
            status=BrevoSubscriptionStatus.UNSUBSCRIBED, email_blacklisted=True
        )

        result = self.api.get_operations_user_brevo_sync(
            "uid-1", db_session=self.session
        )

        self.assertFalse(result.in_sync)
        self.assertEqual(len(result.issues), 1)

    def test_user_not_found(self, mock_state, _list_id):
        self.session.get.return_value = None

        with self.assertRaises(HTTPException) as ctx:
            self.api.get_operations_user_brevo_sync("missing", db_session=self.session)
        self.assertEqual(ctx.exception.status_code, 404)
        mock_state.assert_not_called()

    def test_brevo_error_is_502(self, mock_state, _list_id):
        self.session.get.return_value = _make_user()
        self.session.query.return_value = _chain([])
        mock_state.side_effect = sib_api_v3_sdk.rest.ApiException(status=500)

        with self.assertRaises(HTTPException) as ctx:
            self.api.get_operations_user_brevo_sync("uid-1", db_session=self.session)
        self.assertEqual(ctx.exception.status_code, 502)

    def test_brevo_not_configured_is_500(self, mock_state, list_id):
        self.session.get.return_value = _make_user()
        self.session.query.return_value = _chain([])
        list_id.side_effect = RuntimeError(
            "BREVO_API_ANNOUNCEMENTS_LIST_ID environment variable is not set"
        )

        with self.assertRaises(HTTPException) as ctx:
            self.api.get_operations_user_brevo_sync("uid-1", db_session=self.session)
        self.assertEqual(ctx.exception.status_code, 500)
        mock_state.assert_not_called()


if __name__ == "__main__":
    unittest.main()
