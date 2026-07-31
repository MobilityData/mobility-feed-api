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
"""DB-backed tests for feed-scoped notification subscriptions (issue #1778).

These exercise the full create path (validation, persistence into the
``notification_subscription_feed`` join table, a new subscription per call with the
per-type feed-uniqueness rule) and the ``ON DELETE CASCADE`` / ``delete-orphan``
behaviour against the real users test database.
"""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import configure_mappers

from middleware.request_context import _request_context

# Importing the module registers the mapper_configured listener under test.
from shared.database.users_database import UsersDatabase
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    FeatureFlag,
    NotificationSubscription,
    NotificationSubscriptionFeed,
    NotificationType,
    UserFeatureFlag,
)
from user_service.impl.users_api_impl import UsersApiImpl
from user_service_gen.models.create_notification_subscription_request import (
    CreateNotificationSubscriptionRequest,
)

FEED_SCOPED_TYPE = "feed.url_updated"


def _reset_singleton():
    UsersDatabase.instance = None
    UsersDatabase.initialized = False


def test_feed_scoped_relationship_uses_delete_orphan_and_passive_deletes():
    """Regression guard: the listener configures the feed join collection for DB-driven cascade."""
    configure_mappers()
    rel = NotificationSubscription.__mapper__.relationships["notification_subscription_feeds"]
    assert rel.passive_deletes is True
    assert "delete-orphan" in rel.cascade


@pytest.fixture
def api_session(users_test_database_url, monkeypatch):
    """A real users-DB session plus seeded user/type, always rolled back."""
    # Feed existence + metadata are resolved against the separate feeds DB; stub both here.
    monkeypatch.setattr("user_service.impl.users_api_impl.find_unknown_feed_ids", lambda *a, **k: [])
    monkeypatch.setattr("user_service.impl.users_api_impl.resolve_feed_metadata", lambda *a, **k: {})
    _reset_singleton()
    db = UsersDatabase()
    suffix = uuid.uuid4().hex
    user_id = f"feed-user-{suffix}"
    session = db.Session()
    session.add(AppUser(id=user_id, email=f"{user_id}@test.org"))
    # The feed-scoped type may already be seeded in the test DB; only insert if absent.
    if session.get(NotificationType, FEED_SCOPED_TYPE) is None:
        session.add(NotificationType(id=FEED_SCOPED_TYPE, description="url updated"))
    # Subscription management is gated by the isNotificationsEnabled flag (default off); enable it
    # for this user. The flag row is seeded by migration, but insert-if-absent keeps the test
    # self-contained.
    if session.get(FeatureFlag, "isNotificationsEnabled") is None:
        session.add(FeatureFlag(id="isNotificationsEnabled", value_type="boolean", default_value=False))
    session.add(UserFeatureFlag(user_id=user_id, feature_flag_id="isNotificationsEnabled", value=True))
    session.flush()
    _request_context.set({"user_id": user_id, "user_email": f"{user_id}@test.org", "is_guest": False})
    try:
        yield UsersApiImpl(), session, user_id
    finally:
        session.rollback()
        session.close()
        _reset_singleton()
        _request_context.set({})


def _feed_rows(session, sub_id):
    return {
        r.feed_stable_id for r in session.query(NotificationSubscriptionFeed).filter_by(subscription_id=sub_id).all()
    }


def _feed_rows_for_feed(session, feed_stable_id):
    return session.query(NotificationSubscriptionFeed).filter_by(feed_stable_id=feed_stable_id).all()


def test_create_persists_feed_ids(api_session):
    api, session, _ = api_session

    result = api.create_user_subscription(
        CreateNotificationSubscriptionRequest(notification_id=FEED_SCOPED_TYPE, feed_ids=["mdb-2", "mdb-1", "mdb-2"]),
        db_session=session,
    )

    assert result.notification_id == FEED_SCOPED_TYPE
    assert [f.feed_id for f in result.feeds] == ["mdb-1", "mdb-2"]  # sorted + deduped
    assert _feed_rows(session, result.id) == {"mdb-1", "mdb-2"}


