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
import os
import unittest
from unittest.mock import MagicMock, patch

import flask

from main import GtfsChangeTracker, gtfs_change_tracker


def _make_dataset(id_, stable_id, hosted_url, feed_stable_id="mdb-1"):
    dataset = MagicMock()
    dataset.id = id_
    dataset.stable_id = stable_id
    dataset.hosted_url = hosted_url
    dataset.feed = MagicMock()
    dataset.feed.stable_id = feed_stable_id
    return dataset


class TestGtfsChangeTrackerHandler(unittest.TestCase):
    """Tests for the HTTP handler function."""

    def _request(self, payload):
        with flask.Flask(__name__).test_request_context(json=payload):
            return gtfs_change_tracker(flask.request)

    def test_missing_all_params(self):
        result = self._request({})
        self.assertEqual(result["status"], "error")
        self.assertIn("required", result["error"])

    def test_missing_one_param(self):
        result = self._request({"feed_id": "f1", "previous_dataset_id": "p1"})
        self.assertEqual(result["status"], "error")

    def test_missing_bucket_env(self):
        os.environ.pop("DATASETS_BUCKET_NAME", None)
        result = self._request(
            {"feed_id": "f1", "previous_dataset_id": "p1", "current_dataset_id": "c1"}
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("DATASETS_BUCKET_NAME", result["error"])

    @patch("main.GtfsChangeTracker")
    def test_success(self, mock_tracker_cls):
        os.environ["DATASETS_BUCKET_NAME"] = "test-bucket"
        instance = MagicMock()
        instance.run.return_value = {
            "message": "Changelog generated successfully.",
            "changelog_url": "https://storage.googleapis.com/test-bucket/mdb-1/changelogs/p1_c1_changelog.json",
        }
        mock_tracker_cls.return_value = instance

        result = self._request(
            {"feed_id": "f1", "previous_dataset_id": "p1", "current_dataset_id": "c1"}
        )
        self.assertEqual(result["status"], "success")
        self.assertIn("changelog_url", result)
        mock_tracker_cls.assert_called_once_with(
            feed_id="f1",
            previous_dataset_id="p1",
            current_dataset_id="c1",
            bucket_name="test-bucket",
        )

    @patch("main.GtfsChangeTracker")
    def test_exception_returns_error(self, mock_tracker_cls):
        os.environ["DATASETS_BUCKET_NAME"] = "test-bucket"
        instance = MagicMock()
        instance.run.side_effect = Exception("something went wrong")
        mock_tracker_cls.return_value = instance

        result = self._request(
            {"feed_id": "f1", "previous_dataset_id": "p1", "current_dataset_id": "c1"}
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("something went wrong", result["error"])


class TestGtfsChangeTrackerRun(unittest.TestCase):
    """Tests for GtfsChangeTracker.run() with mocked collaborators."""

    def setUp(self):
        os.environ["DATASETS_BUCKET_NAME"] = "test-bucket"
        self.tracker = GtfsChangeTracker(
            feed_id="feed-uuid",
            previous_dataset_id="prev-uuid",
            current_dataset_id="curr-uuid",
            bucket_name="test-bucket",
        )

    @patch("main.GtfsChangeTracker._save_changelog_record")
    @patch("main.GtfsChangeTracker._upload_changelog")
    @patch("main.GtfsChangeTracker._download_zip")
    @patch("main.GtfsChangeTracker._resolve_datasets")
    def test_run_happy_path(self, mock_resolve, mock_download, mock_upload, mock_save):
        prev_ds = _make_dataset(
            "prev-uuid", "mdb-1-20240101", "https://example.com/prev.zip"
        )
        curr_ds = _make_dataset(
            "curr-uuid", "mdb-1-20240201", "https://example.com/curr.zip"
        )
        mock_resolve.return_value = (prev_ds, curr_ds, "mdb-1")

        fake_summary = MagicMock()
        fake_summary.model_dump.return_value = {"total_changes": 42}
        fake_diff = MagicMock()
        fake_diff.summary = fake_summary
        fake_diff.model_dump_json.return_value = (
            '{"metadata": {}, "summary": {}, "file_diffs": []}'
        )

        changelog_url = (
            "https://storage.googleapis.com/test-bucket/mdb-1/changelogs/"
            "mdb-1-20240101_mdb-1-20240201_changelog.json"
        )
        mock_upload.return_value = changelog_url

        with patch("main.diff_feeds", return_value=fake_diff, create=True) as mock_diff:
            result = self.tracker.run()

        mock_resolve.assert_called_once()
        self.assertEqual(mock_download.call_count, 2)
        mock_diff.assert_called_once()
        mock_upload.assert_called_once_with(
            fake_diff.model_dump_json.return_value.encode("utf-8"),
            "mdb-1",
            "mdb-1-20240101",
            "mdb-1-20240201",
        )
        mock_save.assert_called_once_with(
            changelog_url=changelog_url,
            diff_summary={"total_changes": 42},
        )
        self.assertEqual(result["changelog_url"], changelog_url)

    @patch("main.GtfsChangeTracker._resolve_datasets")
    def test_run_raises_when_resolve_fails(self, mock_resolve):
        mock_resolve.side_effect = ValueError("Previous dataset not found: prev-uuid")
        with self.assertRaises(ValueError):
            self.tracker.run()


class TestDownloadZip(unittest.TestCase):
    def setUp(self):
        self.tracker = GtfsChangeTracker(
            feed_id="f",
            previous_dataset_id="p",
            current_dataset_id="c",
            bucket_name="bucket",
        )

    @patch("main.requests.get")
    def test_download_writes_chunks(self, mock_get):
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        import tempfile
        import os

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp_path = tmp.name
        try:
            self.tracker._download_zip("https://example.com/feed.zip", tmp_path)
            with open(tmp_path, "rb") as f:
                content = f.read()
            self.assertEqual(content, b"chunk1chunk2")
        finally:
            os.unlink(tmp_path)

    @patch("main.requests.get")
    def test_download_raises_on_http_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_get.return_value = mock_response

        with self.assertRaises(Exception):
            self.tracker._download_zip("https://example.com/missing.zip", "/tmp/x.zip")


class TestUploadChangelog(unittest.TestCase):
    def setUp(self):
        self.tracker = GtfsChangeTracker(
            feed_id="f",
            previous_dataset_id="p",
            current_dataset_id="c",
            bucket_name="my-bucket",
        )

    @patch("main.storage.Client")
    def test_uploads_two_blobs_and_returns_primary_url(self, mock_storage_cls):
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage_cls.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        url = self.tracker._upload_changelog(
            b'{"data": 1}', "mdb-1", "mdb-1-20240101", "mdb-1-20240201"
        )

        self.assertEqual(mock_bucket.blob.call_count, 2)
        upload_calls = mock_blob.upload_from_string.call_args_list
        self.assertEqual(len(upload_calls), 2)
        for c in upload_calls:
            self.assertEqual(
                c.kwargs.get("content_type") or c.args[1], "application/json"
            )

        expected_primary = (
            "https://storage.googleapis.com/my-bucket/mdb-1/changelogs/"
            "mdb-1-20240101_mdb-1-20240201_changelog.json"
        )
        self.assertEqual(url, expected_primary)

        blob_paths = [c.args[0] for c in mock_bucket.blob.call_args_list]
        self.assertIn(
            "mdb-1/changelogs/mdb-1-20240101_mdb-1-20240201_changelog.json", blob_paths
        )
        self.assertIn(
            "mdb-1/mdb-1-20240201/mdb-1-20240201_mdb-1-20240101_changelog.json",
            blob_paths,
        )
