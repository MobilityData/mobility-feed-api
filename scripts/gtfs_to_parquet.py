#!/usr/bin/env python3
"""
gtfs_to_parquet.py

Converts a GTFS ZIP file into Parquet files suitable for efficient browser-side
pagination and search via DuckDB-WASM + HTTP Range requests (same principle as PMTiles).

Each GTFS CSV is sorted by its primary key column(s) and written with row-group
statistics so that DuckDB can skip irrelevant row groups when paginating or filtering.

Usage:
    # From a MobilityDatabase feed ID (looks up latest dataset automatically):
    python3 scripts/gtfs_to_parquet.py --feed-id mdb-2014 [--env dev|qa|prod] [--upload]

    # From a direct URL:
    python3 scripts/gtfs_to_parquet.py --url <GTFS_URL> [--upload] [--env dev|qa|prod]

    # From a local file:
    python3 scripts/gtfs_to_parquet.py --file <LOCAL_ZIP>

Options:
    --feed-id ID        MobilityDatabase feed ID (e.g. mdb-2014). Resolves the
                        latest dataset from GCS and uploads result alongside it.
    --url URL           Direct URL of the GTFS ZIP to download
    --file FILE         Path to a local GTFS ZIP file
    --env ENV           Target environment: dev, qa, or prod (default: dev).
                        Used with --feed-id or --upload.
    --upload            After conversion, upload Parquet files to GCS alongside
                        the source dataset (requires gcloud/gsutil auth).
    --dataset-id ID     Specific dataset stable ID to use (optional, overrides
                        latest resolution when used with --feed-id).
    --output DIR        Local output directory (default: ./gtfs_parquet_output)
    --row-group-size N  Rows per Parquet row group (default: 50000)
    --no-sort           Skip sorting (faster ingestion, slower queries)

GCS layout:
    gs://mobilitydata-datasets-{env}/{feed_id}/{dataset_id}/gtfs_parquet/
        metadata.json
        stops.parquet
        routes.parquet
        trips.parquet
        stop_times.parquet
        ...
"""

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import duckdb
    import requests
except ImportError as e:
    print(f"[ERROR] Missing dependency: {e}")
    print("       Run: pip install duckdb requests")
    sys.exit(1)


# Maps GTFS filename → columns to sort by (order matters for row-group skipping)
GTFS_FILE_CONFIGS: dict[str, list[str]] = {
    "agency.txt": ["agency_id"],
    "stops.txt": ["stop_id"],
    "routes.txt": ["route_id"],
    "trips.txt": ["route_id", "trip_id"],
    "stop_times.txt": ["trip_id", "stop_sequence"],
    "calendar.txt": ["service_id"],
    "calendar_dates.txt": ["service_id", "date"],
    "shapes.txt": ["shape_id", "shape_pt_sequence"],
    "fare_attributes.txt": ["fare_id"],
    "fare_rules.txt": ["route_id"],
    "frequencies.txt": ["trip_id", "start_time"],
    "transfers.txt": ["from_stop_id", "to_stop_id"],
    "pathways.txt": ["pathway_id"],
    "levels.txt": ["level_id"],
    "attributions.txt": ["organization_name"],
    "feed_info.txt": [],
}

# Maps GTFS filename → columns that are semantically searchable (IDs, names, codes).
# Numeric columns (times, sequences, coordinates) are excluded — they are not useful
# for text search and prevent DuckDB from skipping row groups.
GTFS_SEARCH_COLUMNS: dict[str, list[str]] = {
    "agency.txt": ["agency_id", "agency_name"],
    "stops.txt": ["stop_id", "stop_name", "stop_code", "zone_id", "parent_station"],
    "routes.txt": ["route_id", "route_short_name", "route_long_name", "agency_id"],
    "trips.txt": ["trip_id", "route_id", "service_id", "trip_headsign", "shape_id"],
    "stop_times.txt": ["trip_id", "stop_id", "stop_headsign"],
    "calendar.txt": ["service_id"],
    "calendar_dates.txt": ["service_id"],
    "shapes.txt": ["shape_id"],
    "fare_attributes.txt": ["fare_id", "agency_id"],
    "fare_rules.txt": ["fare_id", "route_id", "origin_id", "destination_id", "contains_id"],
    "frequencies.txt": ["trip_id"],
    "transfers.txt": ["from_stop_id", "to_stop_id"],
    "pathways.txt": ["pathway_id", "from_stop_id", "to_stop_id"],
    "levels.txt": ["level_id"],
    "attributions.txt": ["organization_name"],
    "feed_info.txt": ["feed_publisher_name"],
}

BUCKET_TEMPLATE = "mobilitydata-datasets-{env}"
DEFAULT_ROW_GROUP_SIZE = 50_000
DOWNLOAD_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB


