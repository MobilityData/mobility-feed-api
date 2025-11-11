import unittest
from unittest.mock import patch, MagicMock

from tasks.licenses.license_matcher import (
    get_parameters,
    get_csv_response,
    process_feed,
    match_licenses_task,
    match_license_handler,
    process_all_feeds,
)


class TestLicenseMatcher(unittest.TestCase):
    def test_get_parameters_defaults(self):
        payload = {}
        dry_run, only_unmatched, feed_stable_id, content_type = get_parameters(payload)
        self.assertFalse(dry_run)
        self.assertTrue(only_unmatched)
        self.assertIsNone(feed_stable_id)
        self.assertEqual(content_type, "application/json")

    def test_get_parameters_values(self):
        payload = {
            "dry_run": True,
            "only_unmatched": False,
            "feed_stable_id": "feed-123",
            "content_type": "text/csv",
        }
        dry_run, only_unmatched, feed_stable_id, content_type = get_parameters(payload)
        self.assertTrue(dry_run)
        self.assertFalse(only_unmatched)
        self.assertEqual(feed_stable_id, "feed-123")
        self.assertEqual(content_type, "text/csv")

    def test_get_csv_response(self):
        matches = [
            {
                "feed_id": "id1",
                "feed_stable_id": "stable1",
                "feed_data_type": "gtfs",
                "feed_license_url": "http://example.com/license1",
                "matched_license_id": "MIT",
                "matched_spdx_id": "MIT",
                "confidence": 0.99,
                "match_type": "exact",
                "matched_name": "MIT License",
                "matched_catalog_url": "http://example.com/license1",
                "matched_source": "db.license",
            }
        ]
        csv_text = get_csv_response(matches)
        header = csv_text.splitlines()[0]
        # Current implementation concatenates md_url and feed_license_url in header
        self.assertIn("md_urlfeed_license_url", header)
        self.assertIn("feed_id,feed_stable_id,feed_data_type", header)
        self.assertIn("https://mobilitydatabase.org/feeds/stable1", csv_text)
        self.assertIn("MIT", csv_text)

    @patch("tasks.licenses.license_matcher.resolve_license")
    def test_process_feed_with_match(self, mock_resolve):
        feed = MagicMock()
        feed.id = "feed1"
        feed.stable_id = "stable1"
        feed.data_type = "gtfs"
        feed.license_url = "http://example.com/license"
        feed.license_id = None

        match_obj = MagicMock()
        match_obj.license_id = "MIT"
        match_obj.spdx_id = "MIT"
        match_obj.confidence = 0.95
        match_obj.match_type = "exact"
        match_obj.matched_name = "MIT License"
        match_obj.matched_catalog_url = "http://example.com/license"
        match_obj.matched_source = "db.license"
        mock_resolve.return_value = [match_obj]

        result = process_feed(feed, dry_run=False, db_session=MagicMock())
        self.assertIsNotNone(result)
        self.assertEqual(result["matched_license_id"], "MIT")
        self.assertEqual(feed.license_id, "MIT")

    @patch("tasks.licenses.license_matcher.resolve_license")
    def test_process_feed_no_match(self, mock_resolve):
        feed = MagicMock()
        feed.id = "feed2"
        feed.stable_id = "stable2"
        feed.data_type = "gtfs"
        feed.license_url = "http://example.com/license2"
        mock_resolve.return_value = []
        result = process_feed(feed, dry_run=True, db_session=MagicMock())
        self.assertIsNone(result)

    @patch("tasks.licenses.license_matcher.process_feed")
    def test_match_licenses_task_single_feed(self, mock_process_feed):
        feed = MagicMock()
        feed.stable_id = "stable1"
        mock_process_feed.return_value = {"feed_id": "f1"}

        query_stub = MagicMock()
        query_stub.filter.return_value = query_stub
        query_stub.first.return_value = feed

        db_session = MagicMock()
        db_session.query.return_value = query_stub

        result = match_licenses_task(
            dry_run=True,
            only_unmatched=True,
            feed_stable_id="stable1",
            db_session=db_session,
        )
        self.assertEqual(result, [{"feed_id": "f1"}])
        mock_process_feed.assert_called_once()

    @patch("tasks.licenses.license_matcher.process_feed")
    def test_match_license_handler_csv(self, mock_process_feed):
        mock_process_feed.return_value = {
            "feed_id": "f1",
            "feed_stable_id": "stable1",
            "feed_data_type": "gtfs",
            "feed_license_url": "http://example.com/license",
            "matched_license_id": "MIT",
            "matched_spdx_id": "MIT",
            "confidence": 1.0,
            "match_type": "exact",
            "matched_name": "MIT License",
            "matched_catalog_url": "http://example.com/license",
            "matched_source": "db.license",
        }

        with patch(
            "tasks.licenses.license_matcher.match_licenses_task",
            return_value=[mock_process_feed.return_value],
        ):
            payload = {
                "dry_run": True,
                "feed_stable_id": "stable1",
                "content_type": "text/csv",
            }
            csv_output = match_license_handler(payload)
            self.assertIn("feed_stable_id", csv_output.splitlines()[0])
            self.assertIn("stable1", csv_output)
            self.assertIn("MIT", csv_output)

    @patch("tasks.licenses.license_matcher.process_feed")
    def test_match_license_handler_json(self, mock_process_feed):
        mock_process_feed.return_value = {"feed_id": "f1"}
        with patch(
            "tasks.licenses.license_matcher.match_licenses_task",
            return_value=[mock_process_feed.return_value],
        ):
            payload = {"dry_run": True, "feed_stable_id": "stable1"}
            result = match_license_handler(payload)
            self.assertEqual(result, [{"feed_id": "f1"}])

    @patch("tasks.licenses.license_matcher.resolve_license")
    def test_process_all_feeds_sequential(self, mock_resolve):
        # Prepare feeds
        feed1 = MagicMock()
        feed1.id = "a"
        feed1.stable_id = "sA"
        feed1.data_type = "gtfs"
        feed1.license_url = "http://example.com/l1"
        feed1.license_id = None
        feed2 = MagicMock()
        feed2.id = "b"
        feed2.stable_id = "sB"
        feed2.data_type = "gtfs"
        feed2.license_url = "http://example.com/l2"
        feed2.license_id = None

        # MatchingLicense mocks
        m1 = MagicMock()
        m1.license_id = "MIT"
        m1.spdx_id = "MIT"
        m1.confidence = 0.9
        m1.match_type = "exact"
        m1.matched_name = "MIT"
        m1.matched_catalog_url = "u1"
        m1.matched_source = "db.license"
        m2 = MagicMock()
        m2.license_id = "BSD"
        m2.spdx_id = "BSD"
        m2.confidence = 0.8
        m2.match_type = "exact"
        m2.matched_name = "BSD"
        m2.matched_catalog_url = "u2"
        m2.matched_source = "db.license"
        mock_resolve.side_effect = [[m1], [m2]]

        # Query stub returning one batch then empty
        class QueryStub:
            def __init__(self, batches):
                self.batches = batches
                self.calls = 0

            def filter(self, *a, **k):
                return self

            def order_by(self, *a, **k):
                return self

            def limit(self, *a, **k):
                return self

            def all(self):
                if self.calls < len(self.batches):
                    res = self.batches[self.calls]
                else:
                    res = []
                self.calls += 1
                return res

        db_session = MagicMock()
        db_session.query.return_value = QueryStub([[feed1, feed2], []])
        db_session.flush.return_value = None
        db_session.expunge_all.return_value = None

        matches = process_all_feeds(
            dry_run=False, only_unmatched=True, db_session=db_session
        )
        self.assertEqual(len(matches), 2)
        self.assertEqual(feed1.license_id, "MIT")
        self.assertEqual(feed2.license_id, "BSD")


if __name__ == "__main__":
    unittest.main()
