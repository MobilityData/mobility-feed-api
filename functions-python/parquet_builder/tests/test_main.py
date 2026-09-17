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
"""The orchestration: claiming, converting, publishing, and failing safely.

Only Google Cloud Storage is faked. The archive really is a zip, and it really is
extracted and converted, so the wiring between the phases is exercised rather than
asserted about.
"""

import io
import json
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import flask
import pytest

import main

pytest.importorskip("duckdb")

FEED = "mdb-1210"
DATASET = "mdb-1210-202402121801"
BUCKET = "test-datasets"
PUBLIC = "https://files.example.org"

AGENCY = "agency_id,agency_name,agency_url,agency_timezone\n1,T,https://e.org,UTC\n"
STOPS = "stop_id,stop_name\nS1,First\n"


def _zip_bytes(nested: bool = False) -> bytes:
    buffer = io.BytesIO()
    prefix = "feed/" if nested else ""
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(f"{prefix}agency.txt", AGENCY)
        zf.writestr(f"{prefix}stops.txt", STOPS)
    return buffer.getvalue()


class FakeBlob:
    def __init__(self, name, store, payload=None):
        self.name = name
        self._store = store
        self._payload = payload
        self.size = len(payload) if payload else 0
        self.public = False

    def exists(self):
        return self._payload is not None

    def reload(self):
        pass

    def download_to_filename(self, path):
        Path(path).write_bytes(self._payload)

    def upload_from_filename(self, path):
        self._store.uploaded[self.name] = Path(path).read_bytes()

    def make_public(self):
        self.public = True
        self._store.made_public.add(self.name)

    def delete(self):
        self._store.deleted.append(self.name)


class FakeBucket:
    def __init__(self, archive: bytes, existing=()):
        self.name = BUCKET
        self.uploaded = {}
        self.deleted = []
        self.made_public = set()
        self._archive = archive
        self._existing = list(existing)

    def blob(self, name):
        archive_path = f"{FEED}/{DATASET}/{DATASET}.zip"
        payload = self._archive if name == archive_path else None
        return FakeBlob(name, self, payload)

    def list_blobs(self, prefix):
        return [FakeBlob(n, self) for n in self._existing if n.startswith(prefix)]


