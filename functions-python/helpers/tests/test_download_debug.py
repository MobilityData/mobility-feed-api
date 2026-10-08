import os
import unittest
from unittest.mock import MagicMock, patch

import pytest

import utils
from utils import (
    REDACTED,
    FeedDownloadError,
    FeedRequestDiagnostics,
    build_availability_check,
    download_feed,
    get_external_ip,
    sanitize_headers,
    sanitize_url,
)


class TestSanitizeHeaders(unittest.TestCase):
    def test_redacts_known_secret_headers(self):
        result = sanitize_headers(
            {
                "User-Agent": "agent",
                "Authorization": "Bearer abc",
                "Cookie": "session=1",
                "X-Api-Key": "secret",
            }
        )
        self.assertEqual(result["User-Agent"], "agent")
        self.assertEqual(result["Authorization"], REDACTED)
        self.assertEqual(result["Cookie"], REDACTED)
        self.assertEqual(result["X-Api-Key"], REDACTED)

    def test_redacts_api_key_parameter_name_header(self):
        result = sanitize_headers(
            {"User-Agent": "agent", "my-feed-token": "secret"},
            api_key_parameter_name="my-feed-token",
        )
        self.assertEqual(result["my-feed-token"], REDACTED)
        self.assertEqual(result["User-Agent"], "agent")

    def test_header_names_are_preserved(self):
        result = sanitize_headers({"Authorization": "Bearer abc"})
        self.assertIn("Authorization", result)

    def test_none_returns_none(self):
        self.assertIsNone(sanitize_headers(None))


class TestSanitizeUrl(unittest.TestCase):
    def test_redacts_api_key_query_parameter(self):
        result = sanitize_url(
            "https://example.com/gtfs.zip?operator=CE&token=secret",
            api_key_parameter_name="token",
        )
        self.assertIn("operator=CE", result)
        self.assertNotIn("secret", result)

    def test_redacts_known_secret_query_parameters(self):
        result = sanitize_url("https://example.com/gtfs.zip?api_key=secret&x=1")
        self.assertIn("x=1", result)
        self.assertNotIn("secret", result)

    def test_strips_userinfo(self):
        result = sanitize_url("https://user:password@example.com/gtfs.zip")
        self.assertNotIn("password", result)
        self.assertIn("example.com", result)

    def test_url_without_credentials_is_unchanged(self):
        url = "https://example.com/gtfs.zip"
        self.assertEqual(sanitize_url(url), url)

    def test_none_returns_none(self):
        self.assertIsNone(sanitize_url(None))


class TestGetExternalIp(unittest.TestCase):
    def setUp(self):
        utils._external_ip_cache = None

    def tearDown(self):
        utils._external_ip_cache = None

    def test_returns_ip_on_success(self):
        response = MagicMock(status=200, data=b"34.1.2.3\n")
        pool = MagicMock()
        pool.request.return_value = response
        pool.__enter__ = lambda s: pool
        pool.__exit__ = MagicMock(return_value=False)

        with patch("utils.urllib3.PoolManager", return_value=pool):
            self.assertEqual(get_external_ip(), "34.1.2.3")

    def test_returns_none_when_lookup_fails(self):
        with patch("utils.urllib3.PoolManager", side_effect=Exception("boom")):
            self.assertIsNone(get_external_ip())

    def test_result_is_cached(self):
        response = MagicMock(status=200, data=b"34.1.2.3")
        pool = MagicMock()
        pool.request.return_value = response
        pool.__enter__ = lambda s: pool
        pool.__exit__ = MagicMock(return_value=False)

        with patch("utils.urllib3.PoolManager", return_value=pool) as mock_pool:
            get_external_ip()
            get_external_ip()
            self.assertEqual(mock_pool.call_count, 1)


def _mock_response(status=200, headers=None, chunks=None):
    response = MagicMock()
    response.status = status
    response.headers = headers if headers is not None else {}
    response.retries = MagicMock(history=[])
    response.__enter__ = lambda s: response
    response.__exit__ = MagicMock(return_value=False)
    data = list(chunks if chunks is not None else [b""])

    def read(_size):
        return data.pop(0) if data else b""

    response.read.side_effect = read
    return response


