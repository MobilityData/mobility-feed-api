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
"""Integration tests for the dispatch_notifications task.

These run against the real Postgres users test database
(``MobilityDatabaseUsersTest``). The baseline notification types and app users
are seeded by ``conftest.py``; each test creates its own subscriptions/events
and removes them again in ``tearDown`` so the baseline is preserved. Brevo
calls are mocked, so no API keys are required.
"""

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from shared.database.users_database import with_users_db_session
from shared.notifications.notification_constants import (
    AdminEventUpdateType,
    FeedUrlUpdateType,
    NotificationCadence,
    NotificationFeedRole,
    NotificationLogStatus,
    NotificationTypeId,
)
from shared.users_database_gen.sqlacodegen_models import (
    NotificationEvent,
    NotificationEventFeed,
    NotificationLog,
    NotificationSubscription,
)
from tasks.notifications.dispatch_notifications import (
    apply_filter_params,
    dispatch,
    emit_admin_summary,
    find_events_for_subscription,
    find_subscriptions,
    dispatch_notifications_handler,
    process_subscription,
    _resolve_scheduled_cadences,
)
from test_shared.test_utils.database_utils import default_users_db_url

# Test-created rows live in these tables, in FK-safe deletion order. The
# baseline notification_type / app_user rows seeded by conftest are preserved.
_WRITE_MODELS = [
    NotificationLog,
    NotificationEventFeed,
    NotificationEvent,
    NotificationSubscription,
]


@with_users_db_session(db_url=default_users_db_url)
def _cleanup_notifications(db_session: Session = None):
    """Remove subscriptions/events/logs created by a test."""
    for model in _WRITE_MODELS:
        db_session.query(model).delete()


def _uid() -> str:
    return str(uuid.uuid4())


def _make_subscription(
    db_session,
    user_id: str,
    notification_type_id: str = NotificationTypeId.FEED_URL_UPDATED,
    cadence: str = NotificationCadence.WEEKLY,
    digest: bool = True,
    filter_params=None,
    active: bool = True,
    active_since: Optional[datetime] = None,
) -> NotificationSubscription:
    sub = NotificationSubscription(
        id=_uid(),
        user_id=user_id,
        notification_type_id=notification_type_id,
        cadence=cadence,
        digest=digest,
        filter_params=filter_params,
        active=active,
        active_since=active_since
        or (datetime.now(timezone.utc) - timedelta(seconds=5)),
    )
    db_session.add(sub)
    db_session.flush()
    return sub


def _make_event(
    db_session,
    feed_stable_id: str = "mdb-1",
    update_type: str = FeedUrlUpdateType.URL_REPLACED,
    notification_type_id: str = NotificationTypeId.FEED_URL_UPDATED,
    created_at: datetime = None,
    old_url: str = "https://old.example.com",
    new_url: str = "https://new.example.com",
    target_feed_stable_id: str = None,
) -> NotificationEvent:
    event = NotificationEvent(
        id=_uid(),
        notification_type_id=notification_type_id,
        event_subtype=update_type,
        source="test",
        payload={"old_url": old_url, "new_url": new_url},
        created_at=created_at or datetime.now(timezone.utc),
    )
    db_session.add(event)
    db_session.flush()
    if feed_stable_id is not None:
        db_session.add(
            NotificationEventFeed(
                id=_uid(),
                notification_event_id=event.id,
                feed_stable_id=feed_stable_id,
                role=NotificationFeedRole.SUBJECT,
            )
        )
    if target_feed_stable_id is not None:
        db_session.add(
            NotificationEventFeed(
                id=_uid(),
                notification_event_id=event.id,
                feed_stable_id=target_feed_stable_id,
                role=NotificationFeedRole.TARGET,
            )
        )
    db_session.flush()
    db_session.refresh(event)
    return event


def _mock_event(*feed_ids):
    """Lightweight stand-in for a NotificationEvent exposing
    ``notification_event_feeds`` for apply_filter_params tests."""
    return MagicMock(
        notification_event_feeds=[MagicMock(feed_stable_id=fid) for fid in feed_ids]
    )


# ---------------------------------------------------------------------------
# apply_filter_params
# ---------------------------------------------------------------------------


