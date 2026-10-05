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
"""Rewrite an extracted GTFS feed as one Parquet file per table.

This mirrors what `gtfs-garage --export` produces, deliberately rather than by
importing it. Two reasons, the second being the one that would survive the first:

  * The distribution carries a web server. `gtfs-garage` is on PyPI, but it declares
    FastAPI, uvicorn and python-multipart as unconditional dependencies, so a function
    that never starts a server would ship one. Its `tests/test_layering.py` keeps
    `gtfs_garage.core` framework-free and names this repository as the consumer, so
    this is a packaging gap rather than a design one - it would take a `server` extra
    over there to close it.
  * The shapes differ. `Feed.export_parquet` registers the whole feed into one DuckDB
    database and then exports every table; `main._convert_and_publish` fetches,
    converts, uploads and deletes one table at a time, so peak memory tracks the
    largest single table rather than the feed, which is what fits a large one inside
    the function's tmpfs. Importing would not supply that loop, only the SQL in it.

What is actually being reproduced is small - a view per file and a COPY per table -
and it is pinned here by tests that assert the properties the viewer depends on.

Two of those properties are load-bearing and neither is obvious:

  * Every column is text. The reader compares with ILIKE and with `= ''`, so a typed
    column silently breaks filtering rather than failing loudly. `ALL_VARCHAR` on the
    way in is what guarantees it on the way out.
  * An empty CSV field becomes NULL, not an empty string, because the reader rewrites
    `= ''` into `IS NULL OR = ''` on that basis.

Bump PARQUET_CONVERTER_VERSION when the output changes in a way that makes previously
written files wrong. It is the run id of the tracking rows, so a bump invalidates every
dataset's artifacts instead of serving files a newer reader no longer matches.
"""

from __future__ import annotations

import io
import json
import logging
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

PARQUET_CONVERTER_VERSION = "2"

# The one GTFS file that is not a CSV, and the table it becomes.
LOCATIONS_GEOJSON = "locations.geojson"
LOCATIONS_TABLE = "locations"

# Written beside the Parquet: the dataset's description of itself. The reader takes
# its table list from here, and its load report - how big each file was before
# conversion and after it - which is why the sizes below are worth carrying.
MANIFEST = "manifest.json"
MANIFEST_VERSION = 2

# phase, done, total, detail
ProgressFn = Callable[[str, int, int, str], None]

PHASE_CONVERT = "convert"
PHASE_EXTRACT = "extract"


@dataclass
class SourceFacts:
    """Where the feed came from, for the manifest header.

    Defaults describe a directory of GTFS files, which is what a caller that simply
    points at an extracted feed has. A zip source fills all three in.
    """

    kind: str = "folder"
    bytes: Optional[int] = None
    # Keyed by file name. Empty for a folder: a member's compressed size exists only
    # in a zip's central directory and is unrecoverable once extracted.
    compressed_sizes: dict = field(default_factory=dict)


@dataclass
class ConvertedTable:
    name: str
    file: str
    rows: int
    columns: int
    # What the source file weighed, and what it weighed inside the archive it arrived
    # in. Neither survives the conversion - the CSVs are deleted and the archive is
    # gone - so they are recorded here or lost.
    bytes: Optional[int]
    compressed_bytes: Optional[int]
    parquet_bytes: int

    def as_manifest_entry(self) -> dict:
        return {
            "name": self.name,
            "file": self.file,
            "rows": self.rows,
            "columns": self.columns,
            "bytes": self.bytes,
            "compressed_bytes": self.compressed_bytes,
            "parquet_bytes": self.parquet_bytes,
        }


def extract_feed(
    archive: Path,
    destination: Path,
    on_progress: Optional[ProgressFn] = None,
) -> Path:
    """Unpack a GTFS archive into `destination`, flattening any wrapping directory.

    Producers differ on whether the files sit at the root of the zip or inside a
    folder, and the conversion looks for *.txt in one place. Flattening here rather
    than searching there keeps that difference from spreading.

    Shared with the local generation script deliberately, so a feed prepared on a
    laptop is unpacked exactly as one prepared in the cloud function.
    """
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        members = [m for m in zf.infolist() if not m.is_dir()]
        for index, member in enumerate(members, start=1):
            name = Path(member.filename).name
            if not name:
                continue
            if on_progress:
                on_progress(PHASE_EXTRACT, index, len(members), name)
            with zf.open(member) as source, open(destination / name, "wb") as target:
                target.write(source.read())
    return destination