def _mock_pool(response):
    pool = MagicMock()
    pool.request.return_value = response
    pool.__enter__ = lambda s: pool
    pool.__exit__ = MagicMock(return_value=False)
    return pool


@patch("shared.common.config_reader.get_config_value", return_value=None)
class TestDownloadFeed(unittest.TestCase):
    def setUp(self):
        self.file_path = os.path.join(
            os.path.dirname(__file__), "download_feed_test.bin"
        )
        utils._external_ip_cache = None

    def tearDown(self):
        if os.path.exists(self.file_path):
            os.remove(self.file_path)
        utils._external_ip_cache = None

    def test_diagnostics_populated_on_success(self, _mock_config):
        response = _mock_response(
            status=200,
            headers={"Content-Type": "application/zip", "Server": "nginx"},
            chunks=[b"PK\x03\x04data", b""],
        )
        with patch("utils.urllib3.PoolManager", return_value=_mock_pool(response)):
            result = download_feed(
                "https://example.com/gtfs.zip", self.file_path, feed_id="feed-1"
            )

        diagnostics = result.diagnostics
        self.assertTrue(diagnostics.success)
        self.assertEqual(diagnostics.status_code, 200)
        self.assertEqual(diagnostics.content_type, "application/zip")
        self.assertEqual(diagnostics.downloaded_bytes, 8)
        self.assertEqual(diagnostics.response_headers["Server"], "nginx")
        self.assertIn("User-Agent", diagnostics.request_headers)
        self.assertIsNotNone(diagnostics.latency_ms)
        self.assertIsNone(diagnostics.error_type)
        self.assertIsNotNone(result.file_hash)

    def test_external_ip_not_looked_up_on_success(self, _mock_config):
        response = _mock_response(chunks=[b"data", b""])
        with patch("utils.urllib3.PoolManager", return_value=_mock_pool(response)):
            with patch("utils.get_external_ip") as mock_ip:
                download_feed("https://example.com/gtfs.zip", self.file_path)
                mock_ip.assert_not_called()

    def test_non_2xx_raises_with_diagnostics(self, _mock_config):
        response = _mock_response(
            status=403, headers={"Content-Type": "text/html", "Server": "cloudflare"}
        )
        with patch("utils.urllib3.PoolManager", return_value=_mock_pool(response)):
            with patch("utils.get_external_ip", return_value="34.1.2.3"):
                with pytest.raises(FeedDownloadError) as exc_info:
                    download_feed("https://example.com/gtfs.zip", self.file_path)

        diagnostics = exc_info.value.diagnostics
        self.assertFalse(diagnostics.success)
        self.assertEqual(diagnostics.status_code, 403)
        self.assertEqual(diagnostics.content_type, "text/html")
        self.assertEqual(diagnostics.response_headers["Server"], "cloudflare")
        self.assertEqual(diagnostics.external_ip, "34.1.2.3")
        self.assertEqual(diagnostics.error_type, "ValueError")

    def test_network_error_raises_with_diagnostics(self, _mock_config):
        with patch("utils.urllib3.PoolManager", side_effect=Exception("Network error")):
            with patch("utils.get_external_ip", return_value=None):
                with pytest.raises(FeedDownloadError) as exc_info:
                    download_feed("https://example.com/gtfs.zip", self.file_path)

        diagnostics = exc_info.value.diagnostics
        self.assertFalse(diagnostics.success)
        self.assertIsNone(diagnostics.status_code)
        self.assertEqual(diagnostics.error_type, "Exception")
        self.assertEqual(diagnostics.error_message, "Network error")

    def test_credentials_never_appear_in_diagnostics(self, _mock_config):
        response = _mock_response(status=403)
        with patch("utils.urllib3.PoolManager", return_value=_mock_pool(response)):
            with patch("utils.get_external_ip", return_value=None):
                with pytest.raises(FeedDownloadError) as exc_info:
                    download_feed(
                        "https://example.com/gtfs.zip",
                        self.file_path,
                        authentication_type=1,
                        api_key_parameter_name="token",
                        credentials="super-secret",
                    )

        serialized = str(exc_info.value.diagnostics.as_dict())
        self.assertNotIn("super-secret", serialized)
        self.assertIn(REDACTED, serialized)

    def test_max_bytes_truncates_and_returns_no_hash(self, _mock_config):
        response = _mock_response(chunks=[b"a" * 10, b"a" * 10, b""])
        with patch("utils.urllib3.PoolManager", return_value=_mock_pool(response)):
            result = download_feed(
                "https://example.com/gtfs.zip",
                self.file_path,
                chunk_size=10,
                max_bytes=10,
            )

        self.assertIsNone(result.file_hash)
        self.assertEqual(result.diagnostics.downloaded_bytes, 10)

    def test_redirect_urls_are_recorded(self, _mock_config):
        response = _mock_response(chunks=[b"data", b""])
        response.retries = MagicMock(
            history=[MagicMock(redirect_location="https://cdn.example.com/gtfs.zip")]
        )
        with patch("utils.urllib3.PoolManager", return_value=_mock_pool(response)):
            result = download_feed("https://example.com/gtfs.zip", self.file_path)

        self.assertEqual(
            result.diagnostics.redirect_urls, ["https://cdn.example.com/gtfs.zip"]
        )