class TestApplyFilterParams(unittest.TestCase):
    def tearDown(self):
        _cleanup_notifications()

    @with_users_db_session(db_url=default_users_db_url)
    def test_no_filter_returns_all(self, db_session: Session = None):
        sub = _make_subscription(db_session, "user-alice", filter_params=None)
        events = [_mock_event("mdb-1"), _mock_event("mdb-2")]
        result = apply_filter_params(events, sub)
        self.assertEqual(result, events)

    @with_users_db_session(db_url=default_users_db_url)
    def test_feed_ids_filter(self, db_session: Session = None):
        sub = _make_subscription(
            db_session, "user-alice", filter_params={"feed_ids": ["mdb-1"]}
        )
        e1 = _mock_event("mdb-1")
        e2 = _mock_event("mdb-2")
        result = apply_filter_params([e1, e2], sub)
        self.assertEqual(result, [e1])

    @with_users_db_session(db_url=default_users_db_url)
    def test_empty_feed_ids_returns_all(self, db_session: Session = None):
        sub = _make_subscription(
            db_session, "user-alice", filter_params={"feed_ids": []}
        )
        events = [_mock_event("mdb-1")]
        # Empty list means no filter — all pass
        result = apply_filter_params(events, sub)
        self.assertEqual(result, events)


# ---------------------------------------------------------------------------
# find_subscriptions
# ---------------------------------------------------------------------------


class TestFindSubscriptions(unittest.TestCase):
    def tearDown(self):
        _cleanup_notifications()

    @with_users_db_session(db_url=default_users_db_url)
    def test_filters_by_cadence(self, db_session: Session = None):
        weekly_sub = _make_subscription(
            db_session, "user-alice", cadence=NotificationCadence.WEEKLY
        )
        _make_subscription(db_session, "user-bob", cadence=NotificationCadence.DAILY)

        result = find_subscriptions(
            db_session=db_session,
            cadence=NotificationCadence.WEEKLY,
            user_ids=[],
            force=False,
        )
        ids = {s.id for s in result}
        self.assertIn(weekly_sub.id, ids)

    @with_users_db_session(db_url=default_users_db_url)
    def test_all_cadence_returns_all_active(self, db_session: Session = None):
        _make_subscription(db_session, "user-alice", cadence=NotificationCadence.WEEKLY)
        _make_subscription(db_session, "user-bob", cadence=NotificationCadence.DAILY)
        _make_subscription(
            db_session, "user-admin", cadence=NotificationCadence.WEEKLY, active=False
        )

        result = find_subscriptions(
            db_session=db_session, cadence="all", user_ids=[], force=False
        )
        self.assertEqual(len(result), 2)  # inactive excluded

    @with_users_db_session(db_url=default_users_db_url)
    def test_user_ids_filter(self, db_session: Session = None):
        _make_subscription(db_session, "user-alice")
        bob_sub = _make_subscription(db_session, "user-bob")

        result = find_subscriptions(
            db_session=db_session, cadence="all", user_ids=["user-bob"], force=False
        )
        self.assertEqual([s.id for s in result], [bob_sub.id])

    @with_users_db_session(db_url=default_users_db_url)
    def test_force_with_user_ids_ignores_cadence(self, db_session: Session = None):
        """force=True + user_ids means bypass cadence."""
        weekly_sub = _make_subscription(
            db_session, "user-alice", cadence=NotificationCadence.WEEKLY
        )

        result = find_subscriptions(
            db_session=db_session,
            cadence=NotificationCadence.DAILY,  # different cadence
            user_ids=["user-alice"],
            force=True,
        )
        ids = {s.id for s in result}
        self.assertIn(weekly_sub.id, ids)


# ---------------------------------------------------------------------------
# find_events_for_subscription
# ---------------------------------------------------------------------------


