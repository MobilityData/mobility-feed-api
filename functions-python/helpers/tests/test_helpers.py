import hashlib
import os
import unittest
from unittest.mock import Mock, MagicMock
from unittest.mock import patch

import pytest
import urllib3_mock

from helpers.logger import Logger
from helpers.utils import create_bucket, download_and_get_hash, download_url_content

responses = urllib3_mock.Responses("requests.packages.urllib3")
expected_user_agent = (
    "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Mobile Safari/537.36"
)


class TestHelpers(unittest.TestCase):
    @patch("google.cloud.storage.Client")
    def test_create_bucket(self, mock_storage_client):
        mock_bucket = Mock()
        mock_storage_client.return_value.lookup_bucket.return_value = None
        mock_storage_client.return_value.create_bucket.return_value = mock_bucket

        create_bucket("test-bucket")

        mock_storage_client.return_value.lookup_bucket.assert_called_once_with(
            "test-bucket"
        )
        mock_storage_client.return_value.create_bucket.assert_called_once_with(
            "test-bucket"
        )

    @patch("google.cloud.storage.Client")
    def test_create_bucket_already_exists(self, mock_storage_client):
        mock_bucket = Mock()
        mock_storage_client.return_value.lookup_bucket.return_value = {}
        mock_storage_client.return_value.create_bucket.return_value = mock_bucket

        create_bucket("test-bucket")

        mock_storage_client.return_value.lookup_bucket.assert_called_once_with(
            "test-bucket"
        )
        mock_storage_client.return_value.create_bucket.assert_not_called()

    def test_download_and_get_hash(self):
        mock_binary_data = b"file content data"
        expected_hash = hashlib.sha256(mock_binary_data).hexdigest()
        file_path = "file_path"

        mock_response = MagicMock()
        mock_response.read.side_effect = [mock_binary_data, b""]
        mock_response.__enter__.return_value = mock_response

        with patch("urllib3.PoolManager.request", return_value=mock_response):
            result = download_and_get_hash("test.com", file_path, "sha256")
            self.assertEqual(
                result,
                expected_hash,
                msg=f"Hash mismatch: got {result}," f" but expected {expected_hash}",
            )
            if os.path.exists(file_path):
                os.remove(file_path)

    # def test_download_and_get_hash_auth_type_1(self):
    #     mock_binary_data = b"binary data for auth type 1"
    #     expected_hash = hashlib.sha256(mock_binary_data).hexdigest()
    #     file_path = "test_file.txt"
    #     url = "https://test.com"
    #     api_key_parameter_name = "Authorization"
    #     credentials = "Bearer token123"

    #     mock_response = MagicMock()
    #     mock_response.read.side_effect = [mock_binary_data, b""]
    #     mock_response.__enter__.return_value = mock_response

    #     with patch(
    #         "urllib3.PoolManager.request", return_value=mock_response
    #     ) as mock_request:
    #         result_hash = download_and_get_hash(
    #             url, file_path, "sha256", 8192, 1, api_key_parameter_name, credentials
    #         )

    #         self.assertEqual(
    #             result_hash,
    #             expected_hash,
    #             msg=f"Hash mismatch: got {result_hash},"
    #             f" but expected {expected_hash}",
    #         )

    #         mock_request.assert_called_with(
    #             "GET",
    #             url,
    #             preload_content=False,
    #             headers={
    #                 "User-Agent": expected_user_agent,
    #                 api_key_parameter_name: credentials,
    #             },
    #         )

    #         if os.path.exists(file_path):
    #             os.remove(file_path)

    # def test_download_and_get_hash_auth_type_2(self):
    #     mock_binary_data = b"binary data for auth type 2"
    #     expected_hash = hashlib.sha256(mock_binary_data).hexdigest()
    #     file_path = "test_file.txt"
    #     base_url = "https://test.com"
    #     api_key_parameter_name = "api_key"
    #     credentials = "key123"

    #     modified_url = f"{base_url}?{api_key_parameter_name}={credentials}"

    #     mock_response = MagicMock()
    #     mock_response.read.side_effect = [mock_binary_data, b""]
    #     mock_response.__enter__.return_value = mock_response

    #     with patch(
    #         "urllib3.PoolManager.request", return_value=mock_response
    #     ) as mock_request:
    #         result_hash = download_and_get_hash(
    #             base_url,
    #             file_path,
    #             "sha256",
    #             8192,
    #             2,
    #             api_key_parameter_name,
    #             credentials,
    #         )

    #         self.assertEqual(
    #             result_hash,
    #             expected_hash,
    #             msg=f"Hash mismatch: got {result_hash},"
    #             f" but expected {expected_hash}",
    #         )

    #         mock_request.assert_called_with(
    #             "GET",
    #             modified_url,
    #             preload_content=False,
    #             headers={"User-Agent": expected_user_agent},
    #         )

    #     if os.path.exists(file_path):
    #         os.remove(file_path)

    def test_download_and_get_hash_auth_type_1(self):
        url = "http://example.com/data"
        api_key_parameter_name = "api_key"
        credentials = "test_api_key"
        expected_url = f"{url}?{api_key_parameter_name}={credentials}"

        with patch("helpers.download.create_urllib3_context") as mock_create_context:
            mock_context = mock_create_context.return_value
            mock_context.load_default_certs.return_value = None

            with patch("helpers.download.urllib3.PoolManager") as mock_pool_manager:
                mock_http = mock_pool_manager.return_value
                mock_response = mock_http.request.return_value
                mock_response.read.side_effect = [b"data_chunk_1", b"data_chunk_2", b""]
                mock_response.__enter__.return_value = mock_response

                result = download_and_get_hash(
                    url,
                    file_path="test_file",
                    hash_algorithm="sha256",
                    authentication_type=1,
                    api_key_parameter_name=api_key_parameter_name,
                    credentials=credentials,
                )

                mock_http.request.assert_called_with(
                    "GET",
                    expected_url,
                    preload_content=False,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0.0.0 Mobile Safari/537.36"
                    },
                )
                assert result is not None

    def test_download_and_get_hash_auth_type_2(self):
        url = "http://example.com/data"
        api_key_parameter_name = "Authorization"
        credentials = "Bearer test_token"
        expected_headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Mobile Safari/537.36",
            api_key_parameter_name: credentials,
        }

        with patch("helpers.download.create_urllib3_context") as mock_create_context:
            mock_context = mock_create_context.return_value
            mock_context.load_default_certs.return_value = None

            with patch("helpers.download.urllib3.PoolManager") as mock_pool_manager:
                mock_http = mock_pool_manager.return_value
                mock_response = mock_http.request.return_value
                mock_response.read.side_effect = [b"data_chunk_1", b"data_chunk_2", b""]
                mock_response.__enter__.return_value = mock_response

                result = download_and_get_hash(
                    url,
                    file_path="test_file",
                    hash_algorithm="sha256",
                    authentication_type=2,
                    api_key_parameter_name=api_key_parameter_name,
                    credentials=credentials,
                )

                mock_http.request.assert_called_with(
                    "GET", url, preload_content=False, headers=expected_headers
                )
                assert result is not None

    def test_download_and_get_hash_exception(self):
        file_path = "test_file.txt"
        url = "https://test.com/"

        with patch(
            "urllib3.PoolManager.request", side_effect=Exception("Network error")
        ):
            with pytest.raises(Exception) as exec_info:
                download_and_get_hash(url, file_path, "sha256", 8192)
                self.assertEqual("Network error", str(exec_info.value))

        if os.path.exists(file_path):
            os.remove(file_path)

    @patch("google.cloud.logging.Client")
    def test_logger_initialization(self, mock_client):
        mock_client.return_value.logger.return_value = MagicMock()

        logger = Logger("test_logger")
        mock_client.assert_called()
        mock_client.return_value.logger.assert_called_with("test_logger")
        self.assertIsNotNone(logger.get_logger())

    @patch("requests.Session.get")
    def test_download_url_content_success(self, mock_get):
        expected_content = b"test content"
        mock_get.return_value = MagicMock(status_code=200, content=expected_content)

        result = download_url_content("https://example.com")
        self.assertEqual(
            result, expected_content, "Content should match the expected content"
        )

    @patch("requests.Session.get")
    def test_download_url_content_failure(self, mock_get):
        mock_get.side_effect = Exception("Failed to download")

        with self.assertRaises(Exception) as context:
            download_url_content("https://example.com")
        self.assertEqual(
            str(context.exception),
            "Failed to download",
            "Should raise the correct exception",
        )
