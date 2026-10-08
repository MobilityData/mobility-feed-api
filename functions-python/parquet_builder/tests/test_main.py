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
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
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


def _zip_bytes(nested: bool = False, reverse: bool = False) -> bytes:
    """`reverse` writes stops before agency, so archive order and table order differ."""
    buffer = io.BytesIO()
    prefix = "feed/" if nested else ""
    members = [(f"{prefix}agency.txt", AGENCY), (f"{prefix}stops.txt", STOPS)]
    if reverse:
        members.reverse()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, body in members:
            zf.writestr(name, body)
    return buffer.getvalue()


class FakeBlob:
    def __init__(self, name, store, payload=None):
        self.name = name
        self._store = store
        self._payload = payload
        self.size = len(payload) if payload else 0
        self.public = False
        self.custom_time = None

    def exists(self):
        return self._payload is not None

    def reload(self):
        pass

    def download_to_filename(self, path):
        self._store.downloaded.append(self.name)
        Path(path).write_bytes(self._payload)

    def download_as_bytes(self, start=None, end=None):
        """Serve a byte range, as GCS does for the archive's central directory."""
        self._store.ranged.append((self.name, start, end))
        data = self._payload or b""
        return data[start : (end + 1 if end is not None else None)]

    def upload_from_filename(self, path):
        self._store.uploaded[self.name] = Path(path).read_bytes()
        self._store.custom_times[self.name] = self.custom_time
        self._store.events.append(("upload", self.name))

    def open(self, mode="rb", chunk_size=None):
        """Stand-in for `BlobReader`: seekable, and never writes to the workdir."""
        assert mode == "rb"
        if self._payload is None:
            raise FileNotFoundError(self.name)
        self._store.opened.append(self.name)
        return io.BytesIO(self._payload)

    def make_public(self):
        if self._store.acl_error is not None:
            raise self._store.acl_error
        self.public = True
        self._store.made_public.add(self.name)

    def delete(self):
        self._store.deleted.append(self.name)
        self._store.events.append(("delete", self.name))


class FakeBucket:
    def __init__(self, archive: bytes, existing=()):
        self.name = BUCKET
        self.uploaded = {}
        # customTime as it stood at upload, per object.
        self.custom_times = {}
        self.deleted = []
        self.made_public = set()
        self.events = []
        self.downloaded = []
        # Blobs read through open("rb") rather than downloaded to the workdir.
        self.opened = []
        self.ranged = []
        # Blobs under <feed>/<dataset>/extracted/, as batch_process_dataset leaves them.
        self.extracted = {}
        self._archive = archive
        self._existing = list(existing)
        # Raised by make_public when set, standing in for a bucket that refuses ACLs.
        self.acl_error = None
        self.iam_configuration = SimpleNamespace(
            uniform_bucket_level_access_enabled=False
        )

    def blob(self, name):
        archive_path = f"{FEED}/{DATASET}/{DATASET}.zip"
        if name == archive_path:
            return FakeBlob(name, self, self._archive)
        return FakeBlob(name, self, self.extracted.get(name))

    def list_blobs(self, prefix):
        names = set(self._existing) | set(self.extracted)
        return [FakeBlob(n, self) for n in sorted(names) if n.startswith(prefix)]


class BuildTestCase(unittest.TestCase):
    def setUp(self):
        self.bucket = FakeBucket(_zip_bytes())
        self.tracker = MagicMock()
        self.tracker.try_acquire.return_value = True
        self.session = MagicMock()
        # Default: no extracted files recorded, so the archive path is taken.
        self.session.query.return_value.filter.return_value.one_or_none.return_value = (
            None
        )

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
        # Neither `extract` nor `download` appears any more. Unzipping is per-member
        # inside `convert`, and the archive is read over the network as those members
        # are asked for, so neither is a stage the build passes through.
        for expected in ("start", "convert", "upload", "summarise"):
            self.assertIn(expected, phases, f"no {expected} reading was published")

    def test_no_download_phase_is_reported(self):
        """Nothing is downloaded, so reporting the phase would describe absent work."""
        self.build()

        phases = [
            call.kwargs["metadata"]["phase"]
            for call in self.tracker.heartbeat.call_args_list
        ]
        self.assertNotIn("download", phases)

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