class BuildTestCase(unittest.TestCase):
    def setUp(self):
        self.bucket = FakeBucket(_zip_bytes())
        self.tracker = MagicMock()
        self.tracker.try_acquire.return_value = True
        self.session = MagicMock()

        client = MagicMock()
        client.get_bucket.return_value = self.bucket
        self._patches = [
            patch.object(main.storage, "Client", return_value=client),
            patch.object(main, "TaskExecutionTracker", return_value=self.tracker),
            patch.dict(
                main.os.environ,
                {"DATASETS_BUCKET_NAME": BUCKET, "PUBLIC_HOSTED_DATASETS_URL": PUBLIC},
            ),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

    def build(self, **kwargs):
        return main.build_parquet(
            feed_stable_id=FEED,
            dataset_stable_id=DATASET,
            bucket_name=BUCKET,
            db_session=self.session,
            **kwargs,
        )


class TestValidation(unittest.TestCase):
    def _call(self, payload):
        with flask.Flask(__name__).test_request_context(json=payload):
            return main.build_parquet_handler(flask.request)

    def test_missing_identifiers_are_rejected(self):
        self.assertIn("error", self._call({"feed_stable_id": FEED}))
        self.assertIn("error", self._call({}))

    def test_a_dataset_belonging_to_another_feed_is_rejected(self):
        result = self._call({"feed_stable_id": "mdb-999", "dataset_stable_id": DATASET})
        self.assertIn("not a prefix", result["error"])

    def test_a_missing_bucket_setting_is_reported(self):
        with patch.dict(main.os.environ, {}, clear=True):
            result = self._call({"feed_stable_id": FEED, "dataset_stable_id": DATASET})
        self.assertIn("DATASETS_BUCKET_NAME", result["error"])

    def test_a_build_failure_returns_200_so_cloud_tasks_does_not_retry(self):
        """A corrupt archive is still corrupt on the second delivery."""
        with patch.dict(
            main.os.environ, {"DATASETS_BUCKET_NAME": BUCKET}
        ), patch.object(main, "build_parquet", side_effect=RuntimeError("boom")):
            result = self._call({"feed_stable_id": FEED, "dataset_stable_id": DATASET})
        # A dict, not a raise: functions-framework would turn a raise into a 500.
        self.assertEqual(result["status"], "error")
        self.assertIn("boom", result["error"])


class TestClaiming(BuildTestCase):
    def test_a_refused_claim_does_no_work(self):
        self.tracker.try_acquire.return_value = False

        result = self.build()

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(self.bucket.uploaded, {}, "nothing may be published")
        self.tracker.mark_completed.assert_not_called()

    def test_force_reopens_a_finished_dataset_before_claiming(self):
        self.build(force=True)

        self.tracker.release_for_retry.assert_called_once_with(DATASET)

    def test_without_force_a_finished_dataset_is_not_reopened(self):
        self.build()

        self.tracker.release_for_retry.assert_not_called()


class TestSuccessfulBuild(BuildTestCase):
    def test_publishes_a_parquet_per_table_plus_a_manifest(self):
        result = self.build()

        self.assertEqual(result["status"], "success")
        self.assertEqual(
            sorted(self.bucket.uploaded),
            [
                f"{FEED}/{DATASET}/parquet/agency.parquet",
                f"{FEED}/{DATASET}/parquet/manifest.json",
                f"{FEED}/{DATASET}/parquet/stops.parquet",
            ],
        )

    def test_every_published_object_is_public(self):
        """The reader discards query strings, so signed URLs cannot work."""
        self.build()

        self.assertEqual(self.bucket.made_public, set(self.bucket.uploaded))

    def test_the_manifest_lists_the_tables(self):
        self.build()

        manifest = json.loads(
            self.bucket.uploaded[f"{FEED}/{DATASET}/parquet/manifest.json"]
        )
        self.assertEqual([t["name"] for t in manifest["tables"]], ["agency", "stops"])

    def test_records_where_the_files_are(self):
        self.build()

        _, kwargs = self.tracker.mark_completed.call_args
        metadata = kwargs["metadata"]
        self.assertEqual(metadata["base_url"], f"{PUBLIC}/{FEED}/{DATASET}/parquet")
        self.assertEqual([t["name"] for t in metadata["tables"]], ["agency", "stops"])
        self.assertEqual(metadata["phase"], "done")

    def test_reports_progress_through_every_phase(self):
        self.build()

        phases = [
            call.kwargs["metadata"]["phase"]
            for call in self.tracker.heartbeat.call_args_list
        ]
        for expected in (
            "start",
            "download",
            "extract",
            "convert",
            "upload",
            "summarise",
        ):
            self.assertIn(expected, phases, f"no {expected} reading was published")

    def test_download_progress_is_reported_in_bytes(self):
        """The reader formats this phase's numbers as a size, not a count."""
        self.build()

        downloads = [
            call.kwargs["metadata"]
            for call in self.tracker.heartbeat.call_args_list
            if call.kwargs["metadata"]["phase"] == "download"
        ]
        self.assertTrue(downloads)
        self.assertEqual(downloads[-1]["total"], len(_zip_bytes()))
        self.assertEqual(downloads[-1]["done"], len(_zip_bytes()))

    def test_a_stale_previous_build_is_cleared_first(self):
        """A rebuild with fewer tables must not leave an orphan behind."""
        self.bucket._existing = [f"{FEED}/{DATASET}/parquet/gone.parquet"]

        self.build()

        self.assertIn(f"{FEED}/{DATASET}/parquet/gone.parquet", self.bucket.deleted)

    def test_a_feed_wrapped_in_a_directory_still_converts(self):
        """Some producers nest the files; the converter looks in one place."""
        self.bucket._archive = _zip_bytes(nested=True)

        result = self.build()

        self.assertEqual(sorted(result["tables"]), ["agency", "stops"])


class TestFailure(BuildTestCase):
    def test_a_missing_archive_is_recorded_and_released(self):
        self.bucket._archive = None
        self.bucket.blob = lambda name: FakeBlob(name, self.bucket, None)

        with self.assertRaises(FileNotFoundError):
            self.build()

        # Recorded as failed rather than left holding the claim until the lease runs
        # out, so the dataset can be retried at once.
        self.tracker.mark_failed.assert_called_once()
        self.assertIn(
            "not found", self.tracker.mark_failed.call_args.kwargs["error_message"]
        )

    def test_a_conversion_failure_releases_the_claim(self):
        with patch.object(
            main, "convert_to_parquet", side_effect=RuntimeError("no memory")
        ):
            with self.assertRaises(RuntimeError):
                self.build()

        self.tracker.mark_failed.assert_called_once()
        self.tracker.mark_completed.assert_not_called()
        self.assertEqual(self.bucket.uploaded, {})


if __name__ == "__main__":
    unittest.main()
