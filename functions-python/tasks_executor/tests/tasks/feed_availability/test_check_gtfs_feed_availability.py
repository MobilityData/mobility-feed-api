#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import unittest
from unittest.mock import patch, MagicMock

import requests

from tasks.feed_availability.check_gtfs_feed_availability import (
    check_gtfs_feed_availability,
    check_gtfs_feed_availability_handler,
    get_feeds_query,
    _perform_head_request,
)


def _make_feed(feed_id: str, producer_url: str):
    feed = MagicMock()
    feed.id = feed_id
    feed.producer_url = producer_url
    return feed


class TestCheckGtfsFeedAvailabilityHandler(unittest.TestCase):
    @patch(
        "tasks.feed_availability.check_gtfs_feed_availability.check_gtfs_feed_availability"
    )
    def test_handler_passes_defaults(self, mock_fn):
        mock_fn.return_value = {"total_feeds": 0}
        result = check_gtfs_feed_availability_handler({})
        mock_fn.assert_called_once_with(
            dry_run=True,
            skip_db_update=False,
            limit=None,
            concurrency=10,
            timeout_seconds=20,
            batch_size=50,
            feed_ids=None,
        )
        self.assertEqual(result["total_feeds"], 0)

    @patch(
        "tasks.feed_availability.check_gtfs_feed_availability.check_gtfs_feed_availability"
    )
    def test_handler_passes_payload_params(self, mock_fn):
        mock_fn.return_value = {"total_feeds": 5}
        payload = {
            "dry_run": False,
            "skip_db_update": True,
            "limit": 5,
            "concurrency": 20,
            "timeout_seconds": 30,
            "batch_size": 25,
            "feed_ids": ["f1", "f2"],
        }
        check_gtfs_feed_availability_handler(payload)
        mock_fn.assert_called_once_with(
            dry_run=False,
            skip_db_update=True,
            limit=5,
            concurrency=20,
            timeout_seconds=30,
            batch_size=25,
            feed_ids=["f1", "f2"],
        )


class TestGetFeedsQuery(unittest.TestCase):
    def test_query_applies_all_filters(self):
        db_session = MagicMock()
        query_mock = MagicMock()
        db_session.query.return_value = query_mock
        query_mock.filter.return_value = query_mock

        get_feeds_query(db_session)

        db_session.query.assert_called_once()
        query_mock.join.assert_not_called()
        query_mock.filter.assert_called_once()

    def test_feed_ids_adds_extra_filter(self):
        db_session = MagicMock()
        query_mock = MagicMock()
        db_session.query.return_value = query_mock
        query_mock.filter.return_value = query_mock

        get_feeds_query(db_session, feed_ids=["f1", "f2"])

        # filter called twice: once for base conditions, once for feed_ids
        self.assertEqual(query_mock.filter.call_count, 2)

    def test_no_feed_ids_does_not_add_extra_filter(self):
        db_session = MagicMock()
        query_mock = MagicMock()
        db_session.query.return_value = query_mock
        query_mock.filter.return_value = query_mock

        get_feeds_query(db_session, feed_ids=None)

        self.assertEqual(query_mock.filter.call_count, 1)


class TestPerformHeadRequest(unittest.TestCase):
    @patch("tasks.feed_availability.check_gtfs_feed_availability.requests.head")
    def test_success_response(self, mock_head):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response

        result = _perform_head_request("feed_1", "http://example.com/feed.zip", 10)

        self.assertTrue(result.success)
        self.assertEqual(result.status_code, 200)
        self.assertIsNotNone(result.latency_ms)
        self.assertIsNone(result.error_message)
        self.assertEqual(result.request_type, "http_head")
        self.assertEqual(result.feed_id, "feed_1")
        self.assertEqual(result.request_url, "http://example.com/feed.zip")

    @patch("tasks.feed_availability.check_gtfs_feed_availability.requests.head")
    def test_4xx_status_marks_failure(self, mock_head):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_head.return_value = mock_response

        result = _perform_head_request("feed_2", "http://example.com/missing.zip", 10)

        self.assertFalse(result.success)
        self.assertEqual(result.status_code, 404)
        self.assertIsNone(result.error_message)

    @patch("tasks.feed_availability.check_gtfs_feed_availability.requests.head")
    def test_timeout_records_error(self, mock_head):
        mock_head.side_effect = requests.exceptions.Timeout("timed out")

        result = _perform_head_request("feed_3", "http://slow.example.com/feed.zip", 5)

        self.assertFalse(result.success)
        self.assertIsNone(result.status_code)
        self.assertEqual(result.error_type, "Timeout")
        self.assertIn("timed out", result.error_message)

    @patch("tasks.feed_availability.check_gtfs_feed_availability.requests.head")
    def test_connection_error_records_error(self, mock_head):
        mock_head.side_effect = requests.exceptions.ConnectionError("refused")

        result = _perform_head_request("feed_4", "http://unreachable.example.com/", 10)

        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "ConnectionError")
        self.assertIsNotNone(result.error_message)