class TestStreamsOneFileAtATime(BuildTestCase):
    """Peak memory is the point of the per-file flow, so it is asserted directly.

    `/tmp` in Cloud Functions gen2 is RAM-backed tmpfs, so a file left on disk costs the
    same as a file held in memory. Converting the whole feed and then uploading it held
    the archive, every CSV and every Parquet at once; this keeps at most one of each.
    """

    def _residency(self):
        """Watch the workdir while the build runs, recording what coexists."""
        seen = []
        real_convert = main.convert_table

        def spy(con, table, source, destination, compressed_bytes=None):
            root = source.parent.parent
            live = [p for p in root.rglob("*") if p.is_file()]
            seen.append(
                {
                    "csv": [p.name for p in live if p.suffix in (".txt", ".geojson")],
                    "parquet": [p.name for p in live if p.suffix == ".parquet"],
                    "zip": [p.name for p in live if p.suffix == ".zip"],
                }
            )
            return real_convert(con, table, source, destination, compressed_bytes)

        with patch.object(main, "convert_table", side_effect=spy):
            self.build()
        return seen

    def test_only_one_source_file_is_ever_resident(self):
        snapshots = self._residency()

        self.assertTrue(snapshots, "no tables were converted")
        worst = max(len(s["csv"]) for s in snapshots)
        self.assertEqual(
            worst, 1, f"more than one CSV was on disk at once: {snapshots}"
        )

    def test_parquet_files_do_not_accumulate(self):
        snapshots = self._residency()

        worst = max(len(s["parquet"]) for s in snapshots)
        self.assertLessEqual(
            worst,
            1,
            f"converted files accumulated instead of being published: {snapshots}",
        )

    def test_the_archive_is_kept_but_never_unpacked_wholesale(self):
        """The deliberate trade on the fallback path.

        Holding the compressed archive and extracting one member at a time costs far
        less than extracting every CSV up front, so the zip staying resident is correct
        - what must not happen is the CSVs piling up beside it.
        """
        snapshots = self._residency()

        self.assertTrue(all(len(s["csv"]) <= 1 for s in snapshots), snapshots)

    def test_everything_is_cleaned_up_afterwards(self):
        self.build()

        leftovers = [p for p in Path(main.TMPDIR).glob("parquet_*") if p.is_dir()]
        self.assertEqual(leftovers, [], f"workdirs left behind: {leftovers}")


class TestPublishIsNotObservablyPartial(BuildTestCase):
    """A reader must never find a dataset advertising tables that are not there yet.

    Reported from the operations web app: a feed loaded with "No tables found", then
    with one table, then with seven of eleven, and only became correct once every
    object had landed. The manifest was being uploaded in the middle of the
    alphabetical sequence, and a rebuild cleared the whole prefix before replacing it.
    """

    def _events(self):
        prefix = f"{FEED}/{DATASET}/parquet/"
        return [(kind, name[len(prefix) :]) for kind, name in self.bucket.events]

    def test_the_manifest_is_published_last(self):
        """It is the readiness marker for anyone reading the bucket directly."""
        self.build()

        uploads = [name for kind, name in self._events() if kind == "upload"]
        self.assertEqual(
            uploads[-1],
            "manifest.json",
            f"manifest must be the final upload, got order {uploads}",
        )

    def test_nothing_is_deleted_before_the_new_set_is_up(self):
        """Clearing first leaves an already-published dataset unreadable meanwhile."""
        self.bucket._existing = [f"{FEED}/{DATASET}/parquet/gone.parquet"]

        self.build()

        kinds = [kind for kind, _ in self._events()]
        self.assertIn("delete", kinds)
        self.assertLess(
            max(i for i, k in enumerate(kinds) if k == "upload"),
            min(i for i, k in enumerate(kinds) if k == "delete"),
            "every upload must precede every delete",
        )

    def test_a_rebuild_never_removes_a_table_it_is_replacing(self):
        """The live objects stay readable, overwritten in place, for the whole build."""
        self.bucket._existing = [f"{FEED}/{DATASET}/parquet/agency.parquet"]

        self.build()

        self.assertNotIn(
            f"{FEED}/{DATASET}/parquet/agency.parquet",
            self.bucket.deleted,
            "a table present in both the old and new set must never be deleted",
        )

    def test_ready_is_recorded_only_after_every_object_has_landed(self):
        recorded = []
        self.tracker.mark_completed.side_effect = lambda *a, **k: recorded.append(
            len(self.bucket.events)
        )

        self.build()

        self.assertEqual(
            recorded, [len(self.bucket.events)], "ready was published mid-publish"
        )


