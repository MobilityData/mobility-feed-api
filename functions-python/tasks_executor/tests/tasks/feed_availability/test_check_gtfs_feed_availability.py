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

import urllib3.exceptions

from shared.helpers.utils import perform_request
from tasks.feed_availability.check_gtfs_feed_availability import (
    check_gtfs_feed_availability,
    check_gtfs_feed_availability_handler,
    get_feeds_query,
    get_feed_credentials,
)


def _make_feed(
    feed_id: str,
    producer_url: str,
    stable_id: str = None,
    authentication_type: str = "0",
    api_key_parameter_name: str = None,
):
    feed = MagicMock()
    feed.id = feed_id
    feed.stable_id = stable_id or feed_id
    feed.producer_url = producer_url
    feed.authentication_type = authentication_type
    feed.api_key_parameter_name = api_key_parameter_name
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
            concurrency=15,
            timeout_seconds=20,
            batch_size=50,
            stable_feed_ids=None,
            verbose=False,
            fallback_to_get=True,
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
            "stable_feed_ids": ["f1", "f2"],
            "verbose": True,
            "fallback_to_get": False,
        }
        check_gtfs_feed_availability_handler(payload)
        mock_fn.assert_called_once_with(
            dry_run=False,
            skip_db_update=True,
            limit=5,
            concurrency=20,
            timeout_seconds=30,
            batch_size=25,
            stable_feed_ids=["f1", "f2"],
            verbose=True,
            fallback_to_get=False,
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

    def test_stable_feed_ids_adds_extra_filter(self):
        db_session = MagicMock()
        query_mock = MagicMock()
        db_session.query.return_value = query_mock
        query_mock.filter.return_value = query_mock

        get_feeds_query(db_session, stable_feed_ids=["f1", "f2"])

        # filter called twice: once for base conditions, once for stable_feed_ids
        self.assertEqual(query_mock.filter.call_count, 2)

    def test_no_stable_feed_ids_does_not_add_extra_filter(self):
        db_session = MagicMock()
        query_mock = MagicMock()
        db_session.query.return_value = query_mock
        query_mock.filter.return_value = query_mock

        get_feeds_query(db_session, stable_feed_ids=None)

        self.assertEqual(query_mock.filter.call_count, 1)


class TestPerformRequest(unittest.TestCase):
    def _call(
        self,
        feed_id,
        url,
        timeout=10,
        stable_id=None,
        auth_type="0",
        api_key_param=None,
        credentials=None,
    ):
        return perform_request(
            feed_id,
            stable_id or feed_id,
            url,
            auth_type,
            api_key_param,
            credentials,
            timeout,
        )

    def _mock_pool(self, status=200, side_effect=None):
        """Return a patcher for urllib3.PoolManager that yields a mock response."""
        mock_resp = MagicMock()
        mock_resp.status = status
        mock_pool_instance = MagicMock()
        if side_effect:
            mock_pool_instance.request.side_effect = side_effect
        else:
            mock_pool_instance.request.return_value = mock_resp
        mock_pool_instance.__enter__ = lambda s: mock_pool_instance
        mock_pool_instance.__exit__ = MagicMock(return_value=False)
        return (
            patch(
                "shared.helpers.utils.urllib3.PoolManager",
                return_value=mock_pool_instance,
            ),
            mock_pool_instance,
        )

    @patch("shared.helpers.utils.build_feed_request_params")
    @patch("shared.helpers.utils.create_feed_ssl_context")
    def test_success_response(self, mock_ssl, mock_params):
        mock_params.return_value = ({}, "http://example.com/feed.zip")
        pool_patch, mock_pool = self._mock_pool(status=200)
        with pool_patch:
            result = self._call("feed_1", "http://example.com/feed.zip")

        self.assertTrue(result.success)
        self.assertEqual(result.status_code, 200)
        self.assertIsNotNone(result.latency_ms)
        self.assertIsNone(result.error_message)
        self.assertEqual(result.request_type, "http_head")
        self.assertEqual(result.feed_id, "feed_1")
        self.assertEqual(result.request_url, "http://example.com/feed.zip")

    @patch("shared.helpers.utils.build_feed_request_params")
    @patch("shared.helpers.utils.create_feed_ssl_context")
    def test_4xx_status_marks_failure(self, mock_ssl, mock_params):
        mock_params.return_value = ({}, "http://example.com/missing.zip")
        pool_patch, _ = self._mock_pool(status=404)
        with pool_patch:
            result = self._call("feed_2", "http://example.com/missing.zip")

        self.assertFalse(result.success)
        self.assertEqual(result.status_code, 404)
        self.assertIsNone(result.error_message)

    @patch("shared.helpers.utils.build_feed_request_params")
    @patch("shared.helpers.utils.create_feed_ssl_context")
    def test_timeout_records_error(self, mock_ssl, mock_params):
        mock_params.return_value = ({}, "http://slow.example.com/feed.zip")
        pool_patch, _ = self._mock_pool(
            side_effect=urllib3.exceptions.TimeoutError("timed out")
        )
        with pool_patch:
            result = self._call("feed_3", "http://slow.example.com/feed.zip", timeout=5)

        self.assertFalse(result.success)
        self.assertIsNone(result.status_code)
        self.assertEqual(result.error_type, "Timeout")
        self.assertIn("timed out", result.error_message)

    @patch("shared.helpers.utils.build_feed_request_params")
    @patch("shared.helpers.utils.create_feed_ssl_context")
    def test_connection_error_records_error(self, mock_ssl, mock_params):
        mock_params.return_value = ({}, "http://unreachable.example.com/")
        pool_patch, _ = self._mock_pool(
            side_effect=urllib3.exceptions.MaxRetryError(
                pool=None, url="http://unreachable.example.com/", reason="refused"
            )
        )
        with pool_patch:
            result = self._call("feed_4", "http://unreachable.example.com/")

        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "ConnectionError")
        self.assertIsNotNone(result.error_message)

    @patch("shared.helpers.utils.build_feed_request_params")
    @patch("shared.helpers.utils.create_feed_ssl_context")
    def test_auth_type1_url_passed_to_build_params(self, mock_ssl, mock_params):
        """build_feed_request_params receives auth type 1 args correctly."""
        mock_params.return_value = ({}, "http://example.com/feed.zip?api_key=secret")
        pool_patch, _ = self._mock_pool(status=200)
        with pool_patch:
            self._call(
                "feed_5",
                "http://example.com/feed.zip",
                auth_type="1",
                api_key_param="api_key",
                credentials="secret",
            )

        mock_params.assert_called_once_with(
            "http://example.com/feed.zip",
            feed_id="feed_5",
            authentication_type="1",
            api_key_parameter_name="api_key",
            credentials="secret",
        )

    @patch("shared.helpers.utils.build_feed_request_params")
    @patch("shared.helpers.utils.create_feed_ssl_context")
    def test_auth_type2_header_passed_to_build_params(self, mock_ssl, mock_params):
        """build_feed_request_params receives auth type 2 args correctly."""
        mock_params.return_value = (
            {"X-API-Key": "token"},
            "http://example.com/feed.zip",
        )
        pool_patch, mock_pool = self._mock_pool(status=200)
        with pool_patch:
            self._call(
                "feed_6",
                "http://example.com/feed.zip",
                auth_type="2",
                api_key_param="X-API-Key",
                credentials="token",
            )

        mock_params.assert_called_once_with(
            "http://example.com/feed.zip",
            feed_id="feed_6",
            authentication_type="2",
            api_key_parameter_name="X-API-Key",
            credentials="token",
        )
        _, call_kwargs = mock_pool.request.call_args
        self.assertEqual(call_kwargs["headers"], {"X-API-Key": "token"})