# ─── Argument parsing ────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a GTFS ZIP to Parquet files for efficient browser viewing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--feed-id", metavar="ID",
                        help="MobilityDatabase feed ID (e.g. mdb-2014)")
    source.add_argument("--url", metavar="URL",
                        help="Direct URL of the GTFS ZIP to download")
    source.add_argument("--file", metavar="FILE",
                        help="Path to a local GTFS ZIP file")

    parser.add_argument("--env", choices=["dev", "qa", "prod"], default="dev",
                        help="Target GCS environment (default: dev). Used with --feed-id or --upload.")
    parser.add_argument("--upload", action="store_true",
                        help="Upload generated Parquet files to GCS after conversion.")
    parser.add_argument("--dataset-id", metavar="ID",
                        help="Specific dataset stable ID (optional override with --feed-id).")
    parser.add_argument("--output", metavar="DIR", default="./gtfs_parquet_output",
                        help="Local output directory (default: ./gtfs_parquet_output)")
    parser.add_argument("--row-group-size", type=int, default=DEFAULT_ROW_GROUP_SIZE,
                        metavar="N", help=f"Rows per row group (default: {DEFAULT_ROW_GROUP_SIZE})")
    parser.add_argument("--memory-limit", type=int, default=4, metavar="GB",
                        help="DuckDB memory limit in GB for sorting large files (default: 4)")
    parser.add_argument("--no-sort", action="store_true",
                        help="Skip sorting (faster ingestion, slower queries)")
    return parser.parse_args()


# ─── GCS helpers ─────────────────────────────────────────────────────────────

def gsutil(*args: str, capture: bool = True) -> str:
    """Run a gsutil command. Raises on non-zero exit."""
    cmd = ["gsutil"] + list(args)
    result = subprocess.run(cmd, capture_output=capture, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"gsutil {' '.join(args)} failed:\n{result.stderr.strip()}"
        )
    return result.stdout.strip() if capture else ""


def resolve_latest_dataset_id(feed_id: str, env: str) -> str:
    """
    Returns the latest dataset_stable_id for a feed by listing the GCS bucket.
    Used to determine the upload target path — download always uses latest.zip.
    """
    bucket = BUCKET_TEMPLATE.format(env=env)
    prefix = f"gs://{bucket}/{feed_id}/"

    print(f"[INFO] Resolving latest dataset ID for {feed_id} in {bucket}…")
    try:
        listing = gsutil("ls", prefix)
    except RuntimeError as e:
        err = str(e)
        if "matched no objects" in err or "BucketNotFoundException" in err:
            raise RuntimeError(
                f"Feed '{feed_id}' has no datasets in {bucket}.\n"
                f"Use --dataset-id to specify the target dataset ID explicitly,\n"
                f"or check the feed exists in the '{env}' environment."
            )
        raise RuntimeError(
            f"Cannot list GCS bucket. Ensure you are authenticated:\n  gcloud auth login\n{e}"
        )

    # Versioned dataset folders look like: gs://.../mdb-2014-202507081807/
    folders = sorted([
        line.rstrip("/")
        for line in listing.splitlines()
        if line.endswith("/") and f"/{feed_id}-" in line
    ])

    if not folders:
        raise RuntimeError(
            f"No dataset folders found for {feed_id} in {prefix}.\n"
            f"Use --dataset-id to specify one explicitly."
        )

    latest_folder = folders[-1]  # alphabetical = chronological (YYYYMMDDHHII suffix)
    dataset_id = latest_folder.split("/")[-1]
    print(f"[INFO] Latest dataset: {dataset_id}  ({len(folders)} datasets found)")
    return dataset_id


def latest_zip_url(feed_id: str) -> str:
    """Public URL for the latest dataset ZIP of a feed (all environments share prod files)."""
    return f"https://files.mobilitydatabase.org/{feed_id}/latest.zip"


def upload_to_gcs(local_dir: Path, feed_id: str, dataset_id: str, env: str) -> None:
    """Upload all Parquet + metadata.json from local_dir to GCS and make them public.
    Uses gsutil (gcloud auth login credentials) for upload and per-object ACLs.
    """
    bucket_name = BUCKET_TEMPLATE.format(env=env)
    gcs_prefix = f"{feed_id}/{dataset_id}/gtfs_parquet"

    print(f"\n[UPLOAD] Uploading to gs://{bucket_name}/{gcs_prefix}/")
    files = sorted(
        list(local_dir.glob("*.parquet")) + [local_dir / "metadata.json"]
    )
    files = [f for f in files if f.exists()]

    for local_file in files:
        gcs_path = f"gs://{bucket_name}/{gcs_prefix}/{local_file.name}"
        gsutil("cp", str(local_file), gcs_path, capture=False)
        # Per-object public-read ACL (works with legacy ACL buckets like dev/qa)
        try:
            gsutil("acl", "ch", "-u", "AllUsers:R", gcs_path, capture=True)
        except Exception:
            pass  # Uniform IAM bucket — public access is set at bucket level
        size_mb = local_file.stat().st_size / 1e6
        print(f"  ✓ {local_file.name}  ({size_mb:.2f} MB)")

    public_base = f"https://storage.googleapis.com/{bucket_name}/{gcs_prefix}"
    print(f"\n[UPLOAD] ✓ {len(files)} files uploaded")
    print(f"\n[UPLOAD] Public metadata URL (paste in GTFS Viewer):")
    print(f"         {public_base}/metadata.json")