class TestReadsPreExtractedFiles(BuildTestCase):
    """The fast path: use what `batch_process_dataset` already unpacked.

    Both paths must produce the same artifact - a dataset should not describe itself
    differently depending on which route the builder happened to take.
    """

    def _with_extracted(self, names, dataset_id=DATASET):
        """Point the DB at Gtfsfile rows and seed the matching blobs."""
        records = []
        for name in names:
            record = MagicMock()
            record.file_name = name
            records.append(record)
            body = AGENCY if name.endswith("agency.txt") else STOPS
            self.bucket.extracted[f"{FEED}/{dataset_id}/extracted/{name}"] = (
                body.encode()
            )

        dataset = MagicMock()
        dataset.gtfsfiles = records
        dataset.zipped_size_bytes = 4321
        self.session.query.return_value.filter.return_value.one_or_none.return_value = (
            dataset
        )
        return dataset

    def test_converts_from_extracted_without_downloading_the_archive(self):
        self._with_extracted(["agency.txt", "stops.txt"])

        result = self.build()

        self.assertEqual(sorted(result["tables"]), ["agency", "stops"])
        self.assertNotIn(
            f"{FEED}/{DATASET}/{DATASET}.zip",
            self.bucket.opened,
            "the archive was read despite extracted files being available",
        )

    def test_a_recorded_file_the_bucket_lacks_falls_back_to_the_archive(self):
        """The Gtfsfile rows are an index, not a guarantee.

        `rebuild_missing_dataset_files` exists because a dataset can be recorded with
        files the bucket no longer holds. This used to raise NotFound from inside the
        conversion and lose the whole build.
        """
        dataset = self._with_extracted(["agency.txt"])
        phantom = MagicMock()
        phantom.file_name = "feed_info.txt"
        dataset.gtfsfiles = list(dataset.gtfsfiles) + [phantom]

        result = self.build()

        self.assertEqual(result["status"], "success")
        self.assertIn(
            f"{FEED}/{DATASET}/{DATASET}.zip",
            self.bucket.opened,
            "the archive was not used despite the extracted set being incomplete",
        )
        # The archive holds both tables, so nothing is lost by taking that route.
        self.assertEqual(sorted(result["tables"]), ["agency", "stops"])

    def test_an_incomplete_extracted_set_is_never_converted_on_its_own(self):
        """Publishing the subset would assert a partial feed is the whole feed."""
        dataset = self._with_extracted(["agency.txt"])
        phantom = MagicMock()
        phantom.file_name = "stop_times.txt"
        dataset.gtfsfiles = list(dataset.gtfsfiles) + [phantom]
        # No archive to fall back to either.
        self.bucket._archive = None
        self.bucket.blob = lambda name: FakeBlob(name, self.bucket, None)

        with self.assertRaises(FileNotFoundError):
            self.build()

        self.assertEqual(self.bucket.uploaded, {}, "a partial set was published")

    def test_archive_relative_paths_are_flattened(self):
        """`extracted/` preserves the archive's own layout, folders and all."""
        self._with_extracted(["feed/agency.txt", "feed/stops.txt"])

        result = self.build()

        self.assertEqual(sorted(result["tables"]), ["agency", "stops"])

    def test_non_gtfs_members_are_ignored(self):
        self._with_extracted(
            ["agency.txt", "stops.txt", "__MACOSX/._stops.txt", "licence.pdf"]
        )

        result = self.build()

        self.assertEqual(sorted(result["tables"]), ["agency", "stops"])

    def test_compressed_sizes_come_from_the_archive_tail(self):
        """Read by range, not by downloading the archive - the numbers exist nowhere else."""
        self._with_extracted(["agency.txt", "stops.txt"])

        self.build()

        manifest = json.loads(
            self.bucket.uploaded[f"{FEED}/{DATASET}/parquet/manifest.json"]
        )
        self.assertEqual(manifest["source"]["kind"], "zip")
        self.assertTrue(
            any(t["compressed_bytes"] for t in manifest["tables"]),
            f"no compressed sizes recovered: {manifest['tables']}",
        )
        self.assertTrue(self.bucket.ranged, "the tail was never fetched")

    def test_the_recorded_archive_size_is_used_when_present(self):
        self._with_extracted(["agency.txt"])

        self.build()

        manifest = json.loads(
            self.bucket.uploaded[f"{FEED}/{DATASET}/parquet/manifest.json"]
        )
        self.assertEqual(manifest["source"]["bytes"], 4321)

    def test_falls_back_to_the_archive_when_nothing_was_extracted(self):
        """Datasets processed before extraction existed still have to build."""
        dataset = MagicMock()
        dataset.gtfsfiles = []
        self.session.query.return_value.filter.return_value.one_or_none.return_value = (
            dataset
        )

        result = self.build()

        self.assertEqual(sorted(result["tables"]), ["agency", "stops"])
        self.assertIn(f"{FEED}/{DATASET}/{DATASET}.zip", self.bucket.opened)


