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
``notification_subscription_feed`` join table, idempotent feed-set replacement) and the
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
def api_session(users_test_database_url):
    """A real users-DB session plus seeded user/type, always rolled back."""
    _reset_singleton()
    db = UsersDatabase()
    suffix = uuid.uuid4().hex
    user_id = f"feed-user-{suffix}"
    session = db.Session()
    session.add(AppUser(id=user_id, email=f"{user_id}@test.org"))
    # The feed-scoped type may already be seeded in the test DB; only insert if absent.
    if session.get(NotificationType, FEED_SCOPED_TYPE) is None:
        session.add(NotificationType(id=FEED_SCOPED_TYPE, description="url updated"))
    # Subscription management is gated by the isNotificationEnabled flag (default off); enable it
    # for this user. The flag row is seeded by migration, but insert-if-absent keeps the test
    # self-contained.
    if session.get(FeatureFlag, "isNotificationEnabled") is None:
        session.add(FeatureFlag(id="isNotificationEnabled", value_type="boolean", default_value=False))
    session.add(UserFeatureFlag(user_id=user_id, feature_flag_id="isNotificationEnabled", value=True))
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
    assert result.feed_ids == ["mdb-1", "mdb-2"]  # sorted + deduped
    assert _feed_rows(session, result.id) == {"mdb-1", "mdb-2"}


def test_create_replaces_feed_set_idempotently(api_session):
    api, session, _ = api_session

    first = api.create_user_subscription(
        CreateNotificationSubscriptionRequest(notification_id=FEED_SCOPED_TYPE, feed_ids=["mdb-1", "mdb-2"]),
        db_session=session,
    )
    second = api.create_user_subscription(
        CreateNotificationSubscriptionRequest(notification_id=FEED_SCOPED_TYPE, feed_ids=["mdb-3"]),
        db_session=session,
    )

    # Same single subscription, feed set replaced.
    assert second.id == first.id
    assert second.feed_ids == ["mdb-3"]
    assert _feed_rows(session, first.id) == {"mdb-3"}


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