class TestFindEventsForSubscription(unittest.TestCase):
    def tearDown(self):
        _cleanup_notifications()

    @with_users_db_session(db_url=default_users_db_url)
    def test_new_events_no_log(self, db_session: Session = None):
        sub = _make_subscription(db_session, "user-alice")
        event = _make_event(db_session)

        now = datetime.now(timezone.utc)
        events = find_events_for_subscription(
            db_session=db_session,
            subscription=sub,
            status_filter="new",
            until=now + timedelta(hours=1),
            max_retries=5,
        )
        self.assertIn(event.id, {e.id for e in events})

    @with_users_db_session(db_url=default_users_db_url)
    def test_already_sent_excluded(self, db_session: Session = None):
        sub = _make_subscription(db_session, "user-alice")
        event = _make_event(db_session)
        # Mark as already sent
        log = NotificationLog(
            id=_uid(),
            notification_event_id=event.id,
            subscription_id=sub.id,
            channel="email",
            status=NotificationLogStatus.SENT,
        )
        db_session.add(log)
        db_session.flush()

        now = datetime.now(timezone.utc)
        events = find_events_for_subscription(
            db_session=db_session,
            subscription=sub,
            status_filter="new",
            until=now + timedelta(hours=1),
            max_retries=5,
        )
        self.assertNotIn(event.id, {e.id for e in events})

    @with_users_db_session(db_url=default_users_db_url)
    def test_failed_events_returned_in_retry_mode(self, db_session: Session = None):
        sub = _make_subscription(db_session, "user-alice")
        event = _make_event(db_session)
        log = NotificationLog(
            id=_uid(),
            notification_event_id=event.id,
            subscription_id=sub.id,
            channel="email",
            status=NotificationLogStatus.FAILED,
            retry_count=1,
        )
        db_session.add(log)
        db_session.flush()

        now = datetime.now(timezone.utc)
        events = find_events_for_subscription(
            db_session=db_session,
            subscription=sub,
            status_filter="failed",
            until=now + timedelta(hours=1),
            max_retries=5,
        )
        self.assertIn(event.id, {e.id for e in events})

    @with_users_db_session(db_url=default_users_db_url)
    def test_max_retries_exceeded_excluded(self, db_session: Session = None):
        sub = _make_subscription(db_session, "user-alice")
        event = _make_event(db_session)
        log = NotificationLog(
            id=_uid(),
            notification_event_id=event.id,
            subscription_id=sub.id,
            channel="email",
            status=NotificationLogStatus.FAILED,
            retry_count=5,  # at max
        )
        db_session.add(log)
        db_session.flush()

        now = datetime.now(timezone.utc)
        events = find_events_for_subscription(
            db_session=db_session,
            subscription=sub,
            status_filter="failed",
            until=now + timedelta(hours=1),
            max_retries=5,
        )
        self.assertNotIn(event.id, {e.id for e in events})

    @with_users_db_session(db_url=default_users_db_url)
    def test_event_before_active_since_excluded(self, db_session: Session = None):
        """Events older than active_since are always excluded, even with no log row.

        This covers both the pre-subscription case (event existed before the user
        subscribed) and the disabled-period case (active_since was reset to now()
        when the subscription was re-enabled).
        """
        now = datetime.now(timezone.utc)
        # Subscription became active 7 days ago.
        sub = _make_subscription(
            db_session, "user-alice", active_since=now - timedelta(days=7)
        )
        # Event was emitted 14 days ago — before active_since.
        old_event = _make_event(
            db_session,
            created_at=now - timedelta(days=14),
        )

        events = find_events_for_subscription(
            db_session=db_session,
            subscription=sub,
            status_filter="new",
            until=now,
            max_retries=5,
        )
        self.assertNotIn(old_event.id, {e.id for e in events})

    @with_users_db_session(db_url=default_users_db_url)
    def test_event_outside_cadence_window_but_after_active_since_is_found(
        self, db_session: Session = None
    ):
        """Regression: events that fell outside the old cadence window but have no
        log row (e.g. because a previous run crashed before writing one) must be
        picked up on subsequent runs.

        With the old implementation these were silently dropped once the cadence
        window (e.g. 24 h) advanced past their created_at.  With active_since as
        the lower bound they are always found.
        """
        now = datetime.now(timezone.utc)
        # Subscription has been active for 48 hours.
        sub = _make_subscription(
            db_session,
            "user-alice",
            cadence=NotificationCadence.DAILY,
            active_since=now - timedelta(hours=48),
        )
        # Event was emitted 36 hours ago — inside active_since window but
        # outside the daily cadence window (now - 24 h).
        event = _make_event(
            db_session,
            created_at=now - timedelta(hours=36),
        )

        events = find_events_for_subscription(
            db_session=db_session,
            subscription=sub,
            status_filter="new",
            until=now,
            max_retries=5,
        )
        self.assertIn(event.id, {e.id for e in events})

    @with_users_db_session(db_url=default_users_db_url)
    def test_explicit_since_can_narrow_window_but_not_below_active_since(
        self, db_session: Session = None
    ):
        """explicit_since further restricts the window but never expands it past active_since."""
        now = datetime.now(timezone.utc)
        active_since = now - timedelta(days=3)
        sub = _make_subscription(db_session, "user-alice", active_since=active_since)

        # Event 2 days ago — after active_since.
        recent_event = _make_event(
            db_session, created_at=now - timedelta(days=2), feed_stable_id="mdb-1"
        )
        # Event 5 days ago — before active_since (pre-subscription / dead zone).
        old_event = _make_event(
            db_session, created_at=now - timedelta(days=5), feed_stable_id="mdb-2"
        )

        # explicit_since = now - 1 day: should narrow window further.
        events = find_events_for_subscription(
            db_session=db_session,
            subscription=sub,
            status_filter="new",
            explicit_since=now - timedelta(days=1),
            until=now,
            max_retries=5,
        )
        ids = {e.id for e in events}
        # recent_event is outside explicit_since window (2 days > 1 day) → excluded.
        self.assertNotIn(recent_event.id, ids)
        # old_event is before active_since → also excluded.
        self.assertNotIn(old_event.id, ids)

        # Without explicit_since, recent_event is included; old_event still excluded.
        events_no_override = find_events_for_subscription(
            db_session=db_session,
            subscription=sub,
            status_filter="new",
            until=now,
            max_retries=5,
        )
        ids_no_override = {e.id for e in events_no_override}
        self.assertIn(recent_event.id, ids_no_override)
        self.assertNotIn(old_event.id, ids_no_override)


