import hashlib
import os
import unittest
from unittest.mock import Mock, ANY, MagicMock
from unittest.mock import patch

import pytest
import urllib3_mock

from helpers.utils import create_bucket, download_url_content, download_and_get_hash

responses = urllib3_mock.Responses("requests.packages.urllib3")


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

    @patch("requests.Session")
    def test_download_url_content(self, mock_session):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = b"test content"
        mock_session.return_value.get.return_value = mock_response

        url = "https://test.com"
        result = download_url_content(url)

        assert result == b"test content"
        mock_session.return_value.get.assert_called_with(
            url, headers=ANY, verify=False, timeout=120, stream=True
        )

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

    def test_download_and_get_hash_auth_type_1(self):
        mock_binary_data = b"binary data for auth type 1"
        expected_hash = hashlib.sha256(mock_binary_data).hexdigest()
        file_path = "test_file.txt"
        url = "https://test.com"
        api_key_parameter_name = "Authorization"
        credentials = "Bearer token123"

        mock_response = MagicMock()
        mock_response.read.side_effect = [mock_binary_data, b""]
        mock_response.__enter__.return_value = mock_response

        with patch(
            "urllib3.PoolManager.request", return_value=mock_response
        ) as mock_request:
            result_hash = download_and_get_hash(
                url, file_path, "sha256", 8192, 1, api_key_parameter_name, credentials
            )

            self.assertEqual(
                result_hash,
                expected_hash,
                msg=f"Hash mismatch: got {result_hash},"
                f" but expected {expected_hash}",
            )

            mock_request.assert_called_with(
                "GET",
                url,
                preload_content=False,
                headers={api_key_parameter_name: credentials},
            )

            if os.path.exists(file_path):
                os.remove(file_path)

    def test_download_and_get_hash_auth_type_2(self):
        mock_binary_data = b"binary data for auth type 2"
        expected_hash = hashlib.sha256(mock_binary_data).hexdigest()
        file_path = "test_file.txt"
        base_url = "https://test.com"
        api_key_parameter_name = "api_key"
        credentials = "key123"

        modified_url = f"{base_url}?{api_key_parameter_name}={credentials}"

        mock_response = MagicMock()
        mock_response.read.side_effect = [mock_binary_data, b""]
        mock_response.__enter__.return_value = mock_response

        with patch(
            "urllib3.PoolManager.request", return_value=mock_response
        ) as mock_request:
            result_hash = download_and_get_hash(
                base_url,
                file_path,
                "sha256",
                8192,
                2,
                api_key_parameter_name,
                credentials,
            )

            self.assertEqual(
                result_hash,
                expected_hash,
                msg=f"Hash mismatch: got {result_hash},"
                f" but expected {expected_hash}",
            )

            mock_request.assert_called_with(
                "GET", modified_url, preload_content=False, headers={}
            )

        if os.path.exists(file_path):
            os.remove(file_path)

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
