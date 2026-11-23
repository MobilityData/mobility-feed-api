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
import os
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from google.cloud.exceptions import NotFound

from shared.helpers.cdn_cache import LATEST_DATASET_CACHE_CONTROL
from tasks.dataset_files.backfill_latest_cache_control import (
    backfill_latest_cache_control_handler,
)

MODULE = "tasks.dataset_files.backfill_latest_cache_control"


class TestBackfillLatestCacheControl(unittest.TestCase):
    def _run(self, stable_ids, payload, patch_errors=None):
        """Runs the handler with the given feeds; patch_errors maps an object name to the
        exception its patch raises. Returns (result, blobs by name, query mock)."""
        patch_errors = patch_errors or {}
        blobs = {}

        def make_blob(name):
            blob = MagicMock()
            blob.name = name
            blob.patch.side_effect = patch_errors.get(name)
            blobs[name] = blob
            return blob

        with patch(
            f"{MODULE}.query_latest_feed_stable_ids", return_value=stable_ids
        ) as mock_query, patch("google.cloud.storage.Client") as mock_client:
            mock_client.return_value.bucket.return_value.blob.side_effect = make_blob
            result = backfill_latest_cache_control_handler(
                payload, db_session=MagicMock()
            )
        return result, blobs, mock_query

    def test_dry_run_counts_without_patching(self):
        result, blobs, _ = self._run(["mdb-1", "mdb-2"], {"bucket_name": "b"})

        self.assertEqual(result["total_feeds"], 2)
        self.assertEqual(result["updated"], 0)
        self.assertEqual(blobs, {})

    def test_patches_latest_zip_of_each_feed(self):
        result, blobs, _ = self._run(
            ["mdb-1", "mdb-2"], {"bucket_name": "b", "dry_run": False}
        )

        self.assertEqual(result["updated"], 2)
        self.assertEqual(set(blobs), {"mdb-1/latest.zip", "mdb-2/latest.zip"})
        for blob in blobs.values():
            self.assertEqual(blob.cache_control, LATEST_DATASET_CACHE_CONTROL)
            blob.patch.assert_called_once()

    def test_missing_object_and_errors_are_reported_without_stopping(self):
        result, blobs, _ = self._run(
            ["mdb-1", "mdb-2", "mdb-3"],
            {"bucket_name": "b", "dry_run": False},
            patch_errors={
                "mdb-1/latest.zip": NotFound("gone"),
                "mdb-2/latest.zip": Exception("503"),
            },
        )

        self.assertEqual(result["not_found"], ["mdb-1"])
        self.assertEqual(result["errors"], ["mdb-2"])
        self.assertEqual(result["updated"], 1)
        blobs["mdb-3/latest.zip"].patch.assert_called_once()

    def test_passes_filters_to_query(self):
        _, _, mock_query = self._run(
            [],
            {
                "bucket_name": "b",
                "uploaded_before": "2026-11-10T18:30:00+00:00",
                "limit": "5",
            },
        )

        _, uploaded_before, limit = mock_query.call_args.args
        self.assertEqual(
            uploaded_before, datetime.fromisoformat("2026-11-10T18:30:00+00:00")
        )
        self.assertEqual(limit, 5)

    @patch.dict(os.environ, {}, clear=True)
    def test_requires_bucket(self):
        with self.assertRaises(ValueError):
            backfill_latest_cache_control_handler({}, db_session=MagicMock())


if __name__ == "__main__":
    unittest.main()
