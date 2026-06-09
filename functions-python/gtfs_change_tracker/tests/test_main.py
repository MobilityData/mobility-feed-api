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
import tempfile
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
            "changelog_url": "https://storage.googleapis.com/test-bucket/mdb-1/c1/c1_p1_changelog.json",
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
            bucket_mount="/mobilitydata-datasets",
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
            bucket_mount="/mobilitydata-datasets",
        )

    @patch("main.GtfsChangeTracker._save_changelog_record")
    @patch("main.GtfsChangeTracker._upload_changelog")
    @patch("main.GtfsChangeTracker._extracted_dir")
    @patch("main.GtfsChangeTracker._resolve_datasets")
    def test_run_happy_path(
        self, mock_resolve, mock_extracted_dir, mock_upload, mock_save
    ):
        prev_ds = _make_dataset(
            "prev-uuid", "mdb-1-20240101", "https://example.com/prev.zip"
        )
        curr_ds = _make_dataset(
            "curr-uuid", "mdb-1-20240201", "https://example.com/curr.zip"
        )
        mock_resolve.return_value = (prev_ds, curr_ds, "mdb-1")
        mock_extracted_dir.side_effect = [
            "/mobilitydata-datasets/mdb-1/mdb-1-20240101/extracted",
            "/mobilitydata-datasets/mdb-1/mdb-1-20240201/extracted",
        ]

        fake_summary = MagicMock()
        fake_summary.model_dump.return_value = {"total_changes": 42}
        fake_diff = MagicMock()
        fake_diff.summary = fake_summary
        fake_diff.model_dump_json.return_value = (
            '{"metadata": {}, "summary": {}, "file_diffs": []}'
        )

        changelog_url = (
            "https://storage.googleapis.com/test-bucket/mdb-1/"
            "mdb-1-20240201/mdb-1-20240201_mdb-1-20240101_changelog.json"
        )
        mock_upload.return_value = changelog_url

        with patch("main.diff_feeds", return_value=fake_diff, create=True) as mock_diff:
            result = self.tracker.run()

        mock_resolve.assert_called_once()
        self.assertEqual(mock_extracted_dir.call_count, 2)
        extracted_calls = mock_extracted_dir.call_args_list
        self.assertEqual(extracted_calls[0].args, ("mdb-1", "mdb-1-20240101"))
        self.assertEqual(extracted_calls[1].args, ("mdb-1", "mdb-1-20240201"))
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


class TestExtractedDir(unittest.TestCase):
    def setUp(self):
        self.tracker = GtfsChangeTracker(
            feed_id="f",
            previous_dataset_id="p",
            current_dataset_id="c",
            bucket_name="my-bucket",
            bucket_mount="/mobilitydata-datasets",
        )

    def test_returns_correct_path_when_dir_exists(self):
        with tempfile.TemporaryDirectory() as mount:
            extracted = os.path.join(mount, "mdb-1", "mdb-1-20240101", "extracted")
            os.makedirs(extracted)
            self.tracker.bucket_mount = mount
            result = self.tracker._extracted_dir("mdb-1", "mdb-1-20240101")
            self.assertEqual(result, extracted)

    def test_raises_when_dir_not_found(self):
        with self.assertRaises(ValueError, msg="Extracted files not found"):
            self.tracker._extracted_dir("mdb-1", "mdb-1-20240101")


class TestUploadChangelog(unittest.TestCase):
    def setUp(self):
        self.tracker = GtfsChangeTracker(
            feed_id="f",
            previous_dataset_id="p",
            current_dataset_id="c",
            bucket_name="my-bucket",
            bucket_mount="/mobilitydata-datasets",
        )

    @patch("main.storage.Client")
    def test_uploads_one_blob_and_returns_url(self, mock_storage_cls):
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage_cls.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        url = self.tracker._upload_changelog(
            b'{"data": 1}', "mdb-1", "mdb-1-20240101", "mdb-1-20240201"
        )

        mock_bucket.blob.assert_called_once_with(
            "mdb-1/mdb-1-20240201/mdb-1-20240201_mdb-1-20240101_changelog.json"
        )
        mock_blob.upload_from_string.assert_called_once_with(
            b'{"data": 1}', content_type="application/json"
        )
        self.assertEqual(
            url,
            "https://storage.googleapis.com/my-bucket/"
            "mdb-1/mdb-1-20240201/mdb-1-20240201_mdb-1-20240101_changelog.json",
        )
