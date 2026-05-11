import base64
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from shared.database.database import with_db_session
from test_shared.test_utils.database_utils import default_db_url
from tasks.dataset_files.backfill_dataset_hash_md5 import (
    backfill_dataset_hash_md5,
    backfill_dataset_hash_md5_handler,
    _build_blob_path,
    _read_md5_from_gcs,
    DEFAULT_LIMIT,
)


class TestBuildBlobPath(unittest.TestCase):
    def test_constructs_expected_path(self):
        result = _build_blob_path("mdb-779", "mdb-779-202507082048")
        self.assertEqual(
            result, "mdb-779/mdb-779-202507082048/mdb-779-202507082048.zip"
        )

    def test_generic_feed_and_dataset(self):
        result = _build_blob_path("feed-1", "feed-1-20240101")
        self.assertEqual(result, "feed-1/feed-1-20240101/feed-1-20240101.zip")


class TestReadMd5FromGcs(unittest.TestCase):
    def test_returns_hex_md5(self):
        raw_md5 = b"\x09\x8f\x6b\xcd\x46\x21\xd3\x73\xca\xde\x4e\x83\x26\x27\xb4\xf6"
        b64_md5 = base64.b64encode(raw_md5).decode()

        mock_blob = MagicMock()
        mock_blob.md5_hash = b64_md5
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        result = _read_md5_from_gcs(mock_bucket, "some/path.zip")
        self.assertEqual(result, raw_md5.hex())
        mock_blob.reload.assert_called_once()

    def test_returns_none_when_blob_not_found(self):
        from google.cloud.exceptions import NotFound

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.reload.side_effect = NotFound("blob not found")
        mock_bucket.blob.return_value = mock_blob

        result = _read_md5_from_gcs(mock_bucket, "missing/path.zip")
        self.assertIsNone(result)

    def test_returns_none_when_md5_hash_is_none(self):
        mock_blob = MagicMock()
        mock_blob.md5_hash = None
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        result = _read_md5_from_gcs(mock_bucket, "some/path.zip")
        self.assertIsNone(result)


class TestBackfillDatasetHashMd5Handler(unittest.TestCase):
    @patch("tasks.dataset_files.backfill_dataset_hash_md5.backfill_dataset_hash_md5")
    def test_handler_passes_default_params(self, mock_backfill):
        mock_backfill.return_value = {
            "message": "Dry run: 5 datasets eligible.",
            "total_candidates": 5,
        }
        result = backfill_dataset_hash_md5_handler({})
        mock_backfill.assert_called_once_with(
            dry_run=True,
            only_latest=True,
            only_missing_hashes=True,
            limit=10,
        )
        self.assertEqual(result["total_candidates"], 5)

    @patch("tasks.dataset_files.backfill_dataset_hash_md5.backfill_dataset_hash_md5")
    def test_handler_passes_custom_params(self, mock_backfill):
        mock_backfill.return_value = {"message": "done", "total_updated": 3}
        backfill_dataset_hash_md5_handler(
            {
                "dry_run": False,
                "only_latest": False,
                "only_missing_hashes": False,
                "limit": 100,
            }
        )
        mock_backfill.assert_called_once_with(
            dry_run=False,
            only_latest=False,
            only_missing_hashes=False,
            limit=100,
        )

    @patch("tasks.dataset_files.backfill_dataset_hash_md5.backfill_dataset_hash_md5")
    def test_handler_string_limit_is_converted_to_int(self, mock_backfill):
        mock_backfill.return_value = {}
        backfill_dataset_hash_md5_handler({"limit": "42"})
        _, kwargs = mock_backfill.call_args
        self.assertEqual(kwargs["limit"], 42)
        self.assertIsInstance(kwargs["limit"], int)

    @patch("tasks.dataset_files.backfill_dataset_hash_md5.backfill_dataset_hash_md5")
    def test_handler_null_limit_means_no_limit(self, mock_backfill):
        mock_backfill.return_value = {}
        backfill_dataset_hash_md5_handler({"limit": None})
        _, kwargs = mock_backfill.call_args
        self.assertIsNone(kwargs["limit"])

    @patch("tasks.dataset_files.backfill_dataset_hash_md5.backfill_dataset_hash_md5")
    def test_handler_invalid_limit_means_default_limit(self, mock_backfill):
        mock_backfill.return_value = {}
        backfill_dataset_hash_md5_handler({"limit": "not-a-number"})
        _, kwargs = mock_backfill.call_args
        self.assertIs(kwargs["limit"], DEFAULT_LIMIT)