class TestCheckGtfsFeedAvailability(unittest.TestCase):
    def _make_mock_session(self, feeds):
        db_session = MagicMock()
        query_mock = MagicMock()
        query_mock.count.return_value = len(feeds)
        query_mock.all.return_value = feeds
        query_mock.limit.return_value = query_mock
        db_session.query.return_value = query_mock
        query_mock.filter.return_value = query_mock
        return db_session

    def test_dry_run_returns_count_without_http_calls(self):
        feeds = [_make_feed("f1", "http://a.com"), _make_feed("f2", "http://b.com")]
        db_session = self._make_mock_session(feeds)

        with patch(
            "tasks.feed_availability.check_gtfs_feed_availability._perform_head_request"
        ) as mock_head:
            result = check_gtfs_feed_availability(db_session=db_session, dry_run=True)

        mock_head.assert_not_called()
        db_session.add_all.assert_not_called()
        self.assertIn("Dry run", result["message"])
        self.assertEqual(result["total_feeds"], 2)

    @patch("tasks.feed_availability.check_gtfs_feed_availability.requests.head")
    def test_checks_all_feeds_and_stores_results(self, mock_head):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response

        feeds = [_make_feed("f1", "http://a.com"), _make_feed("f2", "http://b.com")]
        db_session = self._make_mock_session(feeds)

        result = check_gtfs_feed_availability(
            db_session=db_session, dry_run=False, skip_db_update=False
        )

        db_session.add_all.assert_called_once()
        db_session.commit.assert_called_once()
        self.assertEqual(result["total_feeds"], 2)
        self.assertEqual(result["succeeded"], 2)
        self.assertEqual(result["failed"], 0)

    @patch("tasks.feed_availability.check_gtfs_feed_availability.requests.head")
    def test_skip_db_update_does_not_write(self, mock_head):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response

        feeds = [_make_feed("f1", "http://a.com")]
        db_session = self._make_mock_session(feeds)

        result = check_gtfs_feed_availability(
            db_session=db_session, dry_run=False, skip_db_update=True
        )

        db_session.add_all.assert_not_called()
        db_session.commit.assert_not_called()
        self.assertTrue(result["skip_db_update"])
        self.assertEqual(result["total_feeds"], 1)

    @patch("tasks.feed_availability.check_gtfs_feed_availability.requests.head")
    def test_limit_caps_processed_feeds(self, mock_head):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response

        all_feeds = [_make_feed(f"f{i}", f"http://feed{i}.com") for i in range(10)]
        limited_feeds = all_feeds[:3]

        db_session = MagicMock()
        query_mock = MagicMock()
        limited_query_mock = MagicMock()
        limited_query_mock.all.return_value = limited_feeds
        query_mock.filter.return_value = query_mock
        query_mock.limit.return_value = limited_query_mock
        db_session.query.return_value = query_mock

        result = check_gtfs_feed_availability(
            db_session=db_session, dry_run=False, limit=3, skip_db_update=True
        )

        query_mock.limit.assert_called_once_with(3)
        self.assertEqual(result["total_feeds"], 3)

    def test_dry_run_with_limit_returns_limited_count(self):
        db_session = MagicMock()
        query_mock = MagicMock()
        limited_query_mock = MagicMock()
        limited_query_mock.count.return_value = 3
        query_mock.filter.return_value = query_mock
        query_mock.limit.return_value = limited_query_mock
        db_session.query.return_value = query_mock

        with patch(
            "tasks.feed_availability.check_gtfs_feed_availability._perform_head_request"
        ) as mock_head:
            result = check_gtfs_feed_availability(
                db_session=db_session, dry_run=True, limit=3
            )

        mock_head.assert_not_called()
        db_session.add_all.assert_not_called()
        query_mock.limit.assert_called_once_with(3)
        self.assertIn("Dry run", result["message"])
        self.assertEqual(result["total_feeds"], 3)

    @patch("tasks.feed_availability.check_gtfs_feed_availability.requests.head")
    def test_failed_feeds_counted_correctly(self, mock_head):
        def side_effect(url, **kwargs):
            if "fail" in url:
                raise requests.exceptions.ConnectionError("refused")
            r = MagicMock()
            r.status_code = 200
            return r

        mock_head.side_effect = side_effect

        feeds = [
            _make_feed("f1", "http://ok.com"),
            _make_feed("f2", "http://fail.com"),
        ]
        db_session = self._make_mock_session(feeds)

        result = check_gtfs_feed_availability(
            db_session=db_session, dry_run=False, skip_db_update=True
        )

        self.assertEqual(result["total_feeds"], 2)
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["failed"], 1)

    @patch("tasks.feed_availability.check_gtfs_feed_availability.requests.head")
    def test_commits_once_per_batch(self, mock_head):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response

        feeds = [_make_feed(f"f{i}", f"http://feed{i}.com") for i in range(6)]
        db_session = self._make_mock_session(feeds)

        check_gtfs_feed_availability(
            db_session=db_session, dry_run=False, skip_db_update=False, batch_size=2
        )

        # 6 feeds / batch_size=2 → 3 commits
        self.assertEqual(db_session.commit.call_count, 3)
        self.assertEqual(db_session.add_all.call_count, 3)

    @patch("tasks.feed_availability.check_gtfs_feed_availability.requests.head")
    def test_future_exception_captured_as_failed_check(self, mock_head):
        mock_head.side_effect = RuntimeError("unexpected failure")

        feeds = [_make_feed("f1", "http://a.com")]
        db_session = self._make_mock_session(feeds)

        result = check_gtfs_feed_availability(
            db_session=db_session, dry_run=False, skip_db_update=True
        )

        self.assertEqual(result["total_feeds"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["succeeded"], 0)

    @patch("tasks.feed_availability.check_gtfs_feed_availability.requests.head")
    def test_feed_ids_filters_query(self, mock_head):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response

        feeds = [_make_feed("f1", "http://a.com"), _make_feed("f2", "http://b.com")]
        db_session = self._make_mock_session(feeds)

        check_gtfs_feed_availability(
            db_session=db_session,
            dry_run=False,
            skip_db_update=True,
            feed_ids=["f1", "f2"],
        )

        # filter should have been called twice: base conditions + feed_ids
        self.assertEqual(db_session.query().filter.call_count, 2)


if __name__ == "__main__":
    unittest.main()
