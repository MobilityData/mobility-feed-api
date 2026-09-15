#
#   MobilityData 2025
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
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

from tasks.web_revalidation.revalidate_feed import revalidate_feed_handler


class TestRevalidateFeedHandler(unittest.TestCase):
    def test_missing_feed_stable_id(self):
        result = revalidate_feed_handler({})
        self.assertEqual(result["status"], "error")
        self.assertIn("feed_stable_id", result["error"])

    def test_empty_feed_stable_ids_list(self):
        result = revalidate_feed_handler({"feed_stable_ids": []})
        self.assertEqual(result["status"], "error")

    def test_missing_payload(self):
        result = revalidate_feed_handler(None)
        self.assertEqual(result["status"], "error")

    @patch.dict(
        "os.environ",
        {"WEB_APP_REVALIDATE_URL": "", "WEB_APP_REVALIDATE_SECRET": "secret"},
    )
    def test_missing_revalidate_url(self):
        result = revalidate_feed_handler({"feed_stable_id": "mdb-123"})
        self.assertEqual(result["status"], "skipped")
        self.assertIn("WEB_APP_REVALIDATE_URL", result["message"])

    @patch.dict(
        "os.environ",
        {
            "WEB_APP_REVALIDATE_URL": "https://example.com/api/revalidate",
            "WEB_APP_REVALIDATE_SECRET": "",
        },
    )
    def test_missing_revalidate_secret(self):
        result = revalidate_feed_handler({"feed_stable_id": "mdb-123"})
        self.assertEqual(result["status"], "skipped")
        self.assertIn("WEB_APP_REVALIDATE_SECRET", result["message"])

    @patch("tasks.web_revalidation.revalidate_feed.requests.post")
    @patch.dict(
        "os.environ",
        {
            "WEB_APP_REVALIDATE_URL": "https://example.com/api/revalidate",
            "WEB_APP_REVALIDATE_SECRET": "test-secret",
        },
    )
    def test_successful_revalidation(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = revalidate_feed_handler({"feed_stable_id": "mdb-123"})

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["feed_stable_id"], "mdb-123")
        mock_post.assert_called_once_with(
            "https://example.com/api/revalidate",
            json={"feedIds": ["mdb-123"], "type": "specific-feeds"},
            headers={
                "x-revalidate-secret": "test-secret",
                "Content-Type": "application/json",
            },
            timeout=30,
        )

    @patch("tasks.web_revalidation.revalidate_feed.requests.post")
    @patch.dict(
        "os.environ",
        {
            "WEB_APP_REVALIDATE_URL": "https://example.com/api/revalidate",
            "WEB_APP_REVALIDATE_SECRET": "test-secret",
        },
    )
    def test_failed_revalidation(self, mock_post):
        import requests

        mock_post.side_effect = requests.RequestException("Connection refused")

        result = revalidate_feed_handler({"feed_stable_id": "mdb-456"})

        self.assertEqual(result["status"], "error")
        self.assertIn("Connection refused", result["error"])


class TestRevalidateFeedHandlerBatched(unittest.TestCase):
    """The batched payload: one request carrying many feeds, not one request each.

    The single-feed cases above must keep passing untouched - `create_web_revalidation_task`
    and every dataset-driven call site still send that shape, and tasks in that shape are in
    the queue whenever this deploys.
    """

    @patch("tasks.web_revalidation.revalidate_feed.requests.post")
    @patch.dict(
        "os.environ",
        {
            "WEB_APP_REVALIDATE_URL": "https://example.com/api/revalidate",
            "WEB_APP_REVALIDATE_SECRET": "test-secret",
        },
    )
    def test_many_feeds_are_one_request(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = revalidate_feed_handler(
            {"feed_stable_ids": ["mdb-1", "mdb-2", "mdb-3"]}
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["feed_stable_ids"], ["mdb-1", "mdb-2", "mdb-3"])
        mock_post.assert_called_once_with(
            "https://example.com/api/revalidate",
            json={"feedIds": ["mdb-1", "mdb-2", "mdb-3"], "type": "specific-feeds"},
            headers={
                "x-revalidate-secret": "test-secret",
                "Content-Type": "application/json",
            },
            timeout=120,
        )

    @patch("tasks.web_revalidation.revalidate_feed.requests.post")
    @patch.dict(
        "os.environ",
        {
            "WEB_APP_REVALIDATE_URL": "https://example.com/api/revalidate",
            "WEB_APP_REVALIDATE_SECRET": "test-secret",
        },
    )
    def test_a_single_id_list_is_the_single_feed_request(self, mock_post):
        """A one-element list must not become the longer-timeout batched shape."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = revalidate_feed_handler({"feed_stable_ids": ["mdb-1"]})

        self.assertEqual(result["feed_stable_id"], "mdb-1")
        self.assertEqual(mock_post.call_args.kwargs["timeout"], 30)

    @patch("tasks.web_revalidation.revalidate_feed.requests.post")
    @patch.dict(
        "os.environ",
        {
            "WEB_APP_REVALIDATE_URL": "https://example.com/api/revalidate",
            "WEB_APP_REVALIDATE_SECRET": "test-secret",
        },
    )
    def test_failure_names_the_feeds_by_count(self, mock_post):
        import requests

        mock_post.side_effect = requests.RequestException("Connection refused")

        result = revalidate_feed_handler({"feed_stable_ids": ["mdb-1", "mdb-2"]})

        self.assertEqual(result["status"], "error")
        self.assertIn("2 feeds", result["error"])
        self.assertEqual(result["feed_stable_ids"], ["mdb-1", "mdb-2"])

    @patch.dict(
        "os.environ",
        {"WEB_APP_REVALIDATE_URL": "", "WEB_APP_REVALIDATE_SECRET": "secret"},
    )
    def test_unconfigured_url_still_reports_the_feeds(self):
        result = revalidate_feed_handler({"feed_stable_ids": ["mdb-1", "mdb-2"]})
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["feed_stable_ids"], ["mdb-1", "mdb-2"])


if __name__ == "__main__":
    unittest.main()