class TestBackfillDatasetHashMd5DryRun(unittest.TestCase):
    @with_db_session(db_url=default_db_url)
    def test_dry_run_returns_count_without_db_changes(self, db_session):
        result = backfill_dataset_hash_md5(
            db_session=db_session,
            dry_run=True,
            only_latest=True,
            only_missing_hashes=True,
            limit=10,
        )
        self.assertIn("Dry run", result["message"])
        self.assertIn("total_candidates", result)
        self.assertGreaterEqual(result["total_candidates"], 0)


class TestBackfillDatasetHashMd5Processing(unittest.TestCase):
    def _make_fake_dataset(self, dataset_stable_id, feed_stable_id="mdb-1"):
        fake_feed = SimpleNamespace(stable_id=feed_stable_id)
        return SimpleNamespace(
            stable_id=dataset_stable_id,
            hash_md5=None,
            feed=fake_feed,
        )

    def _make_mock_db_session(self, datasets):
        db_session = MagicMock()
        query_mock = MagicMock()
        filter1 = MagicMock()
        filter2 = MagicMock()
        filter3 = MagicMock()
        options_mock = MagicMock()
        join_mock = MagicMock()

        db_session.query.return_value = query_mock
        query_mock.filter.return_value = filter1
        filter1.join.return_value = join_mock
        join_mock.filter.return_value = filter2
        filter2.filter.return_value = filter3
        filter3.options.return_value = options_mock
        # Support the full chain used in _build_query
        query_mock.filter.return_value.join.return_value.filter.return_value.options.return_value = (
            options_mock
        )
        options_mock.count.return_value = len(datasets)
        options_mock.limit.return_value.all.return_value = datasets
        return db_session, options_mock

    @patch.dict(os.environ, {"DATASETS_BUCKET_NAME": "test-bucket"})
    @patch("tasks.dataset_files.backfill_dataset_hash_md5._build_query")
    @patch("tasks.dataset_files.backfill_dataset_hash_md5._read_md5_from_gcs")
    @patch("tasks.dataset_files.backfill_dataset_hash_md5.storage.Client")
    def test_updates_md5_and_commits_in_batches(
        self, mock_storage_client, mock_read_md5, mock_build_query
    ):
        raw_md5 = "098f6bcd4621d373cade4e832627b4f6"

        datasets = [
            self._make_fake_dataset(f"mdb-1-2024010{i}", "mdb-1") for i in range(3)
        ]

        mock_query = MagicMock()
        mock_query.count.return_value = 3
        mock_query.limit.return_value.all.return_value = datasets
        mock_build_query.return_value = mock_query

        mock_read_md5.return_value = raw_md5
        mock_bucket = MagicMock()
        mock_storage_client.return_value.bucket.return_value = mock_bucket

        db_session = MagicMock()

        result = backfill_dataset_hash_md5(
            db_session=db_session,
            dry_run=False,
            only_latest=True,
            only_missing_hashes=True,
            limit=3,
        )

        self.assertEqual(result["total_updated"], 3)
        self.assertEqual(result["total_skipped"], 0)
        for ds in datasets:
            self.assertEqual(ds.hash_md5, raw_md5)
        # Final commit called for remaining datasets (3 < BATCH_COMMIT_SIZE=50)
        db_session.commit.assert_called_once()

        # Verify blob paths are constructed from stable IDs
        for i, ds in enumerate(datasets):
            expected_blob = f"mdb-1/mdb-1-2024010{i}/mdb-1-2024010{i}.zip"
            mock_read_md5.assert_any_call(mock_bucket, expected_blob)

    @patch.dict(os.environ, {"DATASETS_BUCKET_NAME": "test-bucket"}, clear=False)
    @patch("tasks.dataset_files.backfill_dataset_hash_md5._build_query")
    @patch("tasks.dataset_files.backfill_dataset_hash_md5._read_md5_from_gcs")
    @patch("tasks.dataset_files.backfill_dataset_hash_md5.storage.Client")
    def test_skips_datasets_when_gcs_blob_missing(
        self, mock_storage_client, mock_read_md5, mock_build_query
    ):
        datasets = [self._make_fake_dataset("mdb-1-20240101", "mdb-1")]
        mock_query = MagicMock()
        mock_query.count.return_value = 1
        mock_query.limit.return_value.all.return_value = datasets
        mock_build_query.return_value = mock_query

        mock_read_md5.return_value = None  # blob not found in GCS
        mock_storage_client.return_value.bucket.return_value = MagicMock()
        db_session = MagicMock()

        result = backfill_dataset_hash_md5(
            db_session=db_session,
            dry_run=False,
            only_latest=True,
            only_missing_hashes=True,
            limit=1,
        )

        self.assertEqual(result["total_updated"], 0)
        self.assertEqual(result["total_skipped"], 1)
        db_session.commit.assert_not_called()

    @patch.dict(os.environ, {"DATASETS_BUCKET_NAME": "test-bucket"})
    @patch("tasks.dataset_files.backfill_dataset_hash_md5._build_query")
    @patch("tasks.dataset_files.backfill_dataset_hash_md5._read_md5_from_gcs")
    @patch("tasks.dataset_files.backfill_dataset_hash_md5.storage.Client")
    def test_commits_in_batches_of_50(
        self, mock_storage_client, mock_read_md5, mock_build_query
    ):
        """Verify that commits happen every BATCH_COMMIT_SIZE=50 datasets."""
        from tasks.dataset_files.backfill_dataset_hash_md5 import BATCH_COMMIT_SIZE

        num_datasets = BATCH_COMMIT_SIZE + 10  # 60 total → 1 mid-batch commit + 1 final

        datasets = [
            self._make_fake_dataset(f"mdb-1-2024010{i}", "mdb-1")
            for i in range(num_datasets)
        ]

        mock_query = MagicMock()
        mock_query.count.return_value = num_datasets
        mock_query.limit.return_value.all.return_value = datasets
        mock_build_query.return_value = mock_query

        mock_read_md5.return_value = "abc123"
        mock_storage_client.return_value.bucket.return_value = MagicMock()
        db_session = MagicMock()

        result = backfill_dataset_hash_md5(
            db_session=db_session,
            dry_run=False,
            only_latest=True,
            only_missing_hashes=True,
            limit=num_datasets,
        )

        self.assertEqual(result["total_updated"], num_datasets)
        # 1 mid-batch commit (at 50) + 1 final commit (remaining 10) = 2 total
        self.assertEqual(db_session.commit.call_count, 2)

    @patch.dict(os.environ, {"DATASETS_BUCKET_NAME": "test-bucket"})
    @patch("tasks.dataset_files.backfill_dataset_hash_md5._build_query")
    @patch("tasks.dataset_files.backfill_dataset_hash_md5._read_md5_from_gcs")
    @patch("tasks.dataset_files.backfill_dataset_hash_md5.storage.Client")
    def test_no_limit_processes_all_datasets(
        self, mock_storage_client, mock_read_md5, mock_build_query
    ):
        """When limit=None, query.all() is called directly without .limit()."""
        datasets = [
            self._make_fake_dataset(f"mdb-1-2024010{i}", "mdb-1") for i in range(5)
        ]

        mock_query = MagicMock()
        mock_query.count.return_value = 5
        mock_query.all.return_value = datasets
        mock_build_query.return_value = mock_query

        mock_read_md5.return_value = "abc123"
        mock_storage_client.return_value.bucket.return_value = MagicMock()
        db_session = MagicMock()

        result = backfill_dataset_hash_md5(
            db_session=db_session,
            dry_run=False,
            limit=None,
        )

        self.assertEqual(result["total_updated"], 5)
        # .limit() should NOT be called when limit is None
        mock_query.limit.assert_not_called()
        mock_query.all.assert_called_once()
