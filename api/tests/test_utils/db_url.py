"""Resolution of the test database URLs.

These URLs are per worktree. ``scripts/worktree-env.sh`` publishes Postgres on a
different host port in each git worktree so that several stacks - and several
test runs - can be active at once, and writes the resulting URLs into
``config/.env.worktree``. ``scripts/api-tests.sh`` merges that file into the
``.env`` that sits next to the tests.

The literals below are the values for a checkout with no such override, and for
CI, which never creates one. Behaviour is therefore unchanged when it is absent.
"""

import os
from typing import Final

from dotenv import load_dotenv

# Populate os.environ from the .env that scripts/api-tests.sh writes next to the
# tests. load_dotenv never overrides a variable already set in the environment.
load_dotenv()

DEFAULT_FEEDS_TEST_DATABASE_URL: Final[str] = "postgresql://postgres:postgres@localhost:54320/MobilityDatabaseTest"

DEFAULT_USERS_TEST_DATABASE_URL: Final[str] = "postgresql://postgres:postgres@localhost:54320/MobilityDatabaseUsersTest"


def feeds_test_database_url() -> str:
    """URL of the feeds test database for this worktree."""
    return os.getenv("FEEDS_DATABASE_URL_TEST", DEFAULT_FEEDS_TEST_DATABASE_URL)


def users_test_database_url() -> str:
    """URL of the users test database for this worktree.

    ``TEST_USERS_DATABASE_URL`` is honoured first because it predates the
    per-worktree override and is already used to redirect individual tests.
    """
    return os.getenv("TEST_USERS_DATABASE_URL") or os.getenv("USERS_DATABASE_URL_TEST", DEFAULT_USERS_TEST_DATABASE_URL)
