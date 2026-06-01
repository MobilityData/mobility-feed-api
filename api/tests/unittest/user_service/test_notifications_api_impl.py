import unittest

from fastapi import HTTPException

from user_service.impl.notifications_api_impl import NotificationsApiImpl


class TestNotificationsApiImpl(unittest.TestCase):
    def setUp(self):
        self.api = NotificationsApiImpl()

    def test_get_notifications_returns_501(self):
        with self.assertRaises(HTTPException) as ctx:
            self.api.get_notifications()
        self.assertEqual(ctx.exception.status_code, 501)


if __name__ == "__main__":
    unittest.main()
