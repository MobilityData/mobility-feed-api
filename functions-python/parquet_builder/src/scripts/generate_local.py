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
"""Produce a dataset's Parquet locally, with no GCP involved.

The cloud function needs a bucket, a database, a Cloud Tasks queue and credentials.
None of that is interesting when the thing being worked on is the viewer, so this does
the same conversion against a feed on disk or a public URL and leaves the result
somewhere a browser can read it.

The conversion itself is imported, not reimplemented - `converter.convert_to_parquet`,
exactly what the function calls - so what comes out here is what would come out of a
real build. If the two ever disagree, that is a bug in one of them, not a difference
between local and deployed.

`--serve` exists because the obvious way to serve the output does not work: the reader
queries Parquet over HTTP range requests, and `python -m http.server` ignores Range and
returns whole files. The server here answers ranges and sends the CORS headers a
cross-origin worker needs.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import os
import re
import shutil
import socketserver
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from converter import MANIFEST, convert_to_parquet, extract_feed

# Datasets are public over HTTPS, which is what lets this avoid credentials entirely.
DEFAULT_HOST = "https://files.mobilitydatabase.org"
ENV_HOSTS = {
    "prod": "https://files.mobilitydatabase.org",
    "qa": "https://qa-files.mobilitydatabase.org",
    "dev": "https://dev-files.mobilitydatabase.org",
}

# A dataset id is its feed id with a timestamp appended: mdb-1210-202402121801.
DATASET_ID = re.compile(r"^(?P<feed>.+)-(?P<stamp>\d{8,})$")


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _progress(phase: str, done: int, total: int, detail: str) -> None:
    total_text = f"/{total}" if total else ""
    _log(f"  {phase:9} {done}{total_text} {detail}")


def archive_url(stable_id: str, host: str) -> str:
    """Where a feed or dataset id's archive lives.

    A dataset id addresses one specific archive; a feed id addresses whatever is
    current, which is the more useful thing to type.
    """
    match = DATASET_ID.match(stable_id)
    if match:
        feed = match.group("feed")
        return f"{host}/{feed}/{stable_id}/{stable_id}.zip"
    return f"{host}/{stable_id}/latest.zip"


def download(url: str, target: Path) -> Path:
    _log(f"  download  {url}")
    try:
        with urllib.request.urlopen(url) as response, open(target, "wb") as out:
            shutil.copyfileobj(response, out)
    except urllib.error.HTTPError as error:
        raise SystemExit(
            f"Could not download {url}: {error.code} {error.reason}\n"
            "Check the id, or pass --env dev/qa if the feed is not in production."
        )
    except urllib.error.URLError as error:
        raise SystemExit(f"Could not reach {url}: {error.reason}")
    return target


def resolve_source(source: str, workdir: Path, host: str) -> Path:
    """Get the feed onto disk as a directory of GTFS files, however it was named."""
    candidate = Path(source).expanduser()

    if candidate.is_dir():
        _log(f"  source    {candidate} (directory)")
        return candidate

    if candidate.is_file():
        _log(f"  source    {candidate} (archive)")
        return extract_feed(candidate, workdir / "extracted", on_progress=_progress)

    if candidate.suffix == ".zip" or "/" in source or "\\" in source:
        # Looks like a path the user expected to exist, rather than an id.
        raise SystemExit(f"No such file or directory: {source}")

    archive = download(archive_url(source, host), workdir / f"{source}.zip")
    return extract_feed(archive, workdir / "extracted", on_progress=_progress)


def generate(source: str, out_dir: Path, host: str, keep: bool) -> list:
    out_dir = out_dir.expanduser().resolve()
    if out_dir.exists() and not keep:
        # Cleared so a regeneration cannot leave a table behind that the feed no longer
        # has - the same reason the cloud function clears its prefix before uploading.
        shutil.rmtree(out_dir)

    with tempfile.TemporaryDirectory(prefix="parquet-local-") as tmp:
        workdir = Path(tmp)
        data_dir = resolve_source(source, workdir, host)
        tables = convert_to_parquet(data_dir, out_dir, on_progress=_progress)

    total = sum(t.bytes for t in tables)
    _log("")
    _log(
        f"Wrote {len(tables)} tables and a manifest to {out_dir} ({total / 1e6:.1f} MB)"
    )
    for table in tables:
        _log(f"  {table.name:24} {table.rows:>9,} rows  {table.bytes / 1e3:>8.1f} kB")
    return tables


class RangeRequestHandler(http.server.SimpleHTTPRequestHandler):
    """A static handler that answers Range requests and allows cross-origin reads.

    Both are required by the reader and neither is provided by the stdlib handler: it
    ignores Range entirely, so a query that asks for a few kilobytes of a footer is
    answered with the whole file, and a worker on another origin is refused outright.
    """

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "range")
        self.send_header(
            "Access-Control-Expose-Headers",
            "content-range, content-length, accept-ranges, etag",
        )
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self):  # noqa: N802 - name fixed by the base class
        self.send_response(204)
        self.end_headers()

    def do_GET(self):  # noqa: N802 - name fixed by the base class
        requested = self.headers.get("Range")
        if not requested:
            return super().do_GET()

        match = re.match(r"bytes=(\d*)-(\d*)", requested.strip())
        if not match:
            return super().do_GET()

        path = self.translate_path(self.path)
        try:
            size = os.path.getsize(path)
        except OSError:
            return self.send_error(404, "File not found")

        start_text, end_text = match.groups()
        if start_text:
            start = int(start_text)
            end = int(end_text) if end_text else size - 1
        else:
            # A suffix range - "the last N bytes" - which is how a Parquet footer is
            # read, so getting this wrong breaks every query.
            length = int(end_text or 0)
            start, end = max(0, size - length), size - 1
        end = min(end, size - 1)

        if start > end or start >= size:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return

        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        with open(path, "rb") as handle:
            handle.seek(start)
            self.wfile.write(handle.read(end - start + 1))

    def log_message(self, fmt, *args):
        _log("  " + fmt % args)


def serve(directory: Path, port: int) -> None:
    handler = functools.partial(RangeRequestHandler, directory=str(directory))

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    with Server(("", port), handler) as httpd:
        _log("")
        _log(f"Serving {directory} at http://localhost:{port} (ranges and CORS on)")
        _log(f"  manifest: http://localhost:{port}/{MANIFEST}")
        _log("  Ctrl-C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            _log("stopped")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="parquet-generate-local.sh",
        description="Convert a GTFS feed to Parquet locally, with no GCP access.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  # A feed id: downloads its current archive over HTTPS
  parquet-generate-local.sh mdb-1210

  # A specific dataset
  parquet-generate-local.sh mdb-1210-202402121801

  # A feed already on disk, as a zip or an unpacked folder
  parquet-generate-local.sh ./gtfs.zip
  parquet-generate-local.sh ./extracted/

  # Straight into the operations web app, which serves public/datasets/<id>
  parquet-generate-local.sh mdb-1210 --out ../ops-web/public/datasets/mdb-1210

  # Or serve it directly, with the range support the reader needs
  parquet-generate-local.sh mdb-1210 --serve
""",
    )
    parser.add_argument(
        "source", help="a feed or dataset stable id, a .zip path, or a directory"
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="where to write (default: .dist/parquet/<source>)",
    )
    parser.add_argument(
        "--env",
        choices=sorted(ENV_HOSTS),
        default="prod",
        help="which environment to download a stable id from (default: prod)",
    )
    parser.add_argument(
        "--serve",
        nargs="?",
        type=int,
        const=8090,
        metavar="PORT",
        help="serve the result on PORT (default 8090) with ranges and CORS",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="add to an existing output directory instead of clearing it first",
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    name = Path(args.source).name.removesuffix(".zip") or "feed"
    out_dir = args.out or Path(".dist/parquet") / name

    try:
        tables = generate(
            source=args.source,
            out_dir=out_dir,
            host=ENV_HOSTS[args.env],
            keep=args.keep,
        )
    except ValueError as error:
        # A feed that cannot be converted is a normal thing to type by mistake - a
        # wrong folder, an archive that is not GTFS - so it gets a sentence rather
        # than a traceback.
        _log(f"error: {error}")
        return 1
    if not tables:
        return 1

    if args.serve is not None:
        serve(out_dir.expanduser().resolve(), args.serve)
    return 0


if __name__ == "__main__":
    sys.exit(main())
