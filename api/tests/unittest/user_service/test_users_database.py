import unittest
from unittest.mock import MagicMock, patch

from shared.database.users_database import UsersDatabase, with_users_db_session


def _reset_singleton():
    UsersDatabase.instance = None
    UsersDatabase.initialized = False


class TestUsersDatabaseSingleton(unittest.TestCase):
    def setUp(self):
        _reset_singleton()

    def tearDown(self):
        _reset_singleton()

    @patch("shared.database.users_database.create_engine")
    @patch("shared.database.users_database.sessionmaker")
    def test_singleton_returns_same_instance(self, mock_sessionmaker, mock_create_engine):
        with patch.dict("os.environ", {"USERS_DATABASE_URL": "postgresql://localhost/test"}):
            db1 = UsersDatabase()
            db2 = UsersDatabase()
        self.assertIs(db1, db2)

    @patch("shared.database.users_database.create_engine")
    @patch("shared.database.users_database.sessionmaker")
    def test_init_uses_provided_url(self, mock_sessionmaker, mock_create_engine):
        url = "postgresql://localhost/users_test"
        UsersDatabase(users_database_url=url)
        mock_create_engine.assert_called_once()
        call_args = mock_create_engine.call_args
        self.assertEqual(call_args[0][0], url)

    @patch("shared.database.users_database.create_engine")
    @patch("shared.database.users_database.sessionmaker")
    def test_init_uses_env_var_when_no_url_provided(self, mock_sessionmaker, mock_create_engine):
        with patch.dict("os.environ", {"USERS_DATABASE_URL": "postgresql://localhost/from_env"}):
            UsersDatabase()
        mock_create_engine.assert_called_once()
        self.assertEqual(mock_create_engine.call_args[0][0], "postgresql://localhost/from_env")

    def test_init_raises_when_no_url(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("shared.database.users_database.load_dotenv"):
                with self.assertRaises(Exception, msg="USERS_DATABASE_URL not provided."):
                    UsersDatabase()

    @patch("shared.database.users_database.create_engine")
    @patch("shared.database.users_database.sessionmaker")
    def test_second_init_is_no_op(self, mock_sessionmaker, mock_create_engine):
        url = "postgresql://localhost/users_test"
        UsersDatabase(users_database_url=url)
        UsersDatabase(users_database_url=url)
        mock_create_engine.assert_called_once()


class TestUsersDatabaseSession(unittest.TestCase):
    def setUp(self):
        _reset_singleton()

    def tearDown(self):
        _reset_singleton()

    @patch("shared.database.users_database.create_engine")
    @patch("shared.database.users_database.sessionmaker")
    def _make_db(self, mock_sessionmaker, mock_create_engine):
        mock_session = MagicMock()
        mock_sessionmaker.return_value = lambda: mock_session
        db = UsersDatabase(users_database_url="postgresql://localhost/test")
        return db, mock_session

    def test_start_db_session_commits_on_success(self):
        db, mock_session = self._make_db()
        with db.start_db_session() as session:
            self.assertIs(session, mock_session)
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    def test_start_db_session_rolls_back_on_exception(self):
        db, mock_session = self._make_db()
        with self.assertRaises(ValueError):
            with db.start_db_session():
                raise ValueError("boom")
        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
        mock_session.close.assert_called_once()


class TestWithUsersDbSession(unittest.TestCase):
    def setUp(self):
        _reset_singleton()

    def tearDown(self):
        _reset_singleton()

    def test_passes_through_injected_session(self):
        mock_session = MagicMock()

        @with_users_db_session
        def my_func(db_session=None):
            return db_session

        result = my_func(db_session=mock_session)
        self.assertIs(result, mock_session)

    def test_partial_application_when_func_is_none(self):
        decorator = with_users_db_session(db_url="postgresql://localhost/test")
        self.assertTrue(callable(decorator))

    @patch("shared.database.users_database.create_engine")
    @patch("shared.database.users_database.sessionmaker")
    def test_creates_session_when_none_injected(self, mock_sessionmaker, mock_create_engine):
        mock_session = MagicMock()
        mock_sessionmaker.return_value = lambda: mock_session

        @with_users_db_session(db_url="postgresql://localhost/test")
        def my_func(db_session=None):
            return db_session

        result = my_func()
        self.assertIs(result, mock_session)
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
