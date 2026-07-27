import unittest
import uuid
from unittest.mock import MagicMock

from shared.database.users_database import UsersDatabase
from shared.users_database_gen.sqlacodegen_models import NotificationType as NotificationTypeOrm
from user_service.impl.notifications_api_impl import NotificationsApiImpl
from user_service_gen.models.notification_type import NotificationType


class TestNotificationsApiImpl(unittest.TestCase):
    def setUp(self):
        self.api = NotificationsApiImpl()
        self.mock_session = MagicMock()

    def test_get_notifications_returns_mapped_types(self):
        self.mock_session.query.return_value.order_by.return_value.all.return_value = [
            NotificationTypeOrm(id="api.announcements", description="Announcements"),
            NotificationTypeOrm(id="feed.url_updated", description=None),
        ]

        result = self.api.get_notifications(db_session=self.mock_session)

        self.mock_session.query.assert_called_once_with(NotificationTypeOrm)
        self.assertTrue(all(isinstance(t, NotificationType) for t in result))
        self.assertEqual([t.id for t in result], ["api.announcements", "feed.url_updated"])
        self.assertEqual(result[0].description, "Announcements")
        self.assertIsNone(result[1].description)

    def test_get_notifications_empty(self):
        self.mock_session.query.return_value.order_by.return_value.all.return_value = []
        self.assertEqual(self.api.get_notifications(db_session=self.mock_session), [])


def _reset_singleton():
    UsersDatabase.instance = None
    UsersDatabase.initialized = False


def test_get_notifications_db_backed(users_test_database_url):
    """End-to-end against the real users test DB: an inserted type appears in the result."""
    _reset_singleton()
    db = UsersDatabase()
    type_id = f"test.type-{uuid.uuid4().hex}"
    session = db.Session()
    try:
        session.add(NotificationTypeOrm(id=type_id, description="db-backed test type"))
        session.flush()

        result = NotificationsApiImpl().get_notifications(db_session=session)

        by_id = {t.id: t for t in result}
        assert type_id in by_id
        assert by_id[type_id].description == "db-backed test type"
        # Result is sorted by id.
        assert [t.id for t in result] == sorted(t.id for t in result)
    finally:
        session.rollback()
        session.close()
        _reset_singleton()


if __name__ == "__main__":
    unittest.main()