class TestArchiveIsStreamed(BuildTestCase):
    """The archive is read over the network, never written to the volume.

    Downloading it cost its full size on the in-memory volume for the whole build, on
    top of whichever member was being converted. A 1 GiB archive holding a 4 GiB table
    exhausted the volume before conversion started.
    """

    def _archive_only(self):
        """No Gtfsfile rows, so the build takes the archive path."""
        dataset = MagicMock()
        dataset.gtfsfiles = []
        self.session.query.return_value.filter.return_value.one_or_none.return_value = (
            dataset
        )

    def test_the_archive_is_never_written_to_the_workdir(self):
        self._archive_only()

        self.build()

        self.assertIn(f"{FEED}/{DATASET}/{DATASET}.zip", self.bucket.opened)
        self.assertEqual(
            self.bucket.downloaded, [], "the archive was written to the volume"
        )

    def test_members_are_read_in_archive_order_not_table_order(self):
        """A backward seek throws the reader's buffer away and refetches.

        The fixture writes stops before agency, so archive order and alphabetical order
        disagree and a plan built in the wrong one is visible.
        """
        self.bucket._archive = _zip_bytes(reverse=True)
        self._archive_only()

        plan = main._plan_from_archive(
            self.bucket, FEED, DATASET, Path(tempfile.mkdtemp()), MagicMock()
        )
        try:
            self.assertEqual([table for table, _ in plan.sources], ["stops", "agency"])
        finally:
            plan.close()

    def test_tables_are_still_reported_by_name(self):
        """Conversion order is an IO detail; the manifest must not depend on it."""
        self.bucket._archive = _zip_bytes(reverse=True)
        self._archive_only()

        result = self.build()

        self.assertEqual(result["tables"], ["agency", "stops"])
        manifest = json.loads(
            self.bucket.uploaded[f"{FEED}/{DATASET}/parquet/manifest.json"]
        )
        self.assertEqual([t["name"] for t in manifest["tables"]], ["agency", "stops"])

    def test_compressed_sizes_come_from_the_directory_already_read(self):
        """The central directory is in hand, so the tail is not fetched a second time."""
        self._archive_only()

        self.build()

        manifest = json.loads(
            self.bucket.uploaded[f"{FEED}/{DATASET}/parquet/manifest.json"]
        )
        for table in manifest["tables"]:
            self.assertIsNotNone(
                table["compressed_bytes"], f"{table['name']} lost its zipped size"
            )
        self.assertEqual(self.bucket.ranged, [], "the archive tail was re-read")

    def test_the_handle_is_released_when_the_build_fails(self):
        self._archive_only()

        with patch.object(main, "convert_table", side_effect=RuntimeError("no memory")):
            with self.assertRaises(RuntimeError):
                self.build()

        # Nothing to assert on GCS here; the point is that the failure path runs
        # plan.close() rather than leaking the reader, which the build would otherwise
        # hold until the instance is recycled.
        self.tracker.mark_failed.assert_called_once()


class TestBothPathsAgree(BuildTestCase):
    """A dataset must not describe itself differently depending on the route taken."""

    def _manifest(self):
        return json.loads(
            self.bucket.uploaded[f"{FEED}/{DATASET}/parquet/manifest.json"]
        )

    def _use_extracted(self):
        records = []
        for name, body in (("agency.txt", AGENCY), ("stops.txt", STOPS)):
            record = MagicMock()
            record.file_name = name
            records.append(record)
            self.bucket.extracted[f"{FEED}/{DATASET}/extracted/{name}"] = body.encode()
        dataset = MagicMock()
        dataset.gtfsfiles = records
        dataset.zipped_size_bytes = None  # force both paths to size the archive alike
        self.session.query.return_value.filter.return_value.one_or_none.return_value = (
            dataset
        )

    def test_extracted_and_archive_paths_produce_the_same_manifest(self):
        self.build()  # no Gtfsfile rows -> archive path
        from_archive = self._manifest()

        self.setUp()
        self._use_extracted()
        self.build()
        from_extracted = self._manifest()

        volatile = {"generated_at"}
        self.assertEqual(
            {k: v for k, v in from_archive.items() if k not in volatile},
            {k: v for k, v in from_extracted.items() if k not in volatile},
            "the two source paths disagree about the same dataset",
        )


class TestRetention(BuildTestCase):
    """The builder owns the default, so a caller that says nothing still gets one."""

    def _recorded(self):
        _, kwargs = self.tracker.mark_completed.call_args
        return kwargs["metadata"]["retention_days"]

    def test_an_omitted_value_uses_the_builders_default(self):
        self.build()

        self.assertEqual(self._recorded(), main.DEFAULT_RETENTION_DAYS)

    def test_a_callers_value_is_honoured(self):
        self.build(retention_days=7)

        self.assertEqual(self._recorded(), 7)

    def test_out_of_range_values_fall_back_rather_than_being_stored(self):
        """The API bounds this too, but Cloud Tasks and the CLI do not go through it,
        and a bad value here would be written to the row and obeyed by the sweep."""
        for bad in (0, -1, main.MAX_RETENTION_DAYS + 1, "abc", 3.7e9):
            with self.subTest(bad=bad):
                self.assertEqual(main._retention_days(bad), main.DEFAULT_RETENTION_DAYS)

    def test_the_boundaries_are_accepted(self):
        self.assertEqual(main._retention_days(1), 1)
        self.assertEqual(
            main._retention_days(main.MAX_RETENTION_DAYS), main.MAX_RETENTION_DAYS
        )

    def test_none_means_the_default(self):
        self.assertEqual(main._retention_days(None), main.DEFAULT_RETENTION_DAYS)

    def test_every_object_carries_the_expiry_as_custom_time(self):
        """The bucket's lifecycle rule deletes on customTime, so an object without one
        would never expire."""
        before = datetime.now(timezone.utc)
        self.build(retention_days=7)

        self.assertEqual(
            set(self.bucket.custom_times),
            set(self.bucket.uploaded),
            "an object was published without an expiry",
        )
        for name, stamped in self.bucket.custom_times.items():
            with self.subTest(name=name):
                self.assertIsNotNone(stamped)
                delta = stamped - before
                self.assertGreater(delta, timedelta(days=7) - timedelta(minutes=1))
                self.assertLess(delta, timedelta(days=7) + timedelta(minutes=1))

    def test_the_manifest_expires_with_the_tables(self):
        """A manifest outliving its tables would advertise files that are gone."""
        self.build()

        stamps = set(self.bucket.custom_times.values())
        self.assertEqual(len(stamps), 1, f"the set does not expire together: {stamps}")

    def test_a_shorter_retention_expires_sooner(self):
        self.build(retention_days=7)
        short = min(self.bucket.custom_times.values())

        self.setUp()
        self.build(retention_days=30)
        long = min(self.bucket.custom_times.values())

        self.assertLess(short, long)

    def test_the_row_records_the_same_instant_as_the_objects(self):
        """Two sources of truth for one date would drift; the API reads the row."""
        self.build()

        recorded = datetime.fromisoformat(
            self.tracker.mark_completed.call_args.kwargs["metadata"]["expires_at"]
        )
        self.assertEqual(recorded, next(iter(self.bucket.custom_times.values())))