def zip_member_sizes_from_file(fileobj) -> dict[str, int]:
    """Each member's compressed size, keyed by file name, from a seekable archive.

    Only the central directory is read, so a file-like that serves just the tail of a
    remote archive is enough - see `TailReader`. The number exists nowhere else: once
    the files are extracted, what they weighed inside the zip is gone, and the load
    report has a column for it.
    """
    try:
        with zipfile.ZipFile(fileobj) as zf:
            return {
                Path(info.filename).name: info.compress_size
                for info in zf.infolist()
                if not info.is_dir()
            }
    except (OSError, zipfile.BadZipFile):
        return {}


def zip_member_sizes(archive: Path) -> dict[str, int]:
    """`zip_member_sizes_from_file` for an archive on disk."""
    try:
        with open(archive, "rb") as handle:
            return zip_member_sizes_from_file(handle)
    except OSError:
        return {}


class TailReader(io.RawIOBase):
    """A read-only file over the last `len(tail)` bytes of a larger file.

    Lets `zipfile` read a remote archive's central directory without fetching the
    archive. The directory lives at the end, but its records carry offsets into the
    *whole* file, so a plain buffer of the tail would have every offset wrong. This
    reports the full size and maps absolute positions onto the tail, which is all
    `zipfile` needs to enumerate members - it only seeks earlier when asked to read an
    entry's data, which we never do.
    """

    def __init__(self, tail: bytes, size: int):
        self._tail = tail
        self._size = size
        self._start = size - len(tail)
        self._pos = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            self._pos = offset
        elif whence == io.SEEK_CUR:
            self._pos += offset
        else:
            self._pos = self._size + offset
        return self._pos

    def read(self, size: int = -1) -> bytes:
        if self._pos < self._start:
            # Only reachable if the directory did not fit in the tail; the caller
            # retries with more rather than getting silently truncated records.
            raise ValueError("read before the start of the fetched tail")
        start = self._pos - self._start
        end = len(self._tail) if size is None or size < 0 else start + size
        chunk = self._tail[start:end]
        self._pos += len(chunk)
        return chunk

    def readall(self) -> bytes:
        return self.read(-1)


def _quote(path: Path) -> str:
    """Escape a path for embedding in a DuckDB string literal."""
    return str(path).replace("'", "''")


def _has_header(path: Path) -> bool:
    """True when the file opens with something that could be a header row.

    Worth checking up front because an empty file is not an error to DuckDB: it
    invents a single `column0`, returns no rows, and would be published as a table
    that is not one. A header with no data rows is an entirely different thing and is
    kept - an empty frequencies.txt is a legitimate part of a feed.

    Only the first line is read, so this stays cheap on a multi-gigabyte stop_times.
    """
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            return bool(handle.readline().strip())
    except OSError:
        return False


def open_connection(
    temp_dir: Optional[Path] = None, memory_limit: Optional[str] = None
):
    """A DuckDB connection told where to spill and how much it may hold.

    Both settings matter in a container. DuckDB's default memory heuristic reads the
    host's RAM rather than the cgroup, so left alone it spills far too late and the
    process dies before it ever tries; and its default spill target is the working
    directory. Naming both turns an overshoot into slower work instead of a lost run.
    """
    import duckdb

    con = duckdb.connect(database=":memory:")
    if temp_dir is not None:
        temp_dir.mkdir(parents=True, exist_ok=True)
        con.execute(f"SET temp_directory='{_quote(temp_dir)}'")
    if memory_limit:
        con.execute(f"SET memory_limit='{memory_limit}'")
    return con