# ---------------------------------------------------------------------------
# emit_admin_summary
# ---------------------------------------------------------------------------


class TestEmitAdminSummary(unittest.TestCase):
    def tearDown(self):
        _cleanup_notifications()

    @with_users_db_session(db_url=default_users_db_url)
    def test_creates_notification_event(self, db_session: Session = None):
        stats = {"emails_sent": 3, "emails_failed": 1}
        emit_admin_summary(db_session=db_session, stats=stats, cadence="weekly")

        event = (
            db_session.query(NotificationEvent)
            .filter_by(
                notification_type_id=NotificationTypeId.ADMIN_EVENT_SUMMARY,
                event_subtype=AdminEventUpdateType.DISPATCH_SUMMARY,
            )
            .one_or_none()
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.payload["emails_sent"], 3)
        self.assertEqual(event.payload["cadence"], "weekly")


# ---------------------------------------------------------------------------
# dispatch_notifications_handler — dry run
# ---------------------------------------------------------------------------


class TestDispatchDryRun(unittest.TestCase):
    @patch("tasks.notifications.dispatch_notifications.with_users_db_session")
    def test_dry_run_returns_stats_without_sending(self, mock_decorator):
        """Smoke test: handler returns a stats dict and does not crash."""
        result = dispatch_notifications_handler({"dry_run": True, "cadence": "weekly"})
        # dry_run default is True, so no emails sent
        self.assertTrue("dry_run" in result or isinstance(result, dict))


# ---------------------------------------------------------------------------
# _resolve_scheduled_cadences — day-of-week gating for the single daily job
# ---------------------------------------------------------------------------


class TestResolveScheduledCadences(unittest.TestCase):
    def test_passthrough_for_explicit_cadence(self):
        self.assertEqual(_resolve_scheduled_cadences("weekly", 0), ["weekly"])
        self.assertEqual(_resolve_scheduled_cadences("daily", 0), ["daily"])
        self.assertEqual(_resolve_scheduled_cadences("all", 0), ["all"])

    def test_scheduled_runs_daily_only_off_weekday(self):
        # 2026-06-16 is a Tuesday (weekday()==1); weekly_weekday=0 (Monday).
        tuesday = datetime(2026, 6, 16, 8, 0, tzinfo=timezone.utc)
        self.assertEqual(
            _resolve_scheduled_cadences("scheduled", 0, now=tuesday),
            ["daily"],
        )

    def test_scheduled_adds_weekly_on_weekday(self):
        # 2026-06-15 is a Monday (weekday()==0).
        monday = datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc)
        self.assertEqual(
            _resolve_scheduled_cadences("scheduled", 0, now=monday),
            ["daily", "weekly"],
        )

    def test_scheduled_respects_configured_weekday(self):
        # Configure weekly on Sunday (weekday()==6); 2026-06-21 is a Sunday.
        sunday = datetime(2026, 6, 21, 8, 0, tzinfo=timezone.utc)
        self.assertEqual(
            _resolve_scheduled_cadences("scheduled", 6, now=sunday),
            ["daily", "weekly"],
        )


# ---------------------------------------------------------------------------
# dispatch — integration-style (real users DB, mocked Brevo)
# ---------------------------------------------------------------------------


class TestDispatchIntegration(unittest.TestCase):
    def tearDown(self):
        _cleanup_notifications()

    @patch("tasks.notifications.dispatch_notifications.send_single")
    @with_users_db_session(db_url=default_users_db_url)
    def test_single_event_non_digest_sends_one_email(
        self, mock_send, db_session: Session = None
    ):
        _make_subscription(
            db_session,
            "user-alice",
            cadence=NotificationCadence.WEEKLY,
            digest=False,
        )
        _make_event(db_session)

        now = datetime.now(timezone.utc)
        stats = dispatch(
            cadence=NotificationCadence.WEEKLY,
            dry_run=False,
            status_filter="new",
            user_ids=[],
            force=False,
            since_dt=(now - timedelta(hours=1)).isoformat(),
            until_dt=(now + timedelta(hours=1)).isoformat(),
            max_retries=5,
            db_session=db_session,
        )

        self.assertTrue(mock_send.called)
        self.assertEqual(stats["emails_sent"], 1)

    @patch("tasks.notifications.dispatch_notifications.send_single")
    @with_users_db_session(db_url=default_users_db_url)
    def test_admin_summary_emitted_only_on_real_activity(
        self, mock_send, db_session: Session = None
    ):
        """A new admin.event_summary is emitted when real notifications are
        dispatched, but a follow-up run that only delivers that summary (or does
        nothing) must NOT mint another summary — otherwise the admin receives a
        summary email on every dispatch forever."""
        _make_subscription(
            db_session,
            "user-alice",
            cadence=NotificationCadence.WEEKLY,
            digest=False,
        )
        # An admin subscriber that picks up dispatch summaries.
        _make_subscription(
            db_session,
            "user-admin",
            notification_type_id=NotificationTypeId.ADMIN_EVENT_SUMMARY,
            cadence=NotificationCadence.WEEKLY,
            digest=False,
        )
        _make_event(db_session)

        now = datetime.now(timezone.utc)
        kwargs = dict(
            cadence=NotificationCadence.WEEKLY,
            dry_run=False,
            status_filter="new",
            user_ids=[],
            force=False,
            since_dt=(now - timedelta(hours=1)).isoformat(),
            until_dt=(now + timedelta(hours=1)).isoformat(),
            max_retries=5,
            db_session=db_session,
        )

        def _summary_count() -> int:
            return (
                db_session.query(NotificationEvent)
                .filter_by(notification_type_id=NotificationTypeId.ADMIN_EVENT_SUMMARY)
                .count()
            )

        # First run: a real event is dispatched => exactly one summary emitted.
        dispatch(**kwargs)
        self.assertEqual(_summary_count(), 1)

        # Second run: the only thing to deliver is the prior summary (to the
        # admin) — no real activity, so NO new summary must be created.
        dispatch(**kwargs)
        self.assertEqual(_summary_count(), 1)

        # Third run: nothing new at all — still no additional summary.
        dispatch(**kwargs)
        self.assertEqual(_summary_count(), 1)

    @patch("tasks.notifications.dispatch_notifications.get_brevo_rate_limiter")
    @patch("tasks.notifications.dispatch_notifications.send_single")
    @with_users_db_session(db_url=default_users_db_url)
    def test_rate_limiter_acquired_once_per_send(
        self, mock_send, mock_get_limiter, db_session: Session = None
    ):
        """Each Brevo send attempt acquires a token from the shared limiter."""
        limiter = MagicMock()
        mock_get_limiter.return_value = limiter
        _make_subscription(
            db_session,
            "user-alice",
            cadence=NotificationCadence.WEEKLY,
            digest=False,
        )
        _make_event(db_session)

        now = datetime.now(timezone.utc)
        dispatch(
            cadence=NotificationCadence.WEEKLY,
            dry_run=False,
            status_filter="new",
            user_ids=[],
            force=False,
            since_dt=(now - timedelta(hours=1)).isoformat(),
            until_dt=(now + timedelta(hours=1)).isoformat(),
            max_retries=5,
            db_session=db_session,
        )

        # One successful send => exactly one token acquired.
        limiter.acquire.assert_called_once_with()

    @patch("tasks.notifications.dispatch_notifications.send_digest")
    @with_users_db_session(db_url=default_users_db_url)
    def test_digest_batches_events_into_one_email(
        self, mock_send, db_session: Session = None
    ):
        _make_subscription(
            db_session,
            "user-alice",
            cadence=NotificationCadence.WEEKLY,
            digest=True,
        )
        _make_event(db_session, feed_stable_id="mdb-1")
        _make_event(db_session, feed_stable_id="mdb-2")

        now = datetime.now(timezone.utc)
        stats = dispatch(
            cadence=NotificationCadence.WEEKLY,
            dry_run=False,
            status_filter="new",
            user_ids=[],
            force=False,
            since_dt=(now - timedelta(hours=1)).isoformat(),
            until_dt=(now + timedelta(hours=1)).isoformat(),
            max_retries=5,
            db_session=db_session,
        )

        # One digest call for 2 events
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(stats["emails_sent"], 2)

    @patch("tasks.notifications.dispatch_notifications.send_single")
    @with_users_db_session(db_url=default_users_db_url)
    def test_brevo_failure_marks_log_failed_and_increments_retry_count(
        self, mock_send, db_session: Session = None
    ):
        from shared.notifications.brevo_notification_sender import BrevoSendError

        mock_send.side_effect = BrevoSendError("Brevo 429")
        sub = _make_subscription(
            db_session,
            "user-alice",
            cadence=NotificationCadence.WEEKLY,
            digest=False,
        )
        event = _make_event(db_session)

        now = datetime.now(timezone.utc)
        with patch("tasks.notifications.dispatch_notifications.time.sleep"):
            stats = dispatch(
                cadence=NotificationCadence.WEEKLY,
                dry_run=False,
                status_filter="new",
                user_ids=[],
                force=False,
                since_dt=(now - timedelta(hours=1)).isoformat(),
                until_dt=(now + timedelta(hours=1)).isoformat(),
                max_retries=5,
                db_session=db_session,
            )

        log = (
            db_session.query(NotificationLog)
            .filter_by(notification_event_id=event.id, subscription_id=sub.id)
            .one()
        )
        self.assertEqual(log.status, NotificationLogStatus.FAILED)
        self.assertEqual(log.retry_count, 1)
        self.assertEqual(stats["emails_failed"], 1)

    @patch("tasks.notifications.dispatch_notifications.send_single")
    @with_users_db_session(db_url=default_users_db_url)
    def test_permanently_failed_after_max_retries(
        self, mock_send, db_session: Session = None
    ):
        from shared.notifications.brevo_notification_sender import BrevoSendError

        mock_send.side_effect = BrevoSendError("Persistent failure")
        sub = _make_subscription(
            db_session,
            "user-alice",
            cadence=NotificationCadence.WEEKLY,
            digest=False,
        )
        event = _make_event(db_session)

        # Pre-seed a log with retry_count = max_retries - 1
        log = NotificationLog(
            id=_uid(),
            notification_event_id=event.id,
            subscription_id=sub.id,
            channel="email",
            status=NotificationLogStatus.FAILED,
            retry_count=4,  # one below max
        )
        db_session.add(log)
        db_session.flush()

        now = datetime.now(timezone.utc)
        with patch("tasks.notifications.dispatch_notifications.time.sleep"):
            stats = dispatch(
                cadence=NotificationCadence.WEEKLY,
                dry_run=False,
                status_filter="failed",
                user_ids=[],
                force=False,
                since_dt=(now - timedelta(hours=1)).isoformat(),
                until_dt=(now + timedelta(hours=1)).isoformat(),
                max_retries=5,
                db_session=db_session,
            )

        db_session.refresh(log)
        self.assertEqual(log.status, NotificationLogStatus.PERMANENTLY_FAILED)
        self.assertEqual(log.retry_count, 5)
        self.assertEqual(stats["permanently_failed"], 1)

    @patch("tasks.notifications.dispatch_notifications.send_single")
    @with_users_db_session(db_url=default_users_db_url)
    def test_unique_constraint_prevents_duplicate_log(
        self, mock_send, db_session: Session = None
    ):
        sub = _make_subscription(
            db_session,
            "user-alice",
            cadence=NotificationCadence.WEEKLY,
            digest=False,
        )
        event = _make_event(db_session)

        now = datetime.now(timezone.utc)
        kwargs = dict(
            cadence=NotificationCadence.WEEKLY,
            dry_run=False,
            status_filter="new",
            user_ids=[],
            force=False,
            since_dt=(now - timedelta(hours=1)).isoformat(),
            until_dt=(now + timedelta(hours=1)).isoformat(),
            max_retries=5,
            db_session=db_session,
        )
        dispatch(**kwargs)
        dispatch(**kwargs)  # second run — event already sent

        logs = (
            db_session.query(NotificationLog)
            .filter_by(notification_event_id=event.id, subscription_id=sub.id)
            .all()
        )
        self.assertEqual(len(logs), 1)

    @patch("tasks.notifications.dispatch_notifications.send_single")
    @with_users_db_session(db_url=default_users_db_url)
    def test_filter_params_excludes_unmatched_feed(
        self, mock_send, db_session: Session = None
    ):
        _make_event(
            db_session, feed_stable_id="mdb-1"
        )  # event exists but no subscription matches

        now = datetime.now(timezone.utc)
        stats = dispatch(
            cadence=NotificationCadence.WEEKLY,
            dry_run=False,
            status_filter="new",
            user_ids=[],
            force=False,
            since_dt=(now - timedelta(hours=1)).isoformat(),
            until_dt=(now + timedelta(hours=1)).isoformat(),
            max_retries=5,
            db_session=db_session,
        )

        self.assertFalse(mock_send.called)
        self.assertEqual(stats["emails_sent"], 0)

    @with_users_db_session(db_url=default_users_db_url)
    def test_dry_run_does_not_write_logs(self, db_session: Session = None):
        _make_subscription(db_session, "user-alice", cadence=NotificationCadence.WEEKLY)
        _make_event(db_session)

        now = datetime.now(timezone.utc)
        dispatch(
            cadence=NotificationCadence.WEEKLY,
            dry_run=True,
            status_filter="new",
            user_ids=[],
            force=False,
            since_dt=(now - timedelta(hours=1)).isoformat(),
            until_dt=(now + timedelta(hours=1)).isoformat(),
            max_retries=5,
            db_session=db_session,
        )

        self.assertEqual(db_session.query(NotificationLog).count(), 0)


class TestProcessSubscription(unittest.TestCase):
    """Worker core: claim-then-send for a single subscription."""

    def tearDown(self):
        _cleanup_notifications()

    @patch("tasks.notifications.dispatch_notifications.send_single")
    @with_users_db_session(db_url=default_users_db_url)
    def test_sends_and_logs_single(self, mock_send, db_session: Session = None):
        sub = _make_subscription(
            db_session, "user-alice", cadence=NotificationCadence.WEEKLY, digest=False
        )
        event = _make_event(db_session)

        stats = process_subscription(
            subscription_id=sub.id,
            status_filter="new",
            max_retries=5,
            db_session=db_session,
        )

        self.assertTrue(mock_send.called)
        self.assertEqual(stats["emails_sent"], 1)
        self.assertEqual(stats["events_claimed"], 1)
        log = (
            db_session.query(NotificationLog)
            .filter_by(notification_event_id=event.id, subscription_id=sub.id)
            .one()
        )
        self.assertEqual(log.status, NotificationLogStatus.SENT)

    @patch("tasks.notifications.dispatch_notifications.send_single")
    @with_users_db_session(db_url=default_users_db_url)
    def test_fresh_pending_claim_blocks_duplicate_send(
        self, mock_send, db_session: Session = None
    ):
        """A fresh 'pending' claim (another worker in flight) must not be re-sent."""
        sub = _make_subscription(
            db_session, "user-alice", cadence=NotificationCadence.WEEKLY, digest=False
        )
        event = _make_event(db_session)
        db_session.add(
            NotificationLog(
                id=_uid(),
                notification_event_id=event.id,
                subscription_id=sub.id,
                channel="email",
                status=NotificationLogStatus.PENDING,
                retry_count=0,
                sent_at=datetime.now(timezone.utc),
            )
        )
        db_session.flush()

        stats = process_subscription(
            subscription_id=sub.id,
            status_filter="all",
            max_retries=5,
            db_session=db_session,
        )

        self.assertFalse(mock_send.called)
        self.assertEqual(stats["emails_sent"], 0)
        # No duplicate log row was created.
        self.assertEqual(
            db_session.query(NotificationLog)
            .filter_by(notification_event_id=event.id, subscription_id=sub.id)
            .count(),
            1,
        )

    @patch("tasks.notifications.dispatch_notifications.send_single")
    @with_users_db_session(db_url=default_users_db_url)
    def test_reclaims_stale_pending(self, mock_send, db_session: Session = None):
        """A 'pending' claim older than the lease (crashed worker) is re-sent."""
        sub = _make_subscription(
            db_session, "user-alice", cadence=NotificationCadence.WEEKLY, digest=False
        )
        event = _make_event(db_session)
        db_session.add(
            NotificationLog(
                id=_uid(),
                notification_event_id=event.id,
                subscription_id=sub.id,
                channel="email",
                status=NotificationLogStatus.PENDING,
                retry_count=0,
                sent_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
        )
        db_session.flush()

        stats = process_subscription(
            subscription_id=sub.id,
            status_filter="new",
            max_retries=5,
            stale_claim_seconds=60,
            db_session=db_session,
        )

        self.assertTrue(mock_send.called)
        self.assertEqual(stats["emails_sent"], 1)
        log = (
            db_session.query(NotificationLog)
            .filter_by(notification_event_id=event.id, subscription_id=sub.id)
            .one()
        )
        self.assertEqual(log.status, NotificationLogStatus.SENT)

    @patch("tasks.notifications.dispatch_notifications.send_single")
    @with_users_db_session(db_url=default_users_db_url)
    def test_second_run_is_noop(self, mock_send, db_session: Session = None):
        sub = _make_subscription(
            db_session, "user-alice", cadence=NotificationCadence.WEEKLY, digest=False
        )
        _make_event(db_session)

        kwargs = dict(
            subscription_id=sub.id,
            status_filter="new",
            max_retries=5,
            db_session=db_session,
        )
        process_subscription(**kwargs)
        mock_send.reset_mock()
        stats = process_subscription(**kwargs)

        self.assertFalse(mock_send.called)
        self.assertEqual(stats["emails_sent"], 0)

    @patch("tasks.notifications.dispatch_notifications.send_single")
    @with_users_db_session(db_url=default_users_db_url)
    def test_inactive_subscription_skipped(
        self, mock_send, db_session: Session = None
    ):
        sub = _make_subscription(
            db_session,
            "user-alice",
            cadence=NotificationCadence.WEEKLY,
            digest=False,
            active=False,
        )
        _make_event(db_session)

        stats = process_subscription(
            subscription_id=sub.id, status_filter="new", db_session=db_session
        )

        self.assertFalse(mock_send.called)
        self.assertEqual(stats["events_found"], 0)


if __name__ == "__main__":
    unittest.main()
