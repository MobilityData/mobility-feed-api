# GTFS Change Tracker

This function computes a structured diff between two consecutive GTFS datasets and stores the resulting changelog in GCS and the database.

The function reads pre-extracted GTFS files from a GCS-mounted bucket (uploaded by `batch_process_dataset`), runs the diff engine, uploads the changelog JSON to GCS, and upserts a row in `gtfs_dataset_changelog`.

## Usage

The function receives the following request:
```
{
  "feed_stable_id": str,                  – stable_id of the GTFS feed
  "base_dataset_stable_id": str,          – stable_id of the base (older) dataset
  "new_dataset_stable_id": str,           – stable_id of the new (recent) dataset
  "disallow_overwrite": bool (optional),  – skip if changelog already exists (default: false)
  "dry_run": bool (optional)              – compute diff but skip GCS upload and DB write (default: false)
}
```

Example:
```json
{
  "feed_stable_id": "mdb-2142",
  "base_dataset_stable_id": "mdb-2142-202502251658",
  "new_dataset_stable_id": "mdb-2142-202507081652"
}
```

Example curl call:
```bash
curl -X POST https://<function-url> \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{
    "feed_stable_id": "mdb-2142",
    "base_dataset_stable_id": "mdb-2142-202502251658",
    "new_dataset_stable_id": "mdb-2142-202507081652"
  }'
```

### `disallow_overwrite`
By default the function will overwrite an existing changelog for the same dataset pair. Set `disallow_overwrite: true` to skip execution if a changelog already exists in GCS.

### `dry_run`
When `dry_run: true`, the diff is computed and a summary is returned in the response, but nothing is written to GCS or the database. Useful for validating that the extracted files are present and the diff engine runs correctly.

## Response

Success:
```json
{
  "status": "success",
  "message": "Changelog generated successfully.",
  "changelog_url": "https://storage.googleapis.com/<bucket>/<feed>/<dataset>/..."
}
```

Dry run:
```json
{
  "status": "success",
  "message": "Dry run completed. Diff computed but not persisted.",
  "summary": {
    "total_changes": 42,
    "files_added_count": 0,
    "files_deleted_count": 0,
    "files_modified_count": 3,
    ...
  }
}
```

The function always returns HTTP 200, including on errors. Errors are reported in the response body under `"status": "error"`. This prevents GCP from retrying failures where re-running with the same parameters would produce the same result.

## GCP environment variables

- `DATASETS_BUCKET_NAME`: The GCS bucket where datasets are stored (required). Must include the environment suffix, e.g. `mobilitydata-datasets-dev`.
- `DATASETS_BUCKET_MOUNT`: Mount path for the GCS bucket (default: `/mobilitydata-datasets`).
- `GTFS_DIFF_DUCKDB_TMPDIR`: Mount path for the in-memory tmpfs used by the diff engine (default: `/tmp/in-memory`). Used by `limit_gcp_memory` to compute the available process memory and set `RLIMIT_AS`, preventing silent OOM kills.
- `MEMORY_MARGIN_MB`: Safety margin in MiB subtracted from the memory limit before setting `RLIMIT_AS` (default: `200`).
- `LOGGING_LEVEL`: Log level (default: `INFO`).