def table_name_for(source: Path) -> Optional[str]:
    """The table a source file becomes, or None if it is not one.

    Producers ship all sorts of things in a feed - PDFs, `__MACOSX` entries, licences -
    and everything in the archive is kept, so the filter lives here.
    """
    # AppleDouble resource forks (`__MACOSX/._stops.txt`) flatten to a name that looks
    # exactly like a table once the folder is stripped, and every archive member is
    # published to `extracted/`, so this is routine rather than hypothetical. No GTFS
    # file begins with a dot.
    if source.name.startswith("."):
        return None
    if source.name == LOCATIONS_GEOJSON:
        return LOCATIONS_TABLE
    if source.suffix == ".txt":
        return source.stem
    return None


def register_table(con, table: str, source: Path, logger: logging.Logger) -> bool:
    """Create the view for one source file. False when the file cannot be used.

    A file DuckDB cannot parse is skipped rather than fatal: most GTFS files are
    optional, and one unreadable extra must not cost the whole feed.
    """
    if table == LOCATIONS_TABLE:
        return _register_locations(con, source, logger)

    if not _has_header(source):
        logger.warning("Skipping %s: no header row", source.name)
        return False
    try:
        con.execute(f"""
            CREATE VIEW "{table}" AS
            SELECT * FROM read_csv(
                '{_quote(source)}',
                ALL_VARCHAR = TRUE,
                IGNORE_ERRORS = TRUE,
                NULLSTR = ''
            )
            """)
    except Exception as error:
        logger.warning("Skipping unreadable file %s: %s", source.name, error)
        return False
    return True


def _register_locations(con, source: Path, logger: logging.Logger) -> bool:
    """Flatten locations.geojson to one row per Feature, all columns text.

    `features` is read as opaque JSON rather than letting DuckDB infer its shape, so a
    feed mixing Polygon and MultiPolygon cannot change the columns this produces.
    """
    try:
        con.execute(f"""
            CREATE VIEW "{LOCATIONS_TABLE}" AS
            SELECT
                CAST(json_extract_string(feature, '$.id') AS VARCHAR) AS id,
                CAST(json_extract_string(feature, '$.properties.stop_name') AS VARCHAR)
                    AS stop_name,
                CAST(json_extract_string(feature, '$.properties.stop_desc') AS VARCHAR)
                    AS stop_desc,
                CAST(json_extract_string(feature, '$.geometry.type') AS VARCHAR)
                    AS geometry_type,
                CAST(json_extract(feature, '$.geometry') AS VARCHAR) AS geometry
            FROM (
                SELECT unnest(features) AS feature
                FROM read_json(
                    '{_quote(source)}',
                    columns = {{type: 'VARCHAR', features: 'JSON[]'}}
                )
            )
            """)
        # A view is lazy, so one over malformed JSON is created happily and only fails
        # later, mid-conversion. Reading a row forces the parse while it can still be
        # handled as "this feed has no zones" rather than as a failed build.
        con.execute(f'SELECT * FROM "{LOCATIONS_TABLE}" LIMIT 1').fetchall()
    except Exception as error:
        logger.warning("Ignoring unusable %s: %s", LOCATIONS_GEOJSON, error)
        con.execute(f'DROP VIEW IF EXISTS "{LOCATIONS_TABLE}"')
        return False
    return True


def convert_table(
    con,
    table: str,
    source: Path,
    destination: Path,
    compressed_bytes: Optional[int] = None,
) -> ConvertedTable:
    """Write one registered table as Parquet and describe what was written.

    Drops the view afterwards so the source file can be deleted immediately - holding
    it open would pin a file the caller is about to remove to reclaim memory.
    """
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / f"{table}.parquet"
    con.execute(
        f"""COPY (SELECT * FROM "{table}") TO '{_quote(target)}' """
        f"""(FORMAT PARQUET, COMPRESSION ZSTD)"""
    )
    # Counted off the file rather than the source view: Parquet carries its row count
    # in the footer, so this reads a few bytes instead of reparsing what was just
    # written.
    rows = con.execute(
        f"SELECT count(*) FROM read_parquet('{_quote(target)}')"
    ).fetchone()[0]
    columns = con.execute(f'DESCRIBE "{table}"').fetchall()
    size = _size_of(source)
    con.execute(f'DROP VIEW IF EXISTS "{table}"')
    return ConvertedTable(
        name=table,
        file=target.name,
        rows=int(rows),
        columns=len(columns),
        bytes=size,
        compressed_bytes=compressed_bytes,
        parquet_bytes=target.stat().st_size,
    )


