#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import os
import unittest
from unittest.mock import MagicMock, patch

from cdn_cache import invalidate_cdn_cache, latest_dataset_path

ENV = {"FILES_URL_MAP_NAME": "files-url-map-dev", "PROJECT_ID": "my-project"}


class TestCdnCache(unittest.TestCase):
    def test_latest_dataset_path(self):
        self.assertEqual(latest_dataset_path("mdb-1"), "/mdb-1/latest.zip")

    @patch.dict(os.environ, {}, clear=True)
    @patch("google.auth.default")
    def test_skipped_without_url_map(self, mock_default):
        self.assertIsNone(invalidate_cdn_cache("/mdb-1/latest.zip"))
        mock_default.assert_not_called()

    @patch.dict(os.environ, ENV)
    @patch("google.auth.transport.requests.AuthorizedSession")
    @patch("google.auth.default", return_value=(MagicMock(), "my-project"))
    def test_posts_invalidation(self, _, mock_session_cls):
        response = MagicMock()
        response.json.return_value = {"name": "operation-123"}
        mock_session_cls.return_value.post.return_value = response

        operation = invalidate_cdn_cache("/mdb-1/latest.zip")

        self.assertEqual(operation, "operation-123")
        url = mock_session_cls.return_value.post.call_args.args[0]
        self.assertEqual(
            url,
            "https://compute.googleapis.com/compute/v1/projects/my-project"
            "/global/urlMaps/files-url-map-dev/invalidateCache",
        )
        self.assertEqual(
            mock_session_cls.return_value.post.call_args.kwargs["json"],
            {"path": "/mdb-1/latest.zip"},
        )

    @patch.dict(os.environ, ENV)
    @patch("cdn_cache.time.sleep")
    @patch("google.auth.transport.requests.AuthorizedSession")
    @patch("google.auth.default", return_value=(MagicMock(), "my-project"))
    def test_retries_then_raises(self, _, mock_session_cls, mock_sleep):
        mock_session_cls.return_value.post.side_effect = Exception("503")

        with self.assertRaises(Exception):
            invalidate_cdn_cache("/mdb-1/latest.zip")

        self.assertEqual(mock_session_cls.return_value.post.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch.dict(os.environ, ENV)
    @patch("cdn_cache.time.sleep")
    @patch("google.auth.transport.requests.AuthorizedSession")
    @patch("google.auth.default", return_value=(MagicMock(), "my-project"))
    def test_recovers_after_transient_failure(self, _, mock_session_cls, __):
        response = MagicMock()
        response.json.return_value = {"name": "operation-456"}
        mock_session_cls.return_value.post.side_effect = [Exception("503"), response]

        self.assertEqual(invalidate_cdn_cache("/mdb-1/latest.zip"), "operation-456")


if __name__ == "__main__":
    unittest.main()
