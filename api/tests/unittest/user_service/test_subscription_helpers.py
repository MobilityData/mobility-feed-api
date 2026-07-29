import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from user_service.impl.subscription_helpers import find_unknown_feed_ids, resolve_feed_metadata


class TestFindUnknownFeedIds(unittest.TestCase):
    def _session_with_existing(self, existing_ids):
        session = MagicMock()
        session.query.return_value.filter.return_value.all.return_value = [(fid,) for fid in existing_ids]
        return session

    def test_empty_returns_empty_without_query(self):
        session = MagicMock()
        self.assertEqual(find_unknown_feed_ids([], db_session=session), [])
        session.query.assert_not_called()

    def test_all_known(self):
        session = self._session_with_existing(["mdb-1", "mdb-2"])
        self.assertEqual(find_unknown_feed_ids(["mdb-1", "mdb-2"], db_session=session), [])

    def test_returns_only_unknown_preserving_order(self):
        session = self._session_with_existing(["mdb-1"])
        self.assertEqual(
            find_unknown_feed_ids(["mdb-1", "mdba-100", "mdb-nope"], db_session=session),
            ["mdba-100", "mdb-nope"],
        )

    def test_dedupes_before_checking(self):
        session = self._session_with_existing([])
        self.assertEqual(find_unknown_feed_ids(["mdba-100", "mdba-100"], db_session=session), ["mdba-100"])


class TestResolveFeedMetadata(unittest.TestCase):
    def _session_with_rows(self, rows):
        session = MagicMock()
        session.query.return_value.filter.return_value.all.return_value = [
            SimpleNamespace(stable_id=sid, data_type=dt, provider=pr, feed_name=fn) for (sid, dt, pr, fn) in rows
        ]
        return session

    def test_empty_returns_empty_without_query(self):
        session = MagicMock()
        self.assertEqual(resolve_feed_metadata([], db_session=session), {})
        session.query.assert_not_called()

    def test_maps_stable_id_to_metadata(self):
        session = self._session_with_rows([("mdb-1", "gtfs", "MTA", "Subway")])
        result = resolve_feed_metadata(["mdb-1", "mdb-missing"], db_session=session)
        self.assertEqual(result, {"mdb-1": {"data_type": "gtfs", "provider": "MTA", "feed_name": "Subway"}})
        # A missing feed simply has no entry (caller fills nulls).
        self.assertNotIn("mdb-missing", result)


if __name__ == "__main__":
    unittest.main()
