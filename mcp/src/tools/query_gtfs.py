import json
import logging
import os
import time
from typing import Optional

import duckdb

from gtfs_cache import get_gtfs_cache
from shared.database.database import Database
from shared.database_gen.sqlacodegen_models import Gtfsfeed

logger = logging.getLogger(__name__)

STANDARD_GTFS_FILES = [
    "agency.txt",
    "stops.txt",
    "routes.txt",
    "trips.txt",
    "stop_times.txt",
    "calendar.txt",
    "calendar_dates.txt",
    "shapes.txt",
    "fare_attributes.txt",
    "fare_rules.txt",
    "frequencies.txt",
    "transfers.txt",
    "feed_info.txt",
    "pathways.txt",
    "levels.txt",
    "translations.txt",
    "attributions.txt",
]
ROW_LIMIT = 1000


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _table_name_for_file(filename: str) -> str:
    return filename[:-4] if filename.endswith(".txt") else filename


def _file_name_for_table(table_name: str) -> str:
    return f"{table_name}.txt"


STANDARD_TABLE_NAMES = frozenset(_table_name_for_file(f) for f in STANDARD_GTFS_FILES)


def _load_duckdb(feed_id: str, dataset_id: str, datasets_bucket_url: str, files: list[str]) -> duckdb.DuckDBPyConnection:
    """Load GTFS files directly from GCS into an in-memory DuckDB via httpfs."""
    con = duckdb.connect()
    con.load_extension("httpfs")

    base_url = f"{datasets_bucket_url}/{feed_id}/{dataset_id}/extracted"
    for filename in files:
        table_name = _table_name_for_file(filename)
        url = f"{base_url}/{filename}"
        try:
            con.execute(
                f"CREATE TABLE {_quote_identifier(table_name)} AS "
                f"SELECT * FROM read_csv_auto('{url}', all_varchar=true)"
            )
        except Exception as exc:
            logger.warning("Failed to load %s: %s", filename, exc)

    return con


def _resolve_dataset(feed_id: str) -> tuple[str | None, str | None]:
    """Return (dataset_stable_id, error_json) for a given feed_id."""
    db = Database()
    with db.start_db_session() as session:
        feed = session.query(Gtfsfeed).filter(Gtfsfeed.stable_id == feed_id).first()
        if feed is None:
            return None, json.dumps({"error": f"Feed '{feed_id}' not found."})

        dataset = feed.latest_dataset
        if dataset is None:
            return None, json.dumps({"error": f"Feed '{feed_id}' has no dataset yet."})

        return dataset.stable_id, None


def _get_schema(con: duckdb.DuckDBPyConnection) -> tuple[dict, list[str]]:
    tables = {}
    table_names = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
    for table_name in sorted(table_names):
        columns = [row[1] for row in con.execute(f"PRAGMA table_info({_quote_identifier(table_name)})").fetchall()]
        row_count = con.execute(f"SELECT COUNT(*) FROM {_quote_identifier(table_name)}").fetchone()[0]
        tables[table_name] = {"columns": columns, "row_count": row_count}
    available_files = [f"{table_name}.txt" for table_name in sorted(table_names)]
    return tables, available_files


def _extract_tables_from_query(query: str) -> list[str]:
    """Extract referenced GTFS table names from a SQL query."""
    if not query:
        return []
    upper = query.upper()
    found = []
    for table_name in STANDARD_TABLE_NAMES:
        if table_name.upper() in upper:
            found.append(table_name)
    return found


def _validate_files(
    files: Optional[list[str]], query: Optional[str] = None
) -> tuple[list[str], Optional[str]]:
    """Validate and normalize the files list.

    Returns (filenames, error).  When *error* is not None the caller should
    return it directly — *filenames* will be empty.
    """
    user_provided = bool(files)
    if not files and query and query.strip().upper() != "SCHEMA":
        files = _extract_tables_from_query(query)

    if not files:
        return list(STANDARD_GTFS_FILES), None

    normalized = []
    invalid = []
    for f in files:
        name = f.strip()
        if not name:
            continue
        table_name = _table_name_for_file(name) if name.endswith(".txt") else name
        if table_name not in STANDARD_TABLE_NAMES:
            invalid.append(name)
            continue
        normalized.append(_file_name_for_table(table_name))

    if invalid and user_provided:
        valid_list = ", ".join(sorted(STANDARD_TABLE_NAMES))
        return [], json.dumps({
            "error": f"Invalid GTFS file(s): {', '.join(invalid)}. "
                     f"Valid files are: {valid_list}",
        })

    return (normalized if normalized else list(STANDARD_GTFS_FILES)), None


def query_gtfs_tool(feed_id: str, query: str, files: Optional[list[str]] = None) -> str:
    """
    Load a GTFS feed into an in-memory DuckDB database and execute SQL queries.

    Use query="SCHEMA" first to discover available tables and columns.
    Then write SQL SELECT queries to answer questions about routes, stops, schedules, etc.

    Results are cached per feed/file-set for FEED_CACHE_TTL_SECONDS (default: 10 minutes).

    Args:
        feed_id: Mobility Database feed ID (e.g. "mdb-1210")
        query: Either "SCHEMA" to list tables/columns, or a SQL SELECT statement
        files: Optional list of GTFS files to load (e.g. ["stops", "routes", "trips"]).
               Accepts table names or filenames (e.g. "stops" or "stops.txt").
               If omitted, all standard GTFS files are loaded.
               Tip: only load the tables you need for much faster responses.

    Returns:
        JSON string with schema info or query results
    """
    datasets_bucket_url = os.getenv("DATASETS_BUCKET_URL", "")
    if not datasets_bucket_url:
        return json.dumps({"error": "DATASETS_BUCKET_URL is not configured."})

    dataset_id, error = _resolve_dataset(feed_id)
    if error:
        return error
    logging.info("Querying GTFS feed %s dataset %s with files %s", feed_id, dataset_id, files)
    target_files, validation_error = _validate_files(files, query)
    if validation_error:
        return validation_error
    # Cache key includes sorted file set so different subsets are cached independently
    cache_key_suffix = ",".join(sorted(target_files))
    cache = get_gtfs_cache()
    started_at = time.perf_counter()

    try:
        con = cache.get_or_load(
            feed_id,
            f"{dataset_id}:{cache_key_suffix}",
            lambda: _load_duckdb(feed_id, dataset_id, datasets_bucket_url, target_files),
        )
    except Exception as exc:
        logger.exception("Failed to load GTFS feed %s dataset %s", feed_id, dataset_id)
        return json.dumps(
            {
                "feed_id": feed_id,
                "dataset_id": dataset_id,
                "error": f"Failed to load GTFS feed: {exc}",
            },
            default=str,
        )

    if (query or "").strip().upper() == "SCHEMA":
        cursor = con.cursor()
        try:
            tables, available_files = _get_schema(cursor)
        finally:
            cursor.close()
        return json.dumps(
            {
                "feed_id": feed_id,
                "dataset_id": dataset_id,
                "tables": tables,
                "available_files": available_files,
            },
            default=str,
        )

    normalized_query = (query or "").strip().rstrip(";")
    if not normalized_query.upper().startswith("SELECT"):
        return json.dumps(
            {
                "feed_id": feed_id,
                "dataset_id": dataset_id,
                "error": "Only SQL SELECT queries are allowed. Use SCHEMA to inspect tables.",
            }
        )

    limited_sql = f"SELECT * FROM ({normalized_query}) AS _query_gtfs LIMIT {ROW_LIMIT}"
    cursor = con.cursor()
    try:
        result = cursor.execute(limited_sql)
        rows = [list(row) for row in result.fetchall()]
        columns = [column[0] for column in (result.description or [])]
    except Exception as exc:
        return json.dumps(
            {
                "feed_id": feed_id,
                "dataset_id": dataset_id,
                "sql": limited_sql,
                "error": f"Query failed: {exc}",
            },
            default=str,
        )
    finally:
        cursor.close()

    execution_time_ms = int((time.perf_counter() - started_at) * 1000)
    return json.dumps(
        {
            "feed_id": feed_id,
            "dataset_id": dataset_id,
            "sql": limited_sql,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "execution_time_ms": execution_time_ms,
        },
        default=str,
    )