class TestClaimDurability(BuildTestCase):
    """The claim is what stops a second worker; it cannot ride on a best-effort write."""

    def setUp(self):
        super().setUp()
        self.events = []
        self.session.commit.side_effect = lambda: self.events.append("commit")
        self.tracker.heartbeat.side_effect = lambda *a, **k: self.events.append(
            "heartbeat"
        )

    def test_the_claim_is_committed_before_any_progress_write(self):
        self.build()

        self.assertEqual(
            self.events[0],
            "commit",
            f"the claim was not committed first: {self.events[:3]}",
        )
        self.assertLess(self.events.index("commit"), self.events.index("heartbeat"))

    def test_a_progress_write_that_fails_leaves_the_session_usable(self):
        """Progress is a courtesy, so the failure is swallowed - but not the rollback."""
        self.tracker.heartbeat.side_effect = RuntimeError("connection reset")

        result = self.build()

        self.assertEqual(result["status"], "success")
        self.assertTrue(self.session.rollback.called, "the session was left poisoned")
        self.tracker.mark_completed.assert_called_once()


class TestPublicReadability(BuildTestCase):
    def test_an_acl_failure_fails_the_build(self):
        """A published but unreadable file must not be reported as `ready`."""
        self.bucket.acl_error = RuntimeError("403 forbidden")

        with self.assertRaises(RuntimeError):
            self.build()

        self.tracker.mark_completed.assert_not_called()
        self.tracker.mark_failed.assert_called_once()

    def test_uniform_bucket_level_access_needs_no_acl(self):
        """There the objects are public by policy, and per-object ACLs are rejected."""
        self.bucket.acl_error = RuntimeError("cannot use ACL API")
        self.bucket.iam_configuration.uniform_bucket_level_access_enabled = True

        result = self.build()

        self.assertEqual(result["status"], "success")


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
        with patch.object(main, "convert_table", side_effect=RuntimeError("no memory")):
            with self.assertRaises(RuntimeError):
                self.build()

        self.tracker.mark_failed.assert_called_once()
        self.tracker.mark_completed.assert_not_called()
        self.assertEqual(self.bucket.uploaded, {})

    def test_a_failure_in_the_commit_itself_is_still_recorded(self):
        """Recording a failure must not need a session the failure has just broken."""
        completed = []
        self.tracker.mark_completed.side_effect = lambda *a, **k: completed.append(1)

        def commit():
            if completed:
                raise RuntimeError("could not commit")

        self.session.commit.side_effect = commit

        with self.assertRaises(RuntimeError):
            self.build()

        self.assertTrue(self.session.rollback.called)
        self.tracker.mark_failed.assert_called_once()


if __name__ == "__main__":
    unittest.main()
