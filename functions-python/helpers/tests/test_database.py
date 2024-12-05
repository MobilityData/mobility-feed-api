import os
import unittest
from typing import Final
from unittest import mock

from database import refresh_materialized_view, start_db_session

default_db_url: Final[
    str
] = "postgresql://postgres:postgres@localhost:54320/MobilityDatabaseTest"


@mock.patch.dict(
    os.environ,
    {
        "FEEDS_DATABASE_URL": default_db_url,
        "FEEDS_PUBSUB_TOPIC_NAME": "test_topic",
        "ENVIRONMENT": "test",
        "FEEDS_LIMIT": "5",
    },
)
class TestDatabase(unittest.TestCase):
    def test_refresh_materialized_view_existing_view(self):
        view_name = "feedsearch"

        session = start_db_session(os.getenv("FEEDS_DATABASE_URL"))
        result = refresh_materialized_view(session, view_name)

        self.assertTrue(result)

    def test_refresh_materialized_view_invalid_view(self):
        view_name = "invalid_view_name"

        session = start_db_session(os.getenv("FEEDS_DATABASE_URL"))
        result = refresh_materialized_view(session, view_name)

        self.assertFalse(result)