class TestGetFeedCredentials(unittest.TestCase):
    @patch.dict("os.environ", {"FEEDS_CREDENTIALS": '{"mdb-123": "secret_key"}'})
    def test_returns_credential_for_known_stable_id(self):
        self.assertEqual(get_feed_credentials("mdb-123"), "secret_key")

    @patch.dict("os.environ", {"FEEDS_CREDENTIALS": '{"mdb-123": "secret_key"}'})
    def test_returns_none_for_unknown_stable_id(self):
        self.assertIsNone(get_feed_credentials("mdb-999"))

    @patch.dict("os.environ", {}, clear=True)
    def test_returns_none_when_env_not_set(self):
        self.assertIsNone(get_feed_credentials("mdb-123"))

    @patch.dict("os.environ", {"FEEDS_CREDENTIALS": "not-valid-json"})
    def test_returns_none_on_invalid_json(self):
        self.assertIsNone(get_feed_credentials("mdb-123"))


class TestCheckGtfsFeedAvailability(unittest.TestCase):
    def setUp(self):
        self._mock_check = MagicMock()
        self._mock_check.success = True
        self._mock_check.status_code = 200
        self._mock_check.error_type = None
        self._mock_check.error_message = None

        head_patcher = patch(
            "tasks.feed_availability.check_gtfs_feed_availability.perform_request",
            return_value=self._mock_check,
        )
        self.mock_perform_head = head_patcher.start()
        self.addCleanup(head_patcher.stop)

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

        result = check_gtfs_feed_availability(db_session=db_session, dry_run=True)

        self.mock_perform_head.assert_not_called()
        db_session.add_all.assert_not_called()
        self.assertIn("Dry run", result["message"])
        self.assertEqual(result["total_feeds"], 2)
        self.assertIn("elapsed_seconds", result)

    def test_checks_all_feeds_and_stores_results(self):
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
        self.assertIn("elapsed_seconds", result)

    def test_skip_db_update_does_not_write(self):
        feeds = [_make_feed("f1", "http://a.com")]
        db_session = self._make_mock_session(feeds)

        result = check_gtfs_feed_availability(
            db_session=db_session, dry_run=False, skip_db_update=True
        )

        db_session.add_all.assert_not_called()
        db_session.commit.assert_not_called()
        self.assertTrue(result["skip_db_update"])
        self.assertEqual(result["total_feeds"], 1)
        self.assertIn("elapsed_seconds", result)

    def test_limit_caps_processed_feeds(self):
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

        result = check_gtfs_feed_availability(
            db_session=db_session, dry_run=True, limit=3
        )

        self.mock_perform_head.assert_not_called()
        db_session.add_all.assert_not_called()
        query_mock.limit.assert_called_once_with(3)
        self.assertIn("Dry run", result["message"])
        self.assertEqual(result["total_feeds"], 3)
        self.assertIn("elapsed_seconds", result)

    def test_failed_feeds_counted_correctly(self):
        feeds = [
            _make_feed("f1", "http://ok.com"),
            _make_feed("f2", "http://fail.com"),
        ]
        db_session = self._make_mock_session(feeds)

        def head_side_effect(feed_id, stable_id, url, *args, **kwargs):
            check = MagicMock()
            check.success = "fail" not in url
            check.status_code = None if "fail" in url else 200
            check.error_type = "ConnectionError" if "fail" in url else None
            check.error_message = "refused" if "fail" in url else None
            return check

        self.mock_perform_head.side_effect = head_side_effect

        result = check_gtfs_feed_availability(
            db_session=db_session, dry_run=False, skip_db_update=True
        )

        self.assertEqual(result["total_feeds"], 2)
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["failed"], 1)

    def test_commits_once_per_batch(self):
        feeds = [_make_feed(f"f{i}", f"http://feed{i}.com") for i in range(6)]
        db_session = self._make_mock_session(feeds)

        check_gtfs_feed_availability(
            db_session=db_session, dry_run=False, skip_db_update=False, batch_size=2
        )

        # 6 feeds / batch_size=2 → 3 commits
        self.assertEqual(db_session.commit.call_count, 3)
        self.assertEqual(db_session.add_all.call_count, 3)

    def test_future_exception_captured_as_failed_check(self):
        self.mock_perform_head.side_effect = RuntimeError("unexpected failure")

        feeds = [_make_feed("f1", "http://a.com")]
        db_session = self._make_mock_session(feeds)

        result = check_gtfs_feed_availability(
            db_session=db_session, dry_run=False, skip_db_update=True
        )

        self.assertEqual(result["total_feeds"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["succeeded"], 0)

    def test_stable_feed_ids_filters_query(self):
        feeds = [
            _make_feed("f1", "http://a.com", stable_id="mdb-1"),
            _make_feed("f2", "http://b.com", stable_id="mdb-2"),
        ]
        db_session = self._make_mock_session(feeds)

        check_gtfs_feed_availability(
            db_session=db_session,
            dry_run=False,
            skip_db_update=True,
            stable_feed_ids=["mdb-1", "mdb-2"],
        )

        # filter should have been called twice: base conditions + stable_feed_ids
        self.assertEqual(db_session.query().filter.call_count, 2)

    def test_stable_feed_ids_raises_on_missing_ids(self):
        feeds = [_make_feed("f1", "http://a.com", stable_id="mdb-1")]
        db_session = self._make_mock_session(feeds)

        with self.assertRaises(ValueError) as ctx:
            check_gtfs_feed_availability(
                db_session=db_session,
                dry_run=False,
                skip_db_update=True,
                stable_feed_ids=["mdb-1", "mdb-999", "mdb-888"],
            )
        self.assertIn("mdb-999", str(ctx.exception))
        self.assertIn("mdb-888", str(ctx.exception))

    def test_verbose_false_omits_failures_key(self):
        feeds = [_make_feed("f1", "http://a.com")]
        db_session = self._make_mock_session(feeds)

        result = check_gtfs_feed_availability(
            db_session=db_session, dry_run=False, skip_db_update=True, verbose=False
        )

        self.assertNotIn("failures", result)

    def test_verbose_true_includes_failures_with_stable_id_and_reason(self):
        feeds = [
            _make_feed("f1", "http://ok.com", stable_id="mdb-1"),
            _make_feed("f2", "http://fail.com", stable_id="mdb-2"),
        ]
        db_session = self._make_mock_session(feeds)

        def head_side_effect(feed_id, stable_id, url, *args, **kwargs):
            check = MagicMock()
            check.success = "fail" not in url
            check.feed_id = feed_id
            check.status_code = None if "fail" in url else 200
            check.error_type = "ConnectionError" if "fail" in url else None
            check.error_message = "Max retries exceeded" if "fail" in url else None
            check.content_type = None
            check.is_zip = None
            return check

        self.mock_perform_head.side_effect = head_side_effect

        result = check_gtfs_feed_availability(
            db_session=db_session, dry_run=False, skip_db_update=True, verbose=True
        )

        self.assertIn("failures", result)
        self.assertEqual(len(result["failures"]), 1)
        failure = result["failures"][0]
        self.assertEqual(failure["stable_id"], "mdb-2")
        self.assertEqual(failure["error_type"], "ConnectionError")
        self.assertEqual(failure["reason"], "Max retries exceeded")
        self.assertIn("content_type", failure)
        self.assertIn("is_zip", failure)

    def test_verbose_true_includes_content_type_and_is_zip(self):
        feeds = [_make_feed("f1", "http://fail.com", stable_id="mdb-1")]
        db_session = self._make_mock_session(feeds)

        failed_check = MagicMock()
        failed_check.success = False
        failed_check.feed_id = "f1"
        failed_check.status_code = 405
        failed_check.error_type = None
        failed_check.error_message = None
        failed_check.content_type = "application/zip"
        failed_check.is_zip = True
        self.mock_perform_head.return_value = failed_check

        result = check_gtfs_feed_availability(
            db_session=db_session, dry_run=False, skip_db_update=True, verbose=True
        )

        failure = result["failures"][0]
        self.assertEqual(failure["content_type"], "application/zip")
        self.assertTrue(failure["is_zip"])

    def test_verbose_true_uses_http_status_as_reason_when_no_error_message(self):
        feeds = [_make_feed("f1", "http://a.com", stable_id="mdb-1")]
        db_session = self._make_mock_session(feeds)

        failed_check = MagicMock()
        failed_check.success = False
        failed_check.feed_id = "f1"
        failed_check.status_code = 404
        failed_check.error_type = None
        failed_check.error_message = None
        failed_check.content_type = None
        failed_check.is_zip = None
        self.mock_perform_head.return_value = failed_check

        result = check_gtfs_feed_availability(
            db_session=db_session, dry_run=False, skip_db_update=True, verbose=True
        )

        self.assertEqual(len(result["failures"]), 1)
        self.assertEqual(result["failures"][0]["reason"], "HTTP 404")
        self.assertEqual(result["failures"][0]["stable_id"], "mdb-1")

    def test_fallback_to_get_passed_to_perform_request(self):
        feeds = [_make_feed("f1", "http://a.com", stable_id="mdb-1")]
        db_session = self._make_mock_session(feeds)

        check_gtfs_feed_availability(
            db_session=db_session,
            dry_run=False,
            skip_db_update=True,
            fallback_to_get=False,
        )

        call_args = self.mock_perform_head.call_args[0]
        self.assertIn(False, call_args)  # fallback_to_get=False should be in the args


if __name__ == "__main__":
    unittest.main()
