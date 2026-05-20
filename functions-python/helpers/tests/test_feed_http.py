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
import ssl
import unittest
from unittest.mock import MagicMock, patch

import urllib3.exceptions

from utils import (
    create_feed_ssl_context,
    build_feed_request_params,
    perform_request,
)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Mobile Safari/537.36"
)


class TestCreateFeedSslContext(unittest.TestCase):
    def test_returns_ssl_context(self):
        ctx = create_feed_ssl_context()
        self.assertIsNotNone(ctx)

    def test_legacy_server_connect_flag_is_set(self):
        ctx = create_feed_ssl_context()
        # ssl.OP_LEGACY_SERVER_CONNECT == 0x4
        self.assertTrue(ctx.options & 0x4)

    def test_default_verifies_certs(self):
        ctx = create_feed_ssl_context(trusted_certs=False)
        self.assertTrue(ctx.check_hostname)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)

    def test_trusted_certs_disables_verification(self):
        ctx = create_feed_ssl_context(trusted_certs=True)
        self.assertFalse(ctx.check_hostname)
        self.assertEqual(ctx.verify_mode, ssl.CERT_NONE)


class TestBuildFeedRequestParams(unittest.TestCase):
    @patch("shared.common.config_reader.get_config_value", return_value=None)
    def test_default_headers_include_user_agent_and_referer(self, _):
        headers, url = build_feed_request_params("http://example.com/feed.zip")
        self.assertEqual(headers["User-Agent"], DEFAULT_USER_AGENT)
        self.assertEqual(headers["Referer"], "http://example.com/feed.zip")
        self.assertEqual(url, "http://example.com/feed.zip")

    @patch("shared.common.config_reader.get_config_value", return_value=None)
    def test_auth_type_0_does_not_modify_url_or_headers(self, _):
        headers, url = build_feed_request_params(
            "http://example.com/feed.zip",
            authentication_type="0",
            api_key_parameter_name="key",
            credentials="secret",
        )
        self.assertNotIn("key", url)
        self.assertNotIn("key", headers)

    @patch("shared.common.config_reader.get_config_value", return_value=None)
    def test_auth_type_1_appends_credential_to_url(self, _):
        _, url = build_feed_request_params(
            "http://example.com/feed.zip",
            authentication_type="1",
            api_key_parameter_name="api_key",
            credentials="mysecret",
        )
        self.assertIn("api_key=mysecret", url)
        self.assertTrue(url.startswith("http://example.com/feed.zip?"))

    @patch("shared.common.config_reader.get_config_value", return_value=None)
    def test_auth_type_1_uses_ampersand_when_url_has_query(self, _):
        _, url = build_feed_request_params(
            "http://example.com/feed.zip?operator=CE",
            authentication_type="1",
            api_key_parameter_name="api_key",
            credentials="mysecret",
        )
        self.assertIn("&api_key=mysecret", url)

    @patch("shared.common.config_reader.get_config_value", return_value=None)
    def test_auth_type_2_injects_credential_as_header(self, _):
        headers, url = build_feed_request_params(
            "http://example.com/feed.zip",
            authentication_type="2",
            api_key_parameter_name="X-API-Key",
            credentials="token123",
        )
        self.assertEqual(headers["X-API-Key"], "token123")
        self.assertEqual(url, "http://example.com/feed.zip")

    @patch(
        "shared.common.config_reader.get_config_value",
        return_value={"User-Agent": "CustomAgent/1.0"},
    )
    def test_custom_headers_from_config_override_default(self, _):
        headers, _ = build_feed_request_params("http://example.com/feed.zip")
        self.assertEqual(headers["User-Agent"], "CustomAgent/1.0")
        self.assertNotIn("Referer", headers)

    @patch("shared.common.config_reader.get_config_value", return_value=None)
    def test_none_authentication_type_treated_as_zero(self, _):
        headers, url = build_feed_request_params(
            "http://example.com/feed.zip",
            authentication_type=None,
            api_key_parameter_name="api_key",
            credentials="secret",
        )
        self.assertNotIn("api_key", url)
        self.assertNotIn("api_key", headers)


