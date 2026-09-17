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
importing it: the package is not on PyPI, and it declares FastAPI and uvicorn as hard
dependencies, which is a web server this function would carry and never start. What is
actually being reproduced is small - a view per file and a COPY per table - and it is
pinned here by tests that assert the properties the viewer depends on.

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

import json
import logging
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

PARQUET_CONVERTER_VERSION = "1"

# The one GTFS file that is not a CSV, and the table it becomes.
LOCATIONS_GEOJSON = "locations.geojson"
LOCATIONS_TABLE = "locations"

# Written beside the Parquet so a reader holding only the URL can discover the tables.
# Not on the path the Operations API serves - a caller that got its table list from the
# API never fetches this - but it is what stops anyone else probing all 32 GTFS names.
MANIFEST = "manifest.json"
MANIFEST_VERSION = 1

# phase, done, total, detail
ProgressFn = Callable[[str, int, int, str], None]

PHASE_CONVERT = "convert"
PHASE_EXTRACT = "extract"


@dataclass
class ConvertedTable:
    name: str
    file: str
    rows: int
    bytes: int

    def as_manifest_entry(self) -> dict:
        return {
            "name": self.name,
            "file": self.file,
            "rows": self.rows,
            "bytes": self.bytes,
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


def _register_csv_tables(con, data_dir: Path, logger: logging.Logger) -> list[str]:
    """One view per .txt, named after the file stem, every column text.

    A file DuckDB cannot parse is skipped rather than fatal: most GTFS files are
    optional, and one unreadable extra must not cost the whole feed.
    """
    tables: list[str] = []
    for txt_file in sorted(data_dir.glob("*.txt")):
        table = txt_file.stem
        if not _has_header(txt_file):
            logger.warning("Skipping %s: no header row", txt_file.name)
            continue
        try:
            con.execute(f"""
                CREATE VIEW "{table}" AS
                SELECT * FROM read_csv(
                    '{_quote(txt_file)}',
                    ALL_VARCHAR = TRUE,
                    IGNORE_ERRORS = TRUE,
                    NULLSTR = ''
                )
                """)
        except Exception as error:
            logger.warning("Skipping unreadable file %s: %s", txt_file.name, error)
            continue
        tables.append(table)
    return tables


def _register_locations(con, data_dir: Path, logger: logging.Logger) -> Optional[str]:
    """Flatten locations.geojson to one row per Feature, all columns text.

    `features` is read as opaque JSON rather than letting DuckDB infer its shape, so a
    feed mixing Polygon and MultiPolygon cannot change the columns this produces.
    """
    source = data_dir / LOCATIONS_GEOJSON
    if not source.exists():
        return None

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
        return None

    return LOCATIONS_TABLE


def convert_to_parquet(
    data_dir: Path,
    destination: Path,
    on_progress: Optional[ProgressFn] = None,
    logger: Optional[logging.Logger] = None,
) -> list[ConvertedTable]:
    """Convert every GTFS table under `data_dir` into `destination`.

    Returns what was written, in table-name order, and writes `manifest.json` beside
    the files describing the same thing.
    """
    import duckdb

    logger = logger or logging.getLogger(__name__)
    destination.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(database=":memory:")
    try:
        tables = _register_csv_tables(con, data_dir, logger)
        locations = _register_locations(con, data_dir, logger)
        if locations:
            tables.append(locations)
        tables.sort()

        if not tables:
            raise ValueError(f"No readable GTFS files found in {data_dir}")

        converted: list[ConvertedTable] = []
        for index, table in enumerate(tables, start=1):
            if on_progress:
                on_progress(PHASE_CONVERT, index, len(tables), table)
            target = destination / f"{table}.parquet"
            con.execute(
                f"""COPY (SELECT * FROM "{table}") TO '{_quote(target)}' """
                f"""(FORMAT PARQUET, COMPRESSION ZSTD)"""
            )
            # Counted off the file rather than the CSV view: Parquet carries its row
            # count in the footer, so this reads a few bytes instead of reparsing the
            # table that was just written.
            rows = con.execute(
                f"SELECT count(*) FROM read_parquet('{_quote(target)}')"
            ).fetchone()[0]
            converted.append(
                ConvertedTable(
                    name=table,
                    file=target.name,
                    rows=int(rows),
                    bytes=target.stat().st_size,
                )
            )

        _write_manifest(destination, converted)
        return converted
    finally:
        con.close()


def _write_manifest(destination: Path, tables: list[ConvertedTable]) -> Path:
    manifest = destination / MANIFEST
    manifest.write_text(
        json.dumps(
            {
                "version": MANIFEST_VERSION,
                "converter_version": PARQUET_CONVERTER_VERSION,
                "tables": [table.as_manifest_entry() for table in tables],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest
