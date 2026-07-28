import unittest
from unittest.mock import MagicMock

from user_service.impl.subscription_helpers import find_unknown_feed_ids


class TestFindUnknownFeedIds(unittest.TestCase):
    def _session_with_existing(self, existing_ids):
        session = MagicMock()
        session.query.return_value.filter.return_value.all.return_value = [(fid,) for fid in existing_ids]
        return session

    def test_empty_returns_empty_without_query(self):
        session = MagicMock()
        self.assertEqual(find_unknown_feed_ids([], feeds_db_session=session), [])
        session.query.assert_not_called()

    def test_all_known(self):
        session = self._session_with_existing(["mdb-1", "mdb-2"])
        self.assertEqual(find_unknown_feed_ids(["mdb-1", "mdb-2"], feeds_db_session=session), [])

    def test_returns_only_unknown_preserving_order(self):
        session = self._session_with_existing(["mdb-1"])
        self.assertEqual(
            find_unknown_feed_ids(["mdb-1", "mdba-100", "mdb-nope"], feeds_db_session=session),
            ["mdba-100", "mdb-nope"],
        )

    def test_dedupes_before_checking(self):
        session = self._session_with_existing([])
        self.assertEqual(find_unknown_feed_ids(["mdba-100", "mdba-100"], feeds_db_session=session), ["mdba-100"])


if __name__ == "__main__":
    unittest.main()
