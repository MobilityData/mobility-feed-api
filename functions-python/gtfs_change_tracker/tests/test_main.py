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


def _make_dataset(
    id_, stable_id, hosted_url, feed_stable_id="mdb-1", feed_id="feed-uuid"
):
    dataset = MagicMock()
    dataset.id = id_
    dataset.stable_id = stable_id
    dataset.hosted_url = hosted_url
    dataset.feed = MagicMock()
    dataset.feed.id = feed_id
    dataset.feed.stable_id = feed_stable_id
    return dataset


class TestGtfsChangeTrackerHandler(unittest.TestCase):
    """Tests for the HTTP handler function."""

    app = flask.Flask(__name__)

    def _request(self, payload):
        with self.app.test_request_context(json=payload):
            response = gtfs_change_tracker(flask.request)
        with self.app.app_context():
            return response.status_code, response.get_json()

    def test_missing_all_params(self):
        status, body = self._request({})
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "error")
        self.assertIn("required", body["error"])

    def test_missing_one_param(self):
        status, body = self._request(
            {"feed_stable_id": "mdb-1", "base_dataset_stable_id": "mdb-1-20240101"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "error")

    def test_missing_bucket_env(self):
        os.environ.pop("DATASETS_BUCKET_NAME", None)
        status, body = self._request(
            {
                "feed_stable_id": "mdb-1",
                "base_dataset_stable_id": "mdb-1-20240101",
                "new_dataset_stable_id": "mdb-1-20240201",
            }
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "error")
        self.assertIn("DATASETS_BUCKET_NAME", body["error"])

    @patch("main.GtfsChangeTracker")
    def test_success(self, mock_tracker_cls):
        os.environ["DATASETS_BUCKET_NAME"] = "test-bucket"
        os.environ["DATASETS_BUCKET_MOUNT"] = "/mobilitydata-datasets"
        instance = MagicMock()
        instance.run.return_value = {
            "message": "Changelog generated successfully.",
            "changelog_url": "https://storage.googleapis.com/test-bucket/mdb-1/c1/c1_p1_changelog.json",
        }
        mock_tracker_cls.return_value = instance

        status, body = self._request(
            {
                "feed_stable_id": "mdb-1",
                "base_dataset_stable_id": "mdb-1-20240101",
                "new_dataset_stable_id": "mdb-1-20240201",
            }
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "success")
        self.assertIn("changelog_url", body)
        mock_tracker_cls.assert_called_once_with(
            feed_stable_id="mdb-1",
            base_dataset_stable_id="mdb-1-20240101",
            new_dataset_stable_id="mdb-1-20240201",
            bucket_name="test-bucket",
            bucket_mount="/mobilitydata-datasets",
            allow_overwrite=False,
            dry_run=False,
        )

    @patch("main.GtfsChangeTracker")
    def test_allow_overwrite_and_dry_run_passed(self, mock_tracker_cls):
        os.environ["DATASETS_BUCKET_NAME"] = "test-bucket"
        os.environ["DATASETS_BUCKET_MOUNT"] = "/mobilitydata-datasets"
        instance = MagicMock()
        instance.run.return_value = {"message": "Dry run completed.", "summary": {}}
        mock_tracker_cls.return_value = instance

        self._request(
            {
                "feed_stable_id": "mdb-1",
                "base_dataset_stable_id": "mdb-1-20240101",
                "new_dataset_stable_id": "mdb-1-20240201",
                "allow_overwrite": True,
                "dry_run": True,
            }
        )
        mock_tracker_cls.assert_called_once_with(
            feed_stable_id="mdb-1",
            base_dataset_stable_id="mdb-1-20240101",
            new_dataset_stable_id="mdb-1-20240201",
            bucket_name="test-bucket",
            bucket_mount="/mobilitydata-datasets",
            allow_overwrite=True,
            dry_run=True,
        )

    @patch("main.GtfsChangeTracker")
    def test_exception_returns_200_with_error(self, mock_tracker_cls):
        """All exceptions return HTTP 200 to suppress GCP retries."""
        os.environ["DATASETS_BUCKET_NAME"] = "test-bucket"
        instance = MagicMock()
        instance.run.side_effect = Exception("something went wrong")
        mock_tracker_cls.return_value = instance

        status, body = self._request(
            {
                "feed_stable_id": "mdb-1",
                "base_dataset_stable_id": "mdb-1-20240101",
                "new_dataset_stable_id": "mdb-1-20240201",
            }
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "error")
        self.assertIn("something went wrong", body["error"])


class TestGtfsChangeTrackerRun(unittest.TestCase):
    """Tests for GtfsChangeTracker.run() with mocked collaborators."""

    def setUp(self):
        os.environ["DATASETS_BUCKET_NAME"] = "test-bucket"
        self.tracker = GtfsChangeTracker(
            feed_stable_id="mdb-1",
            base_dataset_stable_id="mdb-1-20240101",
            new_dataset_stable_id="mdb-1-20240201",
            bucket_name="test-bucket",
            bucket_mount="/mobilitydata-datasets",
        )

    @patch("main.storage.Client")
    @patch("main.GtfsChangeTracker._save_changelog_record")
    @patch("main.GtfsChangeTracker._upload_changelog")
    @patch("main.GtfsChangeTracker._extracted_dir")
    @patch("main.GtfsChangeTracker._resolve_datasets")
    def test_run_happy_path(
        self, mock_resolve, mock_extracted_dir, mock_upload, mock_save, mock_storage
    ):
        mock_storage.return_value.bucket.return_value.blob.return_value.exists.return_value = (
            False
        )
        mock_resolve.return_value = ("prev-uuid", "curr-uuid", "feed-uuid")
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
            feed_uuid="feed-uuid",
            prev_dataset_uuid="prev-uuid",
            curr_dataset_uuid="curr-uuid",
            changelog_url=changelog_url,
            diff_summary={"total_changes": 42},
        )
        self.assertEqual(result["changelog_url"], changelog_url)

    @patch("main.storage.Client")
    @patch("main.GtfsChangeTracker._resolve_datasets")
    def test_run_raises_when_resolve_fails(self, mock_resolve, mock_storage):
        mock_storage.return_value.bucket.return_value.blob.return_value.exists.return_value = (
            False
        )
        mock_resolve.side_effect = ValueError(
            "Previous dataset not found: mdb-1-20240101"
        )
        with self.assertRaises(ValueError):
            self.tracker.run()

    @patch("main.storage.Client")
    def test_run_skips_when_changelog_exists(self, mock_storage):
        mock_storage.return_value.bucket.return_value.blob.return_value.exists.return_value = (
            True
        )
        result = self.tracker.run()
        self.assertIn("already exists", result["message"])
        self.assertIn("changelog_url", result)

    @patch("main.storage.Client")
    @patch("main.GtfsChangeTracker._save_changelog_record")
    @patch("main.GtfsChangeTracker._upload_changelog")
    @patch("main.GtfsChangeTracker._extracted_dir")
    @patch("main.GtfsChangeTracker._resolve_datasets")
    def test_allow_overwrite_skips_existence_check(
        self, mock_resolve, mock_extracted_dir, mock_upload, mock_save, mock_storage
    ):
        """allow_overwrite=True should proceed even when the blob exists."""
        mock_storage.return_value.bucket.return_value.blob.return_value.exists.return_value = (
            True
        )
        mock_resolve.return_value = ("prev-uuid", "curr-uuid", "feed-uuid")
        mock_extracted_dir.side_effect = [
            "/mobilitydata-datasets/mdb-1/mdb-1-20240101/extracted",
            "/mobilitydata-datasets/mdb-1/mdb-1-20240201/extracted",
        ]
        fake_diff = MagicMock()
        fake_diff.summary.model_dump.return_value = {}
        fake_diff.model_dump_json.return_value = "{}"
        mock_upload.return_value = (
            "https://storage.googleapis.com/test-bucket/changelog.json"
        )

        tracker = GtfsChangeTracker(
            feed_stable_id="mdb-1",
            base_dataset_stable_id="mdb-1-20240101",
            new_dataset_stable_id="mdb-1-20240201",
            bucket_name="test-bucket",
            bucket_mount="/mobilitydata-datasets",
            allow_overwrite=True,
        )
        with patch("main.diff_feeds", return_value=fake_diff, create=True):
            result = tracker.run()
        self.assertIn("generated successfully", result["message"])
        mock_upload.assert_called_once()

    @patch("main.storage.Client")
    @patch("main.GtfsChangeTracker._upload_changelog")
    @patch("main.GtfsChangeTracker._extracted_dir")
    @patch("main.GtfsChangeTracker._resolve_datasets")
    def test_dry_run_skips_upload_and_db(
        self, mock_resolve, mock_extracted_dir, mock_upload, mock_storage
    ):
        """dry_run=True should compute the diff but not upload or write to DB."""
        mock_storage.return_value.bucket.return_value.blob.return_value.exists.return_value = (
            False
        )
        mock_resolve.return_value = ("prev-uuid", "curr-uuid", "feed-uuid")
        mock_extracted_dir.side_effect = [
            "/mobilitydata-datasets/mdb-1/mdb-1-20240101/extracted",
            "/mobilitydata-datasets/mdb-1/mdb-1-20240201/extracted",
        ]
        fake_diff = MagicMock()
        fake_diff.summary.model_dump.return_value = {"total_changes": 5}

        tracker = GtfsChangeTracker(
            feed_stable_id="mdb-1",
            base_dataset_stable_id="mdb-1-20240101",
            new_dataset_stable_id="mdb-1-20240201",
            bucket_name="test-bucket",
            bucket_mount="/mobilitydata-datasets",
            dry_run=True,
        )
        with patch("main.diff_feeds", return_value=fake_diff, create=True):
            result = tracker.run()

        self.assertIn("Dry run", result["message"])
        self.assertIn("summary", result)
        mock_upload.assert_not_called()


class TestResolveDatasets(unittest.TestCase):
    """Tests for _resolve_datasets — verifies plain string UUIDs are returned."""

    def setUp(self):
        self.tracker = GtfsChangeTracker(
            feed_stable_id="mdb-1",
            base_dataset_stable_id="mdb-1-20240101",
            new_dataset_stable_id="mdb-1-20240201",
            bucket_name="my-bucket",
            bucket_mount="/mobilitydata-datasets",
        )

    def _mock_session_with_datasets(self):
        prev_ds = MagicMock()
        prev_ds.id = "prev-uuid"
        prev_ds.stable_id = "mdb-1-20240101"

        curr_ds = MagicMock()
        curr_ds.id = "curr-uuid"
        curr_ds.stable_id = "mdb-1-20240201"
        curr_ds.feed.id = "feed-uuid"
        curr_ds.feed.stable_id = "mdb-1"

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.one_or_none.side_effect = [
            prev_ds,
            curr_ds,
        ]
        return mock_session

    @patch("main.with_db_session", lambda f: f)
    def test_returns_plain_string_uuids(self):
        """_resolve_datasets must return str UUIDs, not ORM objects.
        If ORM objects were returned, accessing lazy attributes after session
        close would raise DetachedInstanceError in production."""
        mock_session = self._mock_session_with_datasets()
        result = self.tracker._resolve_datasets(db_session=mock_session)
        prev_uuid, curr_uuid, feed_uuid = result
        self.assertIsInstance(prev_uuid, str, "prev_uuid must be a plain string")
        self.assertIsInstance(curr_uuid, str, "curr_uuid must be a plain string")
        self.assertIsInstance(feed_uuid, str, "feed_uuid must be a plain string")
        self.assertEqual(prev_uuid, "prev-uuid")
        self.assertEqual(curr_uuid, "curr-uuid")
        self.assertEqual(feed_uuid, "feed-uuid")

    @patch("main.with_db_session", lambda f: f)
    def test_raises_when_feed_mismatch(self):
        prev_ds = MagicMock()
        prev_ds.id = "prev-uuid"
        curr_ds = MagicMock()
        curr_ds.id = "curr-uuid"
        curr_ds.feed.stable_id = "mdb-999"  # wrong feed

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.one_or_none.side_effect = [
            prev_ds,
            curr_ds,
        ]
        with self.assertRaises(ValueError, msg="should reject dataset from wrong feed"):
            self.tracker._resolve_datasets(db_session=mock_session)


class TestExtractedDir(unittest.TestCase):
    def setUp(self):
        self.tracker = GtfsChangeTracker(
            feed_stable_id="mdb-1",
            base_dataset_stable_id="mdb-1-20240101",
            new_dataset_stable_id="mdb-1-20240201",
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
            feed_stable_id="mdb-1",
            base_dataset_stable_id="mdb-1-20240101",
            new_dataset_stable_id="mdb-1-20240201",
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
