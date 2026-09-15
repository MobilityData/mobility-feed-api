import sys
import os

import pytest

# Ensure src is on the path for these standalone unit tests.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../src"))

from tests.test_utils.db_url import users_test_database_url as resolve_users_test_database_url  # noqa: E402

# Users test database. Per worktree - see tests/test_utils/db_url.py. Defaults to
# the CI "Run tests" Liquibase target
# (liquibase update on jdbc:postgresql://localhost:54320/MobilityDatabaseUsersTest).
USERS_TEST_DATABASE_URL = resolve_users_test_database_url()


@pytest.fixture
def users_test_database_url():
    """Point ``USERS_DATABASE_URL`` at the test users DB for DB-backed unit tests.

    ``load_dotenv`` does not override variables already present in the environment, so setting
    this before ``UsersDatabase`` is constructed keeps the test off the developer's local
    ``USERS_DATABASE_URL`` and on the CI test database.
    """
    previous = os.environ.get("USERS_DATABASE_URL")
    os.environ["USERS_DATABASE_URL"] = USERS_TEST_DATABASE_URL
    try:
        yield os.environ["USERS_DATABASE_URL"]
    finally:
        if previous is None:
            os.environ.pop("USERS_DATABASE_URL", None)
        else:
            os.environ["USERS_DATABASE_URL"] = previous
