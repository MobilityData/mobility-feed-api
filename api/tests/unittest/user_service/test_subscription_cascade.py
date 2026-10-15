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
"""Tests for deleting a NotificationSubscription cascading to its notification_log rows.

Importing ``shared.database.users_database`` registers the ``mapper_configured`` listener that
enables ``passive_deletes`` on ``NotificationSubscription.notification_logs``. Together with the
``ON DELETE CASCADE`` foreign key on ``notification_log.subscription_id``, deleting a subscription
removes its logs without SQLAlchemy trying to NULL the NOT NULL ``subscription_id`` column.
"""

import uuid

from sqlalchemy.orm import configure_mappers

# Importing the module registers the cascade listener (side effect under test).
from shared.database.users_database import UsersDatabase
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    NotificationLog,
    NotificationSubscription,
    NotificationType,
)


def _reset_singleton():
    UsersDatabase.instance = None
    UsersDatabase.initialized = False


def test_notification_logs_relationship_uses_passive_deletes():
    """Regression guard: the listener must keep passive_deletes enabled on the relationship.

    Without passive_deletes, deleting a subscription would try to NULL the NOT NULL
    ``notification_log.subscription_id`` and raise a NotNullViolation.
    """
    configure_mappers()
    rel = NotificationSubscription.__mapper__.relationships["notification_logs"]
    assert rel.passive_deletes is True
    assert "delete-orphan" in rel.cascade


def test_delete_subscription_cascades_to_notification_log(users_test_database_url):
    """End-to-end: deleting a subscription removes its notification_log rows via the DB cascade."""
    _reset_singleton()
    db = UsersDatabase()
    suffix = uuid.uuid4().hex
    user_id = f"cascade-user-{suffix}"
    type_id = f"cascade-type-{suffix}"
    sub_id = f"cascade-sub-{suffix}"
    log_id = f"cascade-log-{suffix}"

    session = db.Session()
    try:
        session.add(AppUser(id=user_id, email=f"{user_id}@test.org"))
        session.add(NotificationType(id=type_id, description="cascade test type"))
        session.flush()
        session.add(NotificationSubscription(id=sub_id, user_id=user_id, notification_type_id=type_id))
        session.flush()
        session.add(NotificationLog(id=log_id, subscription_id=sub_id, status="sent"))
        session.flush()
        assert session.query(NotificationLog).filter_by(id=log_id).count() == 1

        # Must not raise NotNullViolation; the DB ON DELETE CASCADE removes the log.
        session.delete(session.get(NotificationSubscription, sub_id))
        session.flush()

        assert session.query(NotificationLog).filter_by(id=log_id).count() == 0
    finally:
        # Never commit: keep the database clean.
        session.rollback()
        session.close()
        _reset_singleton()
