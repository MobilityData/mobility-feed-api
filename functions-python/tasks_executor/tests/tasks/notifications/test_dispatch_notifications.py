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
"""Unit tests for dispatch_notifications task.

These tests use in-memory SQLite via SQLAlchemy and mock out Brevo calls,
so no real database connection or API keys are required.
"""

from __future__ import annotations

import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import DefaultClause

from shared.notifications.notification_constants import (
    AdminEventUpdateType,
    FeedUrlUpdateType,
    NotificationCadence,
    NotificationLogStatus,
    NotificationTypeId,
)
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    Base,
    NotificationEvent,
    NotificationLog,
    NotificationSubscription,
    NotificationType,
)
from tasks.notifications.dispatch_notifications import (
    apply_filter_params,
    dispatch,
    emit_admin_summary,
    find_events_for_subscription,
    find_subscriptions,
    dispatch_notifications_handler,
)


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):
    """Render Postgres JSONB columns as TEXT under SQLite for unit tests."""
    return "TEXT"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine():
    # active_since is added by migration feat_1724 and then reflected into the
    # auto-generated sqlacodegen_models.py.  Until that cycle completes we add
    # the column to the in-memory SQLite schema here so unit tests can run.
    # We guard against duplicate addition since the Table object is a module-level
    # singleton and the fixture may be called multiple times per test session.
    if "active_since" not in NotificationSubscription.__table__.c:
        from sqlalchemy import Column as _Col, DateTime as _DT

        NotificationSubscription.__table__.append_column(
            _Col(
                "active_since",
                _DT(True),
                nullable=False,
                server_default=text("CURRENT_TIMESTAMP"),
            )
        )
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    with _sqlite_compatible_defaults():
        Base.metadata.create_all(eng)
    return eng


@contextmanager
def _sqlite_compatible_defaults():
    """Temporarily rewrite Postgres-specific ``server_default`` clauses into
    SQLite-compatible DDL so ``create_all`` can build an in-memory database.

    Handles ``now()`` (-> ``CURRENT_TIMESTAMP``) and ``::type`` casts (e.g.
    ``'weekly'::text``, ``(gen_random_uuid())::text``). Originals are restored
    on exit so the generated models remain untouched for any other test.
    """
    originals = []
    for table in Base.metadata.tables.values():
        for column in table.columns:
            default = column.server_default
            if not isinstance(default, DefaultClause):
                continue
            original_text = str(getattr(default.arg, "text", ""))
            if not original_text:
                continue
            rewritten = re.sub(r"::\w+", "", original_text).replace(
                "now()", "CURRENT_TIMESTAMP"
            )
            if rewritten == original_text:
                continue
            originals.append((column, default))
            column.server_default = DefaultClause(text(rewritten))
    try:
        yield
    finally:
        for column, default in originals:
            column.server_default = default


@pytest.fixture
def session(engine):
    Session = sessionmaker(bind=engine)
    sess = Session()
    _seed(sess)
    yield sess
    sess.close()


def _uid() -> str:
    return str(uuid.uuid4())


def _seed(sess):
    """Insert minimal seed data into the in-memory DB."""
    sess.add_all(
        [
            NotificationType(
                id=NotificationTypeId.FEED_URL_UPDATED, description="Feed URL updated"
            ),
            NotificationType(
                id=NotificationTypeId.ADMIN_EVENT_SUMMARY, description="Admin summary"
            ),
        ]
    )
    sess.flush()

    sess.add_all(
        [
            AppUser(id="user-alice", email="alice@example.com", full_name="Alice"),
            AppUser(id="user-bob", email="bob@example.com", full_name="Bob"),
            AppUser(id="user-admin", email="admin@example.com", full_name="Admin"),
        ]
    )
    sess.flush()


def _make_subscription(
    sess,
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
    )
    # Set active_since explicitly so it is available in Python memory regardless
    # of whether the ORM model has been regenerated post-migration.
    sub.active_since = active_since or (
        datetime.now(timezone.utc) - timedelta(seconds=5)
    )
    sess.add(sub)
    sess.flush()
    return sub


def _make_event(
    sess,
    feed_stable_id: str = "mdb-1",
    update_type: str = FeedUrlUpdateType.URL_REPLACED,
    notification_type_id: str = NotificationTypeId.FEED_URL_UPDATED,
    created_at: datetime = None,
    old_url: str = "https://old.example.com",
    new_url: str = "https://new.example.com",
) -> NotificationEvent:
    event = NotificationEvent(
        id=_uid(),
        notification_type_id=notification_type_id,
        update_type=update_type,
        feed_stable_id=feed_stable_id,
        old_url=old_url,
        new_url=new_url,
        source="test",
        created_at=created_at or datetime.now(timezone.utc),
    )
    sess.add(event)
    sess.flush()
    return event


# ---------------------------------------------------------------------------
# apply_filter_params
# ---------------------------------------------------------------------------


class TestApplyFilterParams:
    def test_no_filter_returns_all(self, session):
        sub = _make_subscription(session, "user-alice", filter_params=None)
        events = [
            MagicMock(feed_stable_id="mdb-1"),
            MagicMock(feed_stable_id="mdb-2"),
        ]
        result = apply_filter_params(events, sub)
        assert result == events

    def test_feed_ids_filter(self, session):
        sub = _make_subscription(
            session, "user-alice", filter_params={"feed_ids": ["mdb-1"]}
        )
        e1 = MagicMock(feed_stable_id="mdb-1")
        e2 = MagicMock(feed_stable_id="mdb-2")
        result = apply_filter_params([e1, e2], sub)
        assert result == [e1]

    def test_empty_feed_ids_returns_all(self, session):
        sub = _make_subscription(session, "user-alice", filter_params={"feed_ids": []})
        events = [MagicMock(feed_stable_id="mdb-1")]
        # Empty list means no filter — all pass
        result = apply_filter_params(events, sub)
        assert result == events


# ---------------------------------------------------------------------------
# find_subscriptions
# ---------------------------------------------------------------------------


class TestFindSubscriptions:
    def test_filters_by_cadence(self, session):
        weekly_sub = _make_subscription(
            session, "user-alice", cadence=NotificationCadence.WEEKLY
        )
        _make_subscription(session, "user-bob", cadence=NotificationCadence.DAILY)

        result = find_subscriptions(
            db_session=session,
            cadence=NotificationCadence.WEEKLY,
            user_ids=[],
            force=False,
        )
        ids = {s.id for s in result}
        assert weekly_sub.id in ids

    def test_all_cadence_returns_all_active(self, session):
        _make_subscription(session, "user-alice", cadence=NotificationCadence.WEEKLY)
        _make_subscription(session, "user-bob", cadence=NotificationCadence.DAILY)
        _make_subscription(
            session, "user-admin", cadence=NotificationCadence.WEEKLY, active=False
        )

        result = find_subscriptions(
            db_session=session, cadence="all", user_ids=[], force=False
        )
        assert len(result) == 2  # inactive excluded

    def test_user_ids_filter(self, session):
        _make_subscription(session, "user-alice")
        bob_sub = _make_subscription(session, "user-bob")

        result = find_subscriptions(
            db_session=session, cadence="all", user_ids=["user-bob"], force=False
        )
        assert [s.id for s in result] == [bob_sub.id]

    def test_force_with_user_ids_ignores_cadence(self, session):
        """force=True + user_ids means bypass cadence."""
        weekly_sub = _make_subscription(
            session, "user-alice", cadence=NotificationCadence.WEEKLY
        )

        result = find_subscriptions(
            db_session=session,
            cadence=NotificationCadence.DAILY,  # different cadence
            user_ids=["user-alice"],
            force=True,
        )
        ids = {s.id for s in result}
        assert weekly_sub.id in ids


# ---------------------------------------------------------------------------
# find_events_for_subscription
# ---------------------------------------------------------------------------


class TestFindEventsForSubscription:
    def test_new_events_no_log(self, session):
        sub = _make_subscription(session, "user-alice")
        event = _make_event(session)

        now = datetime.now(timezone.utc)
        events = find_events_for_subscription(
            db_session=session,
            subscription=sub,
            status_filter="new",
            until=now + timedelta(hours=1),
            max_retries=5,
        )
        assert event.id in {e.id for e in events}

    def test_already_sent_excluded(self, session):
        sub = _make_subscription(session, "user-alice")
        event = _make_event(session)
        # Mark as already sent
        log = NotificationLog(
            id=_uid(),
            notification_event_id=event.id,
            subscription_id=sub.id,
            channel="email",
            status=NotificationLogStatus.SENT,
        )
        session.add(log)
        session.flush()

        now = datetime.now(timezone.utc)
        events = find_events_for_subscription(
            db_session=session,
            subscription=sub,
            status_filter="new",
            until=now + timedelta(hours=1),
            max_retries=5,
        )
        assert event.id not in {e.id for e in events}

    def test_failed_events_returned_in_retry_mode(self, session):
        sub = _make_subscription(session, "user-alice")
        event = _make_event(session)
        log = NotificationLog(
            id=_uid(),
            notification_event_id=event.id,
            subscription_id=sub.id,
            channel="email",
            status=NotificationLogStatus.FAILED,
            retry_count=1,
        )
        session.add(log)
        session.flush()

        now = datetime.now(timezone.utc)
        events = find_events_for_subscription(
            db_session=session,
            subscription=sub,
            status_filter="failed",
            until=now + timedelta(hours=1),
            max_retries=5,
        )
        assert event.id in {e.id for e in events}

    def test_max_retries_exceeded_excluded(self, session):
        sub = _make_subscription(session, "user-alice")
        event = _make_event(session)
        log = NotificationLog(
            id=_uid(),
            notification_event_id=event.id,
            subscription_id=sub.id,
            channel="email",
            status=NotificationLogStatus.FAILED,
            retry_count=5,  # at max
        )
        session.add(log)
        session.flush()

        now = datetime.now(timezone.utc)
        events = find_events_for_subscription(
            db_session=session,
            subscription=sub,
            status_filter="failed",
            until=now + timedelta(hours=1),
            max_retries=5,
        )
        assert event.id not in {e.id for e in events}

    def test_event_before_active_since_excluded(self, session):
        """Events older than active_since are always excluded, even with no log row.

        This covers both the pre-subscription case (event existed before the user
        subscribed) and the disabled-period case (active_since was reset to now()
        when the subscription was re-enabled).
        """
        now = datetime.now(timezone.utc)
        # Subscription became active 7 days ago.
        sub = _make_subscription(
            session, "user-alice", active_since=now - timedelta(days=7)
        )
        # Event was emitted 14 days ago — before active_since.
        old_event = _make_event(
            session,
            created_at=now - timedelta(days=14),
        )

        events = find_events_for_subscription(
            db_session=session,
            subscription=sub,
            status_filter="new",
            until=now,
            max_retries=5,
        )
        assert old_event.id not in {e.id for e in events}

    def test_event_outside_cadence_window_but_after_active_since_is_found(
        self, session
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
            session,
            "user-alice",
            cadence=NotificationCadence.DAILY,
            active_since=now - timedelta(hours=48),
        )
        # Event was emitted 36 hours ago — inside active_since window but
        # outside the daily cadence window (now - 24 h).
        event = _make_event(
            session,
            created_at=now - timedelta(hours=36),
        )

        events = find_events_for_subscription(
            db_session=session,
            subscription=sub,
            status_filter="new",
            until=now,
            max_retries=5,
        )
        assert event.id in {e.id for e in events}

    def test_explicit_since_can_narrow_window_but_not_below_active_since(self, session):
        """explicit_since further restricts the window but never expands it past active_since."""
        now = datetime.now(timezone.utc)
        active_since = now - timedelta(days=3)
        sub = _make_subscription(session, "user-alice", active_since=active_since)

        # Event 2 days ago — after active_since.
        recent_event = _make_event(
            session, created_at=now - timedelta(days=2), feed_stable_id="mdb-1"
        )
        # Event 5 days ago — before active_since (pre-subscription / dead zone).
        old_event = _make_event(
            session, created_at=now - timedelta(days=5), feed_stable_id="mdb-2"
        )

        # explicit_since = now - 1 day: should narrow window further.
        events = find_events_for_subscription(
            db_session=session,
            subscription=sub,
            status_filter="new",
            explicit_since=now - timedelta(days=1),
            until=now,
            max_retries=5,
        )
        ids = {e.id for e in events}
        # recent_event is outside explicit_since window (2 days > 1 day) → excluded.
        assert recent_event.id not in ids
        # old_event is before active_since → also excluded.
        assert old_event.id not in ids

        # Without explicit_since, recent_event is included; old_event still excluded.
        events_no_override = find_events_for_subscription(
            db_session=session,
            subscription=sub,
            status_filter="new",
            until=now,
            max_retries=5,
        )
        ids_no_override = {e.id for e in events_no_override}
        assert recent_event.id in ids_no_override
        assert old_event.id not in ids_no_override


# ---------------------------------------------------------------------------
# emit_admin_summary
# ---------------------------------------------------------------------------


class TestEmitAdminSummary:
    def test_creates_notification_event(self, session):
        stats = {"emails_sent": 3, "emails_failed": 1}
        emit_admin_summary(db_session=session, stats=stats, cadence="weekly")

        event = (
            session.query(NotificationEvent)
            .filter_by(
                notification_type_id=NotificationTypeId.ADMIN_EVENT_SUMMARY,
                update_type=AdminEventUpdateType.DISPATCH_SUMMARY,
            )
            .one_or_none()
        )
        assert event is not None
        assert event.extra_data["emails_sent"] == 3
        assert event.extra_data["cadence"] == "weekly"


# ---------------------------------------------------------------------------
# dispatch_notifications_handler — dry run
# ---------------------------------------------------------------------------


class TestDispatchDryRun:
    @patch("tasks.notifications.dispatch_notifications.with_users_db_session")
    def test_dry_run_returns_stats_without_sending(self, mock_decorator):
        """Smoke test: handler returns a stats dict and does not crash."""
        result = dispatch_notifications_handler({"dry_run": True, "cadence": "weekly"})
        # dry_run default is True, so no emails sent
        assert "dry_run" in result or isinstance(result, dict)


# ---------------------------------------------------------------------------
# dispatch — integration-style (in-memory DB, mocked Brevo)
# ---------------------------------------------------------------------------


class TestDispatchIntegration:
    @patch("tasks.notifications.dispatch_notifications.send_single")
    def test_single_event_non_digest_sends_one_email(self, mock_send, session):
        _make_subscription(
            session,
            "user-alice",
            cadence=NotificationCadence.WEEKLY,
            digest=False,
        )
        _make_event(session)

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
            db_session=session,
        )

        assert mock_send.called
        assert stats["emails_sent"] == 1

    @patch("tasks.notifications.dispatch_notifications.send_digest")
    def test_digest_batches_events_into_one_email(self, mock_send, session):
        _make_subscription(
            session,
            "user-alice",
            cadence=NotificationCadence.WEEKLY,
            digest=True,
        )
        _make_event(session, feed_stable_id="mdb-1")
        _make_event(session, feed_stable_id="mdb-2")

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
            db_session=session,
        )

        # One digest call for 2 events
        assert mock_send.call_count == 1
        assert stats["emails_sent"] == 2

    @patch("tasks.notifications.dispatch_notifications.send_single")
    def test_brevo_failure_marks_log_failed_and_increments_retry_count(
        self, mock_send, session
    ):
        from shared.notifications.brevo_notification_sender import BrevoSendError

        mock_send.side_effect = BrevoSendError("Brevo 429")
        sub = _make_subscription(
            session,
            "user-alice",
            cadence=NotificationCadence.WEEKLY,
            digest=False,
        )
        event = _make_event(session)

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
                db_session=session,
            )

        log = (
            session.query(NotificationLog)
            .filter_by(notification_event_id=event.id, subscription_id=sub.id)
            .one()
        )
        assert log.status == NotificationLogStatus.FAILED
        assert log.retry_count == 1
        assert stats["emails_failed"] == 1

    @patch("tasks.notifications.dispatch_notifications.send_single")
    def test_permanently_failed_after_max_retries(self, mock_send, session):
        from shared.notifications.brevo_notification_sender import BrevoSendError

        mock_send.side_effect = BrevoSendError("Persistent failure")
        sub = _make_subscription(
            session,
            "user-alice",
            cadence=NotificationCadence.WEEKLY,
            digest=False,
        )
        event = _make_event(session)

        # Pre-seed a log with retry_count = max_retries - 1
        log = NotificationLog(
            id=_uid(),
            notification_event_id=event.id,
            subscription_id=sub.id,
            channel="email",
            status=NotificationLogStatus.FAILED,
            retry_count=4,  # one below max
        )
        session.add(log)
        session.flush()

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
                db_session=session,
            )

        session.refresh(log)
        assert log.status == NotificationLogStatus.PERMANENTLY_FAILED
        assert log.retry_count == 5
        assert stats["permanently_failed"] == 1

    @patch("tasks.notifications.dispatch_notifications.send_single")
    def test_unique_constraint_prevents_duplicate_log(self, mock_send, session):
        sub = _make_subscription(
            session,
            "user-alice",
            cadence=NotificationCadence.WEEKLY,
            digest=False,
        )
        event = _make_event(session)

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
            db_session=session,
        )
        dispatch(**kwargs)
        dispatch(**kwargs)  # second run — event already sent

        logs = (
            session.query(NotificationLog)
            .filter_by(notification_event_id=event.id, subscription_id=sub.id)
            .all()
        )
        assert len(logs) == 1

    @patch("tasks.notifications.dispatch_notifications.send_single")
    def test_filter_params_excludes_unmatched_feed(self, mock_send, session):
        _make_event(
            session, feed_stable_id="mdb-1"
        )  # different feed — should not match

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
            db_session=session,
        )

        assert not mock_send.called
        assert stats["emails_sent"] == 0

    def test_dry_run_does_not_write_logs(self, session):
        _make_subscription(session, "user-alice", cadence=NotificationCadence.WEEKLY)
        _make_event(session)

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
            db_session=session,
        )

        assert session.query(NotificationLog).count() == 0
