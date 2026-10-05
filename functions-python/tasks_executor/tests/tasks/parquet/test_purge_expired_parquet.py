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
"""The sweep must remove the objects and the row together, or not at all."""

import unittest
from unittest.mock import MagicMock, patch

from tasks.parquet.purge_expired_parquet import (
    _delete_prefix,
    purge_expired_parquet,
    purge_expired_parquet_handler,
)

DATASET = "mdb-1210-202402121801"
FEED = "mdb-1210"
BUCKET = {"DATASETS_BUCKET_NAME": "test-datasets"}


def _expired(*dataset_ids):
    rows = []
    for dataset_id in dataset_ids:
        row = MagicMock()
        row.entity_id = dataset_id
        rows.append(row)
    return rows


class FakeBlob:
    def __init__(self, name, store):
        self.name = name
        self._store = store

    def delete(self):
        self._store.deleted.append(self.name)


class FakeBucket:
    def __init__(self, objects=()):
        self.objects = list(objects)
        self.deleted = []

    def list_blobs(self, prefix):
        return [FakeBlob(n, self) for n in self.objects if n.startswith(prefix)]


class PurgeTestCase(unittest.TestCase):
    def setUp(self):
        self.session = MagicMock()
        self.bucket = FakeBucket(
            [
                f"{FEED}/{DATASET}/parquet/stops.parquet",
                f"{FEED}/{DATASET}/parquet/manifest.json",
                # A sibling artifact that must survive: only the parquet prefix expires.
                f"{FEED}/{DATASET}/pmtiles/stops.pmtiles",
                f"{FEED}/{DATASET}/{DATASET}.zip",
            ]
        )
        client = MagicMock()
        client.get_bucket.return_value = self.bucket
        self._storage = patch("google.cloud.storage.Client", return_value=client)
        self._storage.start()
        self.addCleanup(self._storage.stop)

    def _run(self, rows, **kwargs):
        self.session.execute.return_value.all.return_value = rows
        with patch.dict("os.environ", BUCKET):
            return purge_expired_parquet(db_session=self.session, **kwargs)


class TestDryRun(PurgeTestCase):
    def test_reports_without_deleting_anything(self):
        result = self._run(_expired(DATASET), dry_run=True)

        self.assertEqual(result["total_expired"], 1)
        self.assertEqual(result["datasets"], [DATASET])
        self.assertEqual(self.bucket.deleted, [], "dry run deleted objects")

    def test_dry_run_is_the_default(self):
        with patch.dict("os.environ", BUCKET):
            self.session.execute.return_value.all.return_value = _expired(DATASET)
            result = purge_expired_parquet(db_session=self.session)

        self.assertIn("Dry run", result["message"])
        self.assertEqual(self.bucket.deleted, [])


class TestPurge(PurgeTestCase):
    def test_deletes_only_the_parquet_prefix(self):
        """The dataset's other artifacts are not this task's to remove."""
        self._run(_expired(DATASET), dry_run=False)

        self.assertEqual(
            sorted(self.bucket.deleted),
            [
                f"{FEED}/{DATASET}/parquet/manifest.json",
                f"{FEED}/{DATASET}/parquet/stops.parquet",
            ],
        )

    def test_removes_the_tracking_row_as_well(self):
        """Objects without the row would leave the API advertising a dead base_url."""
        result = self._run(_expired(DATASET), dry_run=False)

        statements = [str(call.args[0]) for call in self.session.execute.call_args_list]
        self.assertTrue(
            any("DELETE FROM task_execution_log" in s for s in statements),
            f"the tracking row was never deleted: {statements}",
        )
        self.assertEqual(result["total_purged"], 1)
        self.assertTrue(self.session.commit.called)

    def test_one_failure_does_not_abandon_the_rest(self):
        other = "mdb-99-202402121801"

        def blow_up_on_first(prefix):
            if DATASET in prefix:
                raise RuntimeError("permission denied")
            return []

        self.bucket.list_blobs = blow_up_on_first
        result = self._run(_expired(DATASET, other), dry_run=False)

        self.assertEqual(result["total_purged"], 1)
        self.assertEqual(result["datasets"], [other])
        self.assertTrue(self.session.rollback.called)

    def test_limit_caps_the_batch(self):
        result = self._run(
            _expired(DATASET, "mdb-99-202402121801"), dry_run=True, limit=1
        )

        self.assertEqual(result["total_expired"], 1)

    def test_a_missing_bucket_setting_is_an_error(self):
        with patch.dict("os.environ", {}, clear=True):
            self.session.execute.return_value.all.return_value = []
            with self.assertRaises(ValueError):
                purge_expired_parquet(db_session=self.session)


class TestPrefix(unittest.TestCase):
    def test_the_feed_prefix_is_the_dataset_id_without_its_timestamp(self):
        bucket = FakeBucket([f"{FEED}/{DATASET}/parquet/stops.parquet"])

        deleted = _delete_prefix(bucket, DATASET)

        self.assertEqual(deleted, 1)


class TestHandler(PurgeTestCase):
    def test_payload_defaults_to_a_dry_run(self):
        self.session.execute.return_value.all.return_value = _expired(DATASET)
        with patch.dict("os.environ", BUCKET), patch(
            "tasks.parquet.purge_expired_parquet.purge_expired_parquet"
        ) as inner:
            purge_expired_parquet_handler({})

        inner.assert_called_once_with(dry_run=True, limit=None)


if __name__ == "__main__":
    unittest.main()