# ─── Download helpers ─────────────────────────────────────────────────────────

def download_from_url(url: str) -> bytes:
    print(f"[INFO] Downloading from URL: {url}")
    response = requests.get(url, stream=True, timeout=120)
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))
    chunks = []
    downloaded = 0
    for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
        chunks.append(chunk)
        downloaded += len(chunk)
        if total:
            print(f"  {downloaded / 1e6:.1f} / {total / 1e6:.1f} MB ({downloaded/total*100:.0f}%)", end="\r")
    print()
    return b"".join(chunks)


# ─── CSV → Parquet conversion ─────────────────────────────────────────────────

def csv_to_parquet(
    csv_bytes: bytes,
    output_path: Path,
    sort_columns: list[str],
    search_columns: list[str],
    row_group_size: int,
    skip_sort: bool,
    memory_limit_gb: int = 4,
) -> dict:
    """
    Convert CSV bytes to a Parquet file using DuckDB.

    DuckDB handles out-of-core sorting (spills to disk when data exceeds memory_limit_gb)
    so this works on arbitrarily large files without OOM — unlike pyarrow which requires
    the entire dataset + its sorted copy to fit in RAM simultaneously.
    """
    spill_dir = output_path.parent / ".duckdb_tmp"
    spill_dir.mkdir(exist_ok=True)

    # Write CSV bytes to a temp file — DuckDB needs a file path
    tmp_csv = Path(tempfile.mktemp(suffix=".csv", dir=output_path.parent))
    tmp_csv.write_bytes(csv_bytes)

    try:
        con = duckdb.connect(config={
            "memory_limit": f"{memory_limit_gb}GB",
            "temp_directory": str(spill_dir),
        })

        # Detect schema — use LIMIT 0 to avoid loading data, no pandas needed
        def get_columns(encoding_opt: str = "") -> list[str]:
            enc = f", encoding='latin-1'" if encoding_opt else ""
            res = con.execute(
                f"SELECT * FROM read_csv('{tmp_csv}', auto_detect=true, "
                f"ignore_errors=true, null_padding=true{enc}) LIMIT 0"
            )
            return [desc[0] for desc in res.description]

        try:
            column_names = get_columns()
        except Exception:
            column_names = get_columns("latin-1")
        valid_sorts = (
            [c for c in sort_columns if c in column_names]
            if not skip_sort else []
        )
        order_clause = f"ORDER BY {', '.join(valid_sorts)}" if valid_sorts else ""

        # Try UTF-8 first; fall back to latin-1 for feeds with non-ASCII characters
        for encoding_opt in ("", ", encoding='latin-1'"):
            try:
                con.execute(f"""
                    COPY (
                        SELECT * FROM read_csv('{tmp_csv}',
                            auto_detect=true,
                            ignore_errors=true,
                            null_padding=true
                            {encoding_opt}
                        )
                        {order_clause}
                    ) TO '{output_path}' (
                        FORMAT PARQUET,
                        ROW_GROUP_SIZE {row_group_size},
                        COMPRESSION 'snappy'
                    )
                """)
                break
            except Exception as e:
                if encoding_opt:
                    raise
                last_err = e

        row_count = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{output_path}')"
        ).fetchone()[0]
        con.close()

        return {
            "row_count": row_count,
            "size_bytes": output_path.stat().st_size,
            "columns": column_names,
            "sort_columns": valid_sorts,
            "search_columns": [c for c in search_columns if c in column_names],
        }

    finally:
        if tmp_csv.exists():
            tmp_csv.unlink()
        if spill_dir.exists():
            shutil.rmtree(spill_dir, ignore_errors=True)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    feed_id: str | None = None
    dataset_id: str | None = getattr(args, "dataset_id", None)

    # ── Acquire GTFS ZIP bytes
    if args.feed_id:
        feed_id = args.feed_id
        url = latest_zip_url(feed_id)
        zip_bytes = download_from_url(url)
        source_label = url

        # Resolve dataset_id for the upload path (only when upload is needed)
        if args.upload and not dataset_id:
            dataset_id = resolve_latest_dataset_id(feed_id, args.env)

    elif args.url:
        zip_bytes = download_from_url(args.url)
        source_label = args.url
        # Try to derive feed_id/dataset_id from files.mobilitydatabase.org URL
        # e.g. https://files.mobilitydatabase.org/mdb-2014/mdb-2014-20250708/mdb-2014-20250708.zip
        parts = args.url.rstrip("/").split("/")
        if len(parts) >= 3 and parts[-3].startswith("mdb-"):
            feed_id = parts[-3]
            dataset_id = parts[-2] if parts[-2].startswith(feed_id) else None

    else:
        local_path = Path(args.file)
        if not local_path.exists():
            print(f"[ERROR] File not found: {local_path}")
            sys.exit(1)
        print(f"[INFO] Reading local file: {local_path}")
        zip_bytes = local_path.read_bytes()
        source_label = str(local_path.resolve())

    print(f"[INFO] ZIP size: {len(zip_bytes) / 1e6:.1f} MB")

    # ── Open ZIP
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as e:
        print(f"[ERROR] Not a valid ZIP file: {e}")
        sys.exit(1)

    zip_names = {Path(n).name: n for n in zf.namelist()}
    print(f"[INFO] Found {len(zip_names)} files: {', '.join(sorted(zip_names.keys()))}")

    tables_meta: dict[str, dict] = {}
    processed = 0
    skipped = []

    for gtfs_filename, sort_cols in GTFS_FILE_CONFIGS.items():
        if gtfs_filename not in zip_names:
            skipped.append(gtfs_filename)
            continue

        parquet_name = gtfs_filename.replace(".txt", ".parquet")
        output_path = output_dir / parquet_name
        print(f"\n[INFO] Processing {gtfs_filename} → {parquet_name}")
        csv_bytes = zf.read(zip_names[gtfs_filename])
        print(f"       CSV size: {len(csv_bytes) / 1e6:.2f} MB")

        try:
            search_cols = GTFS_SEARCH_COLUMNS.get(gtfs_filename, [])
            meta = csv_to_parquet(csv_bytes, output_path, sort_cols, search_cols,
                                   args.row_group_size, args.no_sort, args.memory_limit)
            tables_meta[gtfs_filename.replace(".txt", "")] = {"file": parquet_name, **meta}
            ratio = meta["size_bytes"] / max(len(csv_bytes), 1) * 100
            print(f"       ✓ {meta['row_count']:,} rows | "
                  f"{meta['size_bytes'] / 1e6:.2f} MB ({ratio:.0f}% of CSV)")
            processed += 1
        except Exception as e:
            print(f"       ✗ Failed: {e}")

    # Convert any extra .txt files not in GTFS_FILE_CONFIGS
    for name, zip_path in zip_names.items():
        if not name.endswith(".txt"):
            continue
        table_key = name.replace(".txt", "")
        if table_key in tables_meta:
            continue
        parquet_name = name.replace(".txt", ".parquet")
        print(f"\n[INFO] Processing extra file {name} → {parquet_name}")
        try:
            csv_bytes = zf.read(zip_path)
            meta = csv_to_parquet(csv_bytes, output_dir / parquet_name, [], [],
                                   args.row_group_size, args.no_sort, args.memory_limit)
            tables_meta[table_key] = {"file": parquet_name, **meta}
            print(f"       ✓ {meta['row_count']:,} rows")
            processed += 1
        except Exception as e:
            print(f"       ✗ Failed: {e}")

    # ── Write metadata.json
    metadata = {
        "source": source_label,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "feed_id": feed_id,
        "dataset_id": dataset_id,
        "env": args.env if args.feed_id or args.upload else None,
        "row_group_size": args.row_group_size,
        "tables": tables_meta,
    }
    metadata_path = output_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2))

    print(f"\n{'='*60}")
    print(f"[DONE] Converted {processed} tables → {output_dir}/")
    if skipped:
        print(f"       Skipped (not in ZIP): {', '.join(skipped)}")

    # ── Upload to GCS if requested
    if args.upload:
        if not feed_id or not dataset_id:
            print("\n[WARN] --upload requires a resolvable feed_id and dataset_id.")
            print("       Use --feed-id, or a files.mobilitydatabase.org URL.")
        else:
            upload_to_gcs(output_dir, feed_id, dataset_id, args.env)
    else:
        print(f"\nTo serve locally for the POC viewer:")
        print(f"  python3 scripts/gtfs_parquet_serve.py --dir {output_dir}")
        print(f"\nTo upload to GCS (dev by default):")
        print(f"  Re-run with --upload [--env dev|qa|prod]")
        if feed_id and dataset_id:
            print(f"\n  Or add --upload to this command and set --env {args.env}")


if __name__ == "__main__":
    main()

