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
``notification_subscription_feed`` join table, idempotent feed-set merging) and the
``ON DELETE CASCADE`` / ``delete-orphan`` behaviour against the real users test database.
"""

import uuid

import pytest
from fastapi import HTTPException
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
from user_service_gen.models.update_notification_subscription_request import (
    UpdateNotificationSubscriptionRequest,
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


def test_create_persists_feed_ids(api_session):
    api, session, _ = api_session

    result = api.create_user_subscription(
        CreateNotificationSubscriptionRequest(notification_id=FEED_SCOPED_TYPE, feed_ids=["mdb-2", "mdb-1", "mdb-2"]),
        db_session=session,
    )

    assert result.notification_id == FEED_SCOPED_TYPE
    assert [f.feed_id for f in result.feeds] == ["mdb-1", "mdb-2"]  # sorted + deduped
    assert _feed_rows(session, result.id) == {"mdb-1", "mdb-2"}


def test_create_merges_feed_set_idempotently(api_session):
    api, session, _ = api_session

    first = api.create_user_subscription(
        CreateNotificationSubscriptionRequest(notification_id=FEED_SCOPED_TYPE, feed_ids=["mdb-1", "mdb-2"]),
        db_session=session,
    )
    second = api.create_user_subscription(
        CreateNotificationSubscriptionRequest(notification_id=FEED_SCOPED_TYPE, feed_ids=["mdb-2", "mdb-3"]),
        db_session=session,
    )

    # Same single subscription, feed set merged (union), not replaced.
    assert second.id == first.id
    assert [f.feed_id for f in second.feeds] == ["mdb-1", "mdb-2", "mdb-3"]
    assert _feed_rows(session, first.id) == {"mdb-1", "mdb-2", "mdb-3"}


def test_update_remove_feed_ids_removes_one_feed_and_keeps_others(api_session):
    api, session, _ = api_session

    sub = api.create_user_subscription(
        CreateNotificationSubscriptionRequest(notification_id=FEED_SCOPED_TYPE, feed_ids=["mdb-1", "mdb-2"]),
        db_session=session,
    )

    result = api.update_user_subscription(
        sub.id,
        UpdateNotificationSubscriptionRequest(remove_feed_ids=["mdb-1"]),
        db_session=session,
    )

    assert [f.feed_id for f in result.feeds] == ["mdb-2"]
    assert _feed_rows(session, sub.id) == {"mdb-2"}


def test_update_remove_feed_ids_deletes_subscription_when_emptied(api_session):
    api, session, _ = api_session

    sub = api.create_user_subscription(
        CreateNotificationSubscriptionRequest(notification_id=FEED_SCOPED_TYPE, feed_ids=["mdb-1"]),
        db_session=session,
    )

    result = api.update_user_subscription(
        sub.id,
        UpdateNotificationSubscriptionRequest(remove_feed_ids=["mdb-1"]),
        db_session=session,
    )

    # A feed-scoped subscription can't exist with no feeds, so removing the last feed deletes
    # it entirely (cascading to its feed rows) instead of leaving an empty subscription behind.
    assert result.id == sub.id
    assert result.feeds is None
    assert session.get(NotificationSubscription, sub.id) is None
    assert _feed_rows(session, sub.id) == set()


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


# ── GET /v1/user/subscriptions/feeds and /feeds/{id} (issue #212) ──────────


def test_get_user_subscription_feeds_empty_when_no_feed_scoped_subscriptions(api_session):
    api, session, _ = api_session

    result = api.get_user_subscription_feeds(db_session=session)

    assert result == []


def test_get_user_subscription_feeds_groups_across_feeds(api_session):
    api, session, _ = api_session

    api.create_user_subscription(
        CreateNotificationSubscriptionRequest(notification_id=FEED_SCOPED_TYPE, feed_ids=["mdb-2", "mdb-1"]),
        db_session=session,
    )

    result = api.get_user_subscription_feeds(db_session=session)

    assert [g.feed_id for g in result] == ["mdb-1", "mdb-2"]
    assert all(len(g.subscriptions) == 1 for g in result)


def test_get_user_subscription_feeds_isolated_per_user(api_session):
    api, session, _ = api_session

    api.create_user_subscription(
        CreateNotificationSubscriptionRequest(notification_id=FEED_SCOPED_TYPE, feed_ids=["mdb-1"]),
        db_session=session,
    )

    # A different user's subscription to the same feed must not leak into this user's view.
    other_user_id = f"other-{uuid.uuid4().hex}"
    session.add(AppUser(id=other_user_id, email=f"{other_user_id}@test.org"))
    other_sub = NotificationSubscription(
        id=str(uuid.uuid4()), user_id=other_user_id, notification_type_id=FEED_SCOPED_TYPE, active=True
    )
    other_sub.notification_subscription_feeds.append(NotificationSubscriptionFeed(feed_stable_id="mdb-1"))
    session.add(other_sub)
    session.flush()

    result = api.get_user_subscription_feeds(db_session=session)

    assert len(result) == 1
    assert result[0].feed_id == "mdb-1"
    assert [s.id for s in result[0].subscriptions] != [other_sub.id]


def test_get_user_subscription_feed_by_id_returns_matching_feed(api_session):
    api, session, _ = api_session

    api.create_user_subscription(
        CreateNotificationSubscriptionRequest(notification_id=FEED_SCOPED_TYPE, feed_ids=["mdb-1", "mdb-2"]),
        db_session=session,
    )

    result = api.get_user_subscription_feed_by_id("mdb-2", db_session=session)

    assert result.feed_id == "mdb-2"
    assert len(result.subscriptions) == 1


def test_get_user_subscription_feed_by_id_404_for_unknown_feed(api_session):
    api, session, _ = api_session

    with pytest.raises(HTTPException) as exc:
        api.get_user_subscription_feed_by_id("mdb-999", db_session=session)
    assert exc.value.status_code == 404


def test_get_user_subscription_feed_by_id_null_metadata_when_unresolved(api_session):
    """resolve_feed_metadata is stubbed to {} by api_session (no feeds DB here), simulating a
    feed no longer present in the feeds DB. The group must still be returned, not 404, with
    null metadata fields."""
    api, session, _ = api_session

    api.create_user_subscription(
        CreateNotificationSubscriptionRequest(notification_id=FEED_SCOPED_TYPE, feed_ids=["mdb-1"]),
        db_session=session,
    )

    result = api.get_user_subscription_feed_by_id("mdb-1", db_session=session)

    assert result.feed_id == "mdb-1"
    assert result.data_type is None
    assert result.provider is None
    assert result.feed_name is None
