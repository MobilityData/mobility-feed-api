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
"""The local generator: which archive an id means, and the server's range handling.

The range tests are the point of the file. The reader queries Parquet by asking for
byte ranges, and a server that quietly answers with the whole file looks like it works
until a query returns nothing useful - so the suffix range that reads a footer is
asserted explicitly.
"""

import json
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from functools import partial
from http.server import HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scripts.generate_local import (
    ENV_HOSTS,
    RangeRequestHandler,
    archive_url,
    build_parser,
    generate,
)

pytest.importorskip("duckdb")

AGENCY = "agency_id,agency_name,agency_url,agency_timezone\n1,T,https://e.org,UTC\n"
STOPS = "stop_id,stop_name\nS1,First\n"


class TestArchiveUrl(unittest.TestCase):
    def test_a_dataset_id_addresses_that_exact_archive(self):
        self.assertEqual(
            archive_url("mdb-1210-202402121801", ENV_HOSTS["prod"]),
            "https://files.mobilitydatabase.org/mdb-1210/mdb-1210-202402121801/mdb-1210-202402121801.zip",
        )

    def test_a_feed_id_addresses_whatever_is_current(self):
        self.assertEqual(
            archive_url("mdb-1210", ENV_HOSTS["prod"]),
            "https://files.mobilitydatabase.org/mdb-1210/latest.zip",
        )

    def test_the_environment_selects_the_host(self):
        self.assertTrue(
            archive_url("mdb-1", ENV_HOSTS["dev"]).startswith(
                "https://dev-files.mobilitydatabase.org/"
            )
        )

    def test_a_feed_id_containing_digits_is_not_mistaken_for_a_dataset(self):
        """`mdb-1210` ends in digits too; only a timestamp-length run means a dataset."""
        self.assertTrue(
            archive_url("mdb-1210", ENV_HOSTS["prod"]).endswith("/latest.zip")
        )


class TestGenerate(unittest.TestCase):
    def _feed_zip(self, path: Path, nested: bool = False) -> Path:
        prefix = "feed/" if nested else ""
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr(f"{prefix}agency.txt", AGENCY)
            zf.writestr(f"{prefix}stops.txt", STOPS)
        return path

    def test_converts_a_local_archive(self):
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            archive = self._feed_zip(tmp / "feed.zip")
            out = tmp / "out"

            tables = generate(str(archive), out, ENV_HOSTS["prod"], keep=False)

            self.assertEqual([t.name for t in tables], ["agency", "stops"])
            self.assertTrue((out / "manifest.json").exists())

    def test_converts_a_directory(self):
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            data = tmp / "extracted"
            data.mkdir()
            (data / "agency.txt").write_text(AGENCY)
            out = tmp / "out"

            tables = generate(str(data), out, ENV_HOSTS["prod"], keep=False)

            self.assertEqual([t.name for t in tables], ["agency"])

    def test_a_nested_archive_is_flattened(self):
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            archive = self._feed_zip(tmp / "feed.zip", nested=True)

            tables = generate(str(archive), tmp / "out", ENV_HOSTS["prod"], keep=False)

            self.assertEqual([t.name for t in tables], ["agency", "stops"])

    def test_regenerating_clears_a_table_the_feed_no_longer_has(self):
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            out = tmp / "out"
            out.mkdir()
            (out / "gone.parquet").write_text("stale")

            generate(
                str(self._feed_zip(tmp / "feed.zip")),
                out,
                ENV_HOSTS["prod"],
                keep=False,
            )

            self.assertFalse((out / "gone.parquet").exists())

    def test_keep_leaves_an_existing_directory_alone(self):
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            out = tmp / "out"
            out.mkdir()
            (out / "keep.parquet").write_text("mine")

            generate(
                str(self._feed_zip(tmp / "feed.zip")), out, ENV_HOSTS["prod"], keep=True
            )

            self.assertTrue((out / "keep.parquet").exists())

    def test_a_missing_path_is_reported_not_treated_as_an_id(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as caught:
                generate(
                    "./no/such/feed.zip",
                    Path(tmp) / "out",
                    ENV_HOSTS["prod"],
                    keep=False,
                )
            self.assertIn("No such file", str(caught.exception))


class TestMainExit(unittest.TestCase):
    def test_an_unconvertible_source_exits_1_without_a_traceback(self):
        """A wrong folder is a normal typo, not a crash."""
        from scripts.generate_local import main

        with TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty"
            empty.mkdir()
            self.assertEqual(main([str(empty), "--out", str(Path(tmp) / "out")]), 1)


class TestRangeServer(unittest.TestCase):
    """What `python -m http.server` would get wrong."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = TemporaryDirectory()
        cls.root = Path(cls._tmp.name)
        cls.payload = bytes(range(256)) * 4  # 1024 bytes, every value distinct by index
        (cls.root / "data.parquet").write_bytes(cls.payload)
        (cls.root / "manifest.json").write_text(
            json.dumps({"version": 1, "tables": []})
        )

        handler = partial(RangeRequestHandler, directory=str(cls.root))
        cls.server = HTTPServer(("localhost", 0), handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls._tmp.cleanup()

    def _get(self, path, headers=None):
        request = urllib.request.Request(
            f"http://localhost:{self.port}/{path}", headers=headers or {}
        )
        return urllib.request.urlopen(request)

    def test_serves_a_whole_file_without_a_range(self):
        response = self._get("data.parquet")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.read(), self.payload)

    def test_advertises_range_support_and_allows_cross_origin_reads(self):
        response = self._get("manifest.json")
        self.assertEqual(response.headers["Accept-Ranges"], "bytes")
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")
        self.assertIn(
            "content-range", response.headers["Access-Control-Expose-Headers"]
        )

    def test_answers_a_byte_range_with_exactly_those_bytes(self):
        response = self._get("data.parquet", {"Range": "bytes=10-19"})
        self.assertEqual(response.status, 206)
        self.assertEqual(response.headers["Content-Range"], "bytes 10-19/1024")
        self.assertEqual(response.read(), self.payload[10:20])

    def test_an_open_ended_range_runs_to_the_end(self):
        response = self._get("data.parquet", {"Range": "bytes=1000-"})
        self.assertEqual(response.status, 206)
        self.assertEqual(response.read(), self.payload[1000:])

    def test_a_suffix_range_reads_the_tail(self):
        """How a Parquet footer is fetched; getting it wrong breaks every query."""
        response = self._get("data.parquet", {"Range": "bytes=-8"})
        self.assertEqual(response.status, 206)
        self.assertEqual(response.headers["Content-Range"], "bytes 1016-1023/1024")
        self.assertEqual(response.read(), self.payload[-8:])

    def test_a_range_past_the_end_is_clamped(self):
        response = self._get("data.parquet", {"Range": "bytes=1020-9999"})
        self.assertEqual(response.status, 206)
        self.assertEqual(response.read(), self.payload[1020:])

    def test_an_unsatisfiable_range_is_refused(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self._get("data.parquet", {"Range": "bytes=5000-6000"})
        self.assertEqual(caught.exception.code, 416)


class TestParser(unittest.TestCase):
    def test_serve_defaults_to_a_port_without_one_given(self):
        self.assertEqual(build_parser().parse_args(["mdb-1", "--serve"]).serve, 8090)

    def test_serve_is_off_unless_asked_for(self):
        self.assertIsNone(build_parser().parse_args(["mdb-1"]).serve)

    def test_serve_accepts_an_explicit_port(self):
        self.assertEqual(
            build_parser().parse_args(["mdb-1", "--serve", "9000"]).serve, 9000
        )


if __name__ == "__main__":
    unittest.main()