def test_create_makes_new_subscription_per_call(api_session):
    api, session, _ = api_session

    first = api.create_user_subscription(
        CreateNotificationSubscriptionRequest(notification_id=FEED_SCOPED_TYPE, feed_ids=["mdb-1", "mdb-2"]),
        db_session=session,
    )
    second = api.create_user_subscription(
        CreateNotificationSubscriptionRequest(notification_id=FEED_SCOPED_TYPE, feed_ids=["mdb-3"]),
        db_session=session,
    )

    # A distinct subscription is created each time; earlier feeds are left untouched.
    assert second.id != first.id
    assert _feed_rows(session, first.id) == {"mdb-1", "mdb-2"}
    assert _feed_rows(session, second.id) == {"mdb-3"}
    assert [f.feed_id for f in second.feeds] == ["mdb-3"]


def test_create_rejects_feed_already_subscribed_for_same_type(api_session):
    api, session, _ = api_session

    api.create_user_subscription(
        CreateNotificationSubscriptionRequest(notification_id=FEED_SCOPED_TYPE, feed_ids=["mdb-1", "mdb-2"]),
        db_session=session,
    )

    with pytest.raises(HTTPException) as exc:
        api.create_user_subscription(
            # mdb-2 is already covered by the first subscription for this type.
            CreateNotificationSubscriptionRequest(notification_id=FEED_SCOPED_TYPE, feed_ids=["mdb-2", "mdb-9"]),
            db_session=session,
        )

    assert exc.value.status_code == 400
    assert "mdb-2" in exc.value.detail
    # Nothing from the rejected call is persisted.
    assert not _feed_rows_for_feed(session, "mdb-9")


def test_db_enforces_feed_unique_per_type_across_subscriptions(api_session):
    """The DB trigger is the backstop: a duplicate that bypasses the app pre-check (e.g. a
    concurrent create) is still rejected at flush."""
    api, session, user_id = api_session

    api.create_user_subscription(
        CreateNotificationSubscriptionRequest(notification_id=FEED_SCOPED_TYPE, feed_ids=["mdb-1"]),
        db_session=session,
    )

    # Insert a competing subscription targeting the same feed directly (no pre-check).
    other = NotificationSubscription(
        id=f"other-{uuid.uuid4().hex}", user_id=user_id, notification_type_id=FEED_SCOPED_TYPE
    )
    session.add(other)
    session.flush()
    session.add(NotificationSubscriptionFeed(subscription_id=other.id, feed_stable_id="mdb-1"))

    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_db_allows_same_feed_under_different_notification_type(api_session):
    """The rule is scoped per notification type: the same feed may be targeted under a
    different type without tripping the trigger."""
    api, session, _ = api_session
    if session.get(NotificationType, "feed.coverage") is None:
        session.add(NotificationType(id="feed.coverage", description="coverage"))
        session.flush()

    api.create_user_subscription(
        CreateNotificationSubscriptionRequest(notification_id=FEED_SCOPED_TYPE, feed_ids=["mdb-1"]),
        db_session=session,
    )
    other = api.create_user_subscription(
        CreateNotificationSubscriptionRequest(notification_id="feed.coverage", feed_ids=["mdb-1"]),
        db_session=session,
    )

    assert _feed_rows(session, other.id) == {"mdb-1"}


def test_delete_subscription_cascades_to_feed_rows(api_session):
    api, session, _ = api_session

    sub = api.create_user_subscription(
        CreateNotificationSubscriptionRequest(notification_id=FEED_SCOPED_TYPE, feed_ids=["mdb-1", "mdb-2"]),
        db_session=session,
    )
    assert _feed_rows(session, sub.id) == {"mdb-1", "mdb-2"}

    # Must not raise NotNullViolation; the DB ON DELETE CASCADE removes the feed rows.
    session.delete(session.get(NotificationSubscription, sub.id))
    session.flush()

    assert _feed_rows(session, sub.id) == set()


def test_create_requires_feed_ids_for_feed_scoped_type(api_session):
    api, session, _ = api_session

    with pytest.raises(HTTPException) as exc:
        api.create_user_subscription(
            CreateNotificationSubscriptionRequest(notification_id=FEED_SCOPED_TYPE),
            db_session=session,
        )
    assert exc.value.status_code == 400