class TestPerformRequest(unittest.TestCase):
    def _mock_pool(self, status=200, side_effect=None):
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
            patch("utils.urllib3.PoolManager", return_value=mock_pool_instance),
            mock_pool_instance,
        )

    def _call(
        self,
        feed_id="feed_1",
        stable_id="mdb-1",
        url="http://example.com/feed.zip",
        **kwargs
    ):
        return perform_request(
            feed_id,
            stable_id,
            url,
            kwargs.get("authentication_type", "0"),
            kwargs.get("api_key_parameter_name", None),
            kwargs.get("credentials", None),
            kwargs.get("timeout_seconds", 10),
            kwargs.get("fallback_to_get", False),
        )

    @patch("utils.build_feed_request_params")
    @patch("utils.create_feed_ssl_context")
    def test_success_200_sets_success_true(self, mock_ssl, mock_params):
        mock_params.return_value = ({}, "http://example.com/feed.zip")
        pool_patch, _ = self._mock_pool(status=200)
        with pool_patch:
            result = self._call()
        self.assertTrue(result.success)
        self.assertEqual(result.status_code, 200)
        self.assertIsNotNone(result.latency_ms)
        self.assertIsNone(result.error_message)
        self.assertIsNone(result.error_type)

    @patch("utils.build_feed_request_params")
    @patch("utils.create_feed_ssl_context")
    def test_4xx_response_sets_success_false(self, mock_ssl, mock_params):
        mock_params.return_value = ({}, "http://example.com/feed.zip")
        pool_patch, _ = self._mock_pool(status=404)
        with pool_patch:
            result = self._call()
        self.assertFalse(result.success)
        self.assertEqual(result.status_code, 404)
        self.assertIsNone(result.error_message)

    @patch("utils.build_feed_request_params")
    @patch("utils.create_feed_ssl_context")
    def test_request_url_is_original_not_resolved(self, mock_ssl, mock_params):
        """Credentials must not be stored — request_url is the original producer_url."""
        mock_params.return_value = ({}, "http://example.com/feed.zip?api_key=secret")
        pool_patch, _ = self._mock_pool(status=200)
        with pool_patch:
            result = self._call(url="http://example.com/feed.zip")
        self.assertEqual(result.request_url, "http://example.com/feed.zip")

    @patch("utils.build_feed_request_params")
    @patch("utils.create_feed_ssl_context")
    def test_timeout_error_sets_error_type(self, mock_ssl, mock_params):
        mock_params.return_value = ({}, "http://slow.example.com/feed.zip")
        pool_patch, _ = self._mock_pool(
            side_effect=urllib3.exceptions.TimeoutError("timed out")
        )
        with pool_patch:
            result = self._call(url="http://slow.example.com/feed.zip")
        self.assertFalse(result.success)
        self.assertIsNone(result.status_code)
        self.assertEqual(result.error_type, "Timeout")
        self.assertIn("timed out", result.error_message)

    @patch("utils.build_feed_request_params")
    @patch("utils.create_feed_ssl_context")
    def test_connection_error_sets_error_type(self, mock_ssl, mock_params):
        mock_params.return_value = ({}, "http://unreachable.example.com/")
        pool_patch, _ = self._mock_pool(
            side_effect=urllib3.exceptions.MaxRetryError(
                pool=None, url="http://unreachable.example.com/", reason="refused"
            )
        )
        with pool_patch:
            result = self._call(url="http://unreachable.example.com/")
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "ConnectionError")
        self.assertIsNotNone(result.error_message)

    @patch("utils.build_feed_request_params")
    @patch("utils.create_feed_ssl_context")
    def test_generic_http_error_uses_class_name(self, mock_ssl, mock_params):
        mock_params.return_value = ({}, "http://example.com/feed.zip")
        pool_patch, _ = self._mock_pool(
            side_effect=urllib3.exceptions.HTTPError("generic error")
        )
        with pool_patch:
            result = self._call()
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "HTTPError")
        self.assertIn("generic error", result.error_message)

    @patch("utils.build_feed_request_params")
    @patch("utils.create_feed_ssl_context")
    def test_feed_id_and_checked_at_stored_in_result(self, mock_ssl, mock_params):
        mock_params.return_value = ({}, "http://example.com/feed.zip")
        pool_patch, _ = self._mock_pool(status=200)
        with pool_patch:
            result = self._call(feed_id="mdb-42")
        self.assertEqual(result.feed_id, "mdb-42")
        self.assertIsNotNone(result.checked_at)

    @patch("utils.build_feed_request_params")
    @patch("utils.create_feed_ssl_context")
    def test_content_type_extracted_from_head_response(self, mock_ssl, mock_params):
        mock_params.return_value = ({}, "http://example.com/feed.zip")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.headers = {"Content-Type": "application/zip; charset=utf-8"}
        pool_patch, mock_pool = self._mock_pool(status=200)
        mock_pool.request.return_value = mock_resp
        with pool_patch:
            result = self._call()
        self.assertEqual(result.content_type, "application/zip")
        self.assertTrue(result.is_zip)

    @patch("utils.build_feed_request_params")
    @patch("utils.create_feed_ssl_context")
    def test_non_zip_content_type_sets_is_zip_false(self, mock_ssl, mock_params):
        mock_params.return_value = ({}, "http://example.com/feed")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.headers = {"Content-Type": "text/html"}
        pool_patch, mock_pool = self._mock_pool(status=200)
        mock_pool.request.return_value = mock_resp
        with pool_patch:
            result = self._call()
        self.assertEqual(result.content_type, "text/html")
        self.assertFalse(result.is_zip)

    @patch("utils.build_feed_request_params")
    @patch("utils.create_feed_ssl_context")
    def test_octet_stream_content_type_sets_is_zip_none(self, mock_ssl, mock_params):
        """application/octet-stream is ambiguous — is_zip stays None until magic bytes check."""
        mock_params.return_value = ({}, "http://example.com/feed.zip")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.headers = {"Content-Type": "application/octet-stream"}
        pool_patch, mock_pool = self._mock_pool(status=200)
        mock_pool.request.return_value = mock_resp
        with pool_patch:
            result = self._call()
        self.assertEqual(result.content_type, "application/octet-stream")
        self.assertIsNone(result.is_zip)

    @patch("utils.build_feed_request_params")
    @patch("utils.create_feed_ssl_context")
    def test_fallback_to_get_on_head_failure_sets_http_get_type(
        self, mock_ssl, mock_params
    ):
        """When HEAD fails and fallback_to_get=True, GET is used and request_type=http_get."""
        mock_params.return_value = ({}, "http://example.com/feed.zip")

        # HEAD returns 405, GET returns 200 with ZIP magic bytes
        head_resp = MagicMock()
        head_resp.status = 405
        head_resp.headers = {}

        get_resp = MagicMock()
        get_resp.status = 200
        get_resp.headers = {"Content-Type": "application/zip"}
        get_resp.read.return_value = b"\x50\x4b\x03\x04"

        call_count = {"n": 0}

        def request_side_effect(method, *args, **kwargs):
            call_count["n"] += 1
            if method == "HEAD":
                return head_resp
            return get_resp

        mock_pool_instance = MagicMock()
        mock_pool_instance.request.side_effect = request_side_effect
        mock_pool_instance.__enter__ = lambda s: mock_pool_instance
        mock_pool_instance.__exit__ = MagicMock(return_value=False)

        with patch("utils.urllib3.PoolManager", return_value=mock_pool_instance):
            result = self._call(fallback_to_get=True)

        self.assertTrue(result.success)
        self.assertEqual(result.request_type, "http_get")
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_zip)
        self.assertEqual(call_count["n"], 2)

    @patch("utils.build_feed_request_params")
    @patch("utils.create_feed_ssl_context")
    def test_fallback_to_get_false_does_not_retry(self, mock_ssl, mock_params):
        """When fallback_to_get=False, HEAD failure is final — no GET attempt."""
        mock_params.return_value = ({}, "http://example.com/feed.zip")

        head_resp = MagicMock()
        head_resp.status = 405
        head_resp.headers = {}

        call_count = {"n": 0}

        def request_side_effect(method, *args, **kwargs):
            call_count["n"] += 1
            return head_resp

        mock_pool_instance = MagicMock()
        mock_pool_instance.request.side_effect = request_side_effect
        mock_pool_instance.__enter__ = lambda s: mock_pool_instance
        mock_pool_instance.__exit__ = MagicMock(return_value=False)

        with patch("utils.urllib3.PoolManager", return_value=mock_pool_instance):
            result = self._call(fallback_to_get=False)

        self.assertFalse(result.success)
        self.assertEqual(result.request_type, "http_head")
        self.assertEqual(call_count["n"], 1)

    @patch("utils.build_feed_request_params")
    @patch("utils.create_feed_ssl_context")
    def test_fallback_get_uses_magic_bytes_for_is_zip(self, mock_ssl, mock_params):
        """is_zip is True when GET response starts with ZIP magic bytes PK\\x03\\x04."""
        mock_params.return_value = ({}, "http://example.com/feed.zip")

        head_resp = MagicMock()
        head_resp.status = 405
        head_resp.headers = {}

        get_resp = MagicMock()
        get_resp.status = 200
        get_resp.headers = {"Content-Type": "application/octet-stream"}
        get_resp.read.return_value = b"\x50\x4b\x03\x04"  # ZIP magic

        def request_side_effect(method, *args, **kwargs):
            return head_resp if method == "HEAD" else get_resp

        mock_pool_instance = MagicMock()
        mock_pool_instance.request.side_effect = request_side_effect
        mock_pool_instance.__enter__ = lambda s: mock_pool_instance
        mock_pool_instance.__exit__ = MagicMock(return_value=False)

        with patch("utils.urllib3.PoolManager", return_value=mock_pool_instance):
            result = self._call(fallback_to_get=True)

        self.assertTrue(result.is_zip)

    @patch("utils.build_feed_request_params")
    @patch("utils.create_feed_ssl_context")
    def test_fallback_get_non_zip_magic_bytes_sets_is_zip_false(
        self, mock_ssl, mock_params
    ):
        """is_zip is False when GET response does not start with ZIP magic bytes."""
        mock_params.return_value = ({}, "http://example.com/feed")

        head_resp = MagicMock()
        head_resp.status = 405
        head_resp.headers = {}

        get_resp = MagicMock()
        get_resp.status = 200
        get_resp.headers = {"Content-Type": "text/html"}
        get_resp.read.return_value = b"<htm"

        def request_side_effect(method, *args, **kwargs):
            return head_resp if method == "HEAD" else get_resp

        mock_pool_instance = MagicMock()
        mock_pool_instance.request.side_effect = request_side_effect
        mock_pool_instance.__enter__ = lambda s: mock_pool_instance
        mock_pool_instance.__exit__ = MagicMock(return_value=False)

        with patch("utils.urllib3.PoolManager", return_value=mock_pool_instance):
            result = self._call(fallback_to_get=True)

        self.assertFalse(result.is_zip)

    @patch("utils.build_feed_request_params")
    @patch("utils.create_feed_ssl_context")
    def test_head_success_does_not_trigger_fallback(self, mock_ssl, mock_params):
        """When HEAD succeeds, no GET fallback should happen."""
        mock_params.return_value = ({}, "http://example.com/feed.zip")

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.headers = {"Content-Type": "application/zip"}

        call_count = {"n": 0}

        def request_side_effect(method, *args, **kwargs):
            call_count["n"] += 1
            return mock_resp

        mock_pool_instance = MagicMock()
        mock_pool_instance.request.side_effect = request_side_effect
        mock_pool_instance.__enter__ = lambda s: mock_pool_instance
        mock_pool_instance.__exit__ = MagicMock(return_value=False)

        with patch("utils.urllib3.PoolManager", return_value=mock_pool_instance):
            result = self._call(fallback_to_get=True)

        self.assertTrue(result.success)
        self.assertEqual(result.request_type, "http_head")
        self.assertEqual(call_count["n"], 1)


class TestIsZipFromContentType(unittest.TestCase):
    def test_application_zip_returns_true(self):
        from utils import _is_zip_from_content_type

        self.assertTrue(_is_zip_from_content_type("application/zip"))

    def test_gtfs_zip_returns_true(self):
        from utils import _is_zip_from_content_type

        self.assertTrue(_is_zip_from_content_type("application/gtfs+zip"))

    def test_text_html_returns_false(self):
        from utils import _is_zip_from_content_type

        self.assertFalse(_is_zip_from_content_type("text/html"))

    def test_octet_stream_returns_none(self):
        from utils import _is_zip_from_content_type

        self.assertIsNone(_is_zip_from_content_type("application/octet-stream"))

    def test_none_returns_none(self):
        from utils import _is_zip_from_content_type

        self.assertIsNone(_is_zip_from_content_type(None))


if __name__ == "__main__":
    unittest.main()