class TestBuildAvailabilityCheck(unittest.TestCase):
    def test_maps_diagnostics_onto_row(self):
        diagnostics = FeedRequestDiagnostics(
            request_url="https://example.com/gtfs.zip",
            resolved_url="https://example.com/gtfs.zip",
            request_headers={"User-Agent": "agent"},
            response_headers={"Server": "cloudflare"},
            status_code=403,
            latency_ms=1840,
            redirect_urls=["https://cdn.example.com/gtfs.zip"],
            external_ip="34.1.2.3",
            content_type="text/html",
            is_zip=False,
            error_type="ValueError",
            error_message="Invalid HTTP response code: [403]",
        )

        row = build_availability_check(
            diagnostics, feed_id="feed-1", source="dataset_download"
        )

        self.assertEqual(row.feed_id, "feed-1")
        self.assertEqual(row.source, "dataset_download")
        self.assertEqual(row.request_type, "http_get")
        self.assertEqual(row.status_code, 403)
        self.assertEqual(row.external_ip, "34.1.2.3")
        self.assertEqual(row.response_headers, {"Server": "cloudflare"})
        self.assertFalse(row.success)

    def test_success_flag_follows_status_code(self):
        diagnostics = FeedRequestDiagnostics(status_code=200)
        row = build_availability_check(
            diagnostics, feed_id="feed-1", source="dataset_download"
        )
        self.assertTrue(row.success)


@patch("shared.common.config_reader.get_config_value", return_value=None)
class TestErrorMessageSanitization(unittest.TestCase):
    def setUp(self):
        self.file_path = os.path.join(os.path.dirname(__file__), "err_test.bin")
        utils._external_ip_cache = None

    def tearDown(self):
        if os.path.exists(self.file_path):
            os.remove(self.file_path)
        utils._external_ip_cache = None

    def test_userinfo_in_producer_url_is_redacted_in_error(self, _mock_config):
        url = "https://user:password@example.com/gtfs.zip"
        with patch(
            "utils.urllib3.PoolManager", side_effect=Exception(f"failed for {url}")
        ):
            with patch("utils.get_external_ip", return_value=None):
                with pytest.raises(FeedDownloadError) as exc_info:
                    download_feed(url, self.file_path)

        self.assertNotIn("password", exc_info.value.diagnostics.error_message)

    def test_credentials_in_resolved_url_are_redacted_in_error(self, _mock_config):
        def boom(*_args, **_kwargs):
            raise Exception(
                "failed for https://example.com/gtfs.zip?token=super-secret"
            )

        with patch("utils.urllib3.PoolManager", side_effect=boom):
            with patch("utils.get_external_ip", return_value=None):
                with pytest.raises(FeedDownloadError) as exc_info:
                    download_feed(
                        "https://example.com/gtfs.zip",
                        self.file_path,
                        authentication_type=1,
                        api_key_parameter_name="token",
                        credentials="super-secret",
                    )

        self.assertNotIn("super-secret", exc_info.value.diagnostics.error_message)