def convert_to_parquet(
    data_dir: Path,
    destination: Path,
    on_progress: Optional[ProgressFn] = None,
    logger: Optional[logging.Logger] = None,
    source: Optional[SourceFacts] = None,
    on_table: Optional[Callable[[ConvertedTable, Path], None]] = None,
    delete_sources: bool = False,
) -> list[ConvertedTable]:
    """Convert every GTFS table under `data_dir` into `destination`.

    Tables are converted one at a time and the view is dropped after each, so at most
    one source is ever open. `on_table` is called with each finished file, which lets a
    caller publish and delete it before the next begins; `delete_sources` removes each
    input once converted. Both default off, because a caller pointed at a directory it
    does not own must not have its files deleted.

    `source` carries facts about where the feed came from that cannot be recovered from
    `data_dir` - the archive's own size, and each member's compressed size.
    """
    logger = logger or logging.getLogger(__name__)
    destination.mkdir(parents=True, exist_ok=True)

    candidates = {}
    for path in sorted(data_dir.iterdir()):
        table = table_name_for(path)
        if table is not None:
            candidates[table] = path
    if not candidates:
        raise ValueError(f"No readable GTFS files found in {data_dir}")

    source = source or SourceFacts(bytes=_folder_bytes(candidates.values()))
    con = open_connection()
    try:
        return _convert_each(
            con,
            candidates,
            destination,
            source,
            on_progress,
            on_table,
            delete_sources,
            logger,
        )
    finally:
        con.close()


def _convert_each(
    con,
    candidates: dict,
    destination: Path,
    source: SourceFacts,
    on_progress,
    on_table,
    delete_sources: bool,
    logger: logging.Logger,
) -> list[ConvertedTable]:
    converted: list[ConvertedTable] = []
    tables = sorted(candidates)
    for index, table in enumerate(tables, start=1):
        origin = candidates[table]
        if on_progress:
            on_progress(PHASE_CONVERT, index, len(tables), table)
        if not register_table(con, table, origin, logger):
            continue
        entry = convert_table(
            con, table, origin, destination, source.compressed_sizes.get(origin.name)
        )
        converted.append(entry)
        if on_table:
            on_table(entry, destination / entry.file)
        if delete_sources:
            origin.unlink(missing_ok=True)

    if not converted:
        raise ValueError("No GTFS tables could be converted")

    write_manifest(destination, converted, source)
    return converted


def _size_of(path: Path) -> Optional[int]:
    try:
        return path.stat().st_size
    except OSError:
        return None


def _folder_bytes(sources) -> int:
    return sum(_size_of(path) or 0 for path in sources)


def write_manifest(
    destination: Path, tables: list[ConvertedTable], source: SourceFacts
) -> Path:
    """Describe the dataset for a reader that will never see what it came from.

    Version 2 added the sizes the load report shows. It is not a superset of version 1:
    there, `bytes` meant the Parquet size, where here it means the source's and the
    converted size is `parquet_bytes`. A reader has to know which it is holding, which
    is what the version is for - do not add fields under the old number.
    """
    sized = [table for table in tables if table.bytes is not None]
    manifest = destination / MANIFEST
    manifest.write_text(
        json.dumps(
            {
                "version": MANIFEST_VERSION,
                "generated_at": datetime.now(timezone.utc).isoformat(
                    timespec="seconds"
                ),
                # Our own converter, not gtfs-garage's version: this writes the same
                # artifact but is not that package, and claiming its version would be
                # a lie a reader might act on.
                "converter_version": PARQUET_CONVERTER_VERSION,
                "source": {"kind": source.kind, "bytes": source.bytes},
                "totals": {
                    "uncompressed_bytes": sum(table.bytes for table in sized),
                    "stored_bytes": sum(table.parquet_bytes for table in tables),
                },
                "tables": [table.as_manifest_entry() for table in tables],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest
