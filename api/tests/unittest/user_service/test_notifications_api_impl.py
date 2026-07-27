import unittest
import uuid
from unittest.mock import MagicMock

from middleware.request_context import _request_context
from shared.database.users_database import UsersDatabase
from shared.users_database_gen.sqlacodegen_models import (
    FeatureFlag,
    NotificationType as NotificationTypeOrm,
    UserFeatureFlag,
)
from user_service.impl.notifications_api_impl import NotificationsApiImpl
from user_service_gen.models.notification_type import NotificationType

ADMIN_TYPE = "admin.event_summary"


def _set_context(user_id="uid-123"):
    _request_context.set({"user_id": user_id, "user_email": "u@e.com", "is_guest": False})


class TestGetNotifications(unittest.TestCase):
    def setUp(self):
        self.api = NotificationsApiImpl()
        self.mock_session = MagicMock()
        _set_context()

    def _set_types(self, types):
        self.mock_session.query.return_value.order_by.return_value.all.return_value = types

    def _set_admin_flag(self, enabled):
        flag = FeatureFlag(
            id="isAdminSummarySubscriptionEnabled", value_type="boolean", default_value=enabled, disabled=False
        )

        def _get(model, key):
            if model is FeatureFlag:
                return flag
            if model is UserFeatureFlag:
                return None
            return None

        self.mock_session.get.side_effect = _get

    def test_returns_mapped_types(self):
        self._set_types(
            [
                NotificationTypeOrm(id="api.announcements", description="Announcements"),
                NotificationTypeOrm(id="feed.url_updated", description=None),
            ]
        )
        self._set_admin_flag(False)

        result = self.api.get_notifications(db_session=self.mock_session)

        self.mock_session.query.assert_called_once_with(NotificationTypeOrm)
        self.assertTrue(all(isinstance(t, NotificationType) for t in result))
        self.assertEqual([t.id for t in result], ["api.announcements", "feed.url_updated"])
        self.assertEqual(result[0].description, "Announcements")
        self.assertIsNone(result[1].description)

    def test_admin_type_hidden_when_flag_off(self):
        self._set_types(
            [
                NotificationTypeOrm(id="api.announcements", description=None),
                NotificationTypeOrm(id=ADMIN_TYPE, description="admin"),
            ]
        )
        self._set_admin_flag(False)

        result = self.api.get_notifications(db_session=self.mock_session)

        self.assertEqual([t.id for t in result], ["api.announcements"])

    def test_admin_type_visible_when_flag_on(self):
        self._set_types(
            [
                NotificationTypeOrm(id="api.announcements", description=None),
                NotificationTypeOrm(id=ADMIN_TYPE, description="admin"),
            ]
        )
        self._set_admin_flag(True)

        result = self.api.get_notifications(db_session=self.mock_session)

        self.assertEqual([t.id for t in result], ["api.announcements", ADMIN_TYPE])

    def test_admin_type_hidden_for_anonymous_without_flag_lookup(self):
        _request_context.set({})  # no user_id
        self._set_types(
            [
                NotificationTypeOrm(id="api.announcements", description=None),
                NotificationTypeOrm(id=ADMIN_TYPE, description="admin"),
            ]
        )

        result = self.api.get_notifications(db_session=self.mock_session)

        self.assertEqual([t.id for t in result], ["api.announcements"])
        # Without a user there is no flag to resolve.
        self.mock_session.get.assert_not_called()

    def test_empty(self):
        self._set_types([])
        self._set_admin_flag(False)
        self.assertEqual(self.api.get_notifications(db_session=self.mock_session), [])


def _reset_singleton():
    UsersDatabase.instance = None
    UsersDatabase.initialized = False


def test_get_notifications_db_backed(users_test_database_url):
    """End-to-end against the real users test DB: an inserted type appears; admin type is hidden."""
    _reset_singleton()
    db = UsersDatabase()
    type_id = f"test.type-{uuid.uuid4().hex}"
    session = db.Session()
    try:
        session.add(NotificationTypeOrm(id=type_id, description="db-backed test type"))
        session.flush()
        _request_context.set({})  # anonymous → admin.event_summary filtered out

        result = NotificationsApiImpl().get_notifications(db_session=session)

        by_id = {t.id: t for t in result}
        assert type_id in by_id
        assert by_id[type_id].description == "db-backed test type"
        # admin.event_summary is seeded (feat_1723) but hidden without the admin flag.
        assert ADMIN_TYPE not in by_id
        assert [t.id for t in result] == sorted(t.id for t in result)
    finally:
        session.rollback()
        session.close()
        _reset_singleton()
        _request_context.set({})


if __name__ == "__main__":
    unittest.main()
