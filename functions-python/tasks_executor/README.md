# Tasks Executor

This directory contains Google Cloud Functions used as a single point of access to multiple _tasks_.

## Usage

The function receive the following payload:

```
{
   "task": "string", # [required] Name of the task to execute
   "payload": { } [optional] Payload to pass to the task
}
```

Examples:

```json
{
  "task": "rebuild_missing_validation_reports",
  "payload": {
    "dry_run": true,
    "bypass_db_update": true,
    "filter_after_in_days": null,
    "force_update": false,
    "validator_endpoint": "https://stg-gtfs-validator-web-mbzoxaljzq-ue.a.run.app",
    "limit": 1,    
    "filter_statuses": ["active", "inactive", "future"]
  }
}
```

```json
{
  "task": "get_validation_run_status",
  "payload": {
    "task_name": "gtfs_validation",
    "run_id": "7.1.1-SNAPSHOT"
  }
}
```

```json
{
  "task": "rebuild_missing_bounding_boxes",
  "payload": {
    "dry_run": true,
    "after_date": "2025-06-01"
  }
}
```

```json
{
  "task": "refresh_materialized_view",
  "payload": {
    "dry_run": true
  }
}
```

To get the list of supported tasks use:

```json
{
  "name": "list_tasks",
  "payload": {}
}
```

To update the geolocation files precision:

```json
{
  "task": "update_geojson_files_precision",
  "payload": {
    "dry_run": true,
    "data_type": "gtfs",
    "precision": 5,
    "limit": 10
  }
}
```

To populate licenses:

```json
{
  "task": "populate_licenses",
  "payload": {
    "dry_run": true
  }
}
```

To backfill MD5 hashes for existing GTFS datasets (reads the MD5 from the GCS object metadata):

```json
{
  "task": "backfill_dataset_hash_md5",
  "payload": {
    "dry_run": true,
    "only_latest": true,
    "only_missing_hashes": true,
    "limit": 10
  }
}
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `dry_run` | bool | `true` | Log changes without writing to the database |
| `only_latest` | bool | `true` | Process only datasets that are the current latest for their feed |
| `only_missing_hashes` | bool | `true` | Skip datasets that already have `hash_md5` set |
| `limit` | int \| null | `10` | Maximum number of datasets to process; omit or pass `null` for no limit |

To check the availability of active/published GTFS feeds via HTTP HEAD requests:

```json
{
  "task": "check_gtfs_feed_availability",
  "payload": {
    "dry_run": true,
    "skip_db_update": false,
    "limit": null,
    "concurrency": 10,
    "timeout_seconds": 20,
    "batch_size": 50,
    "feed_ids": null
  }
}
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `dry_run` | bool | `true` | Count matching feeds only — no HTTP calls or DB writes |
| `skip_db_update` | bool | `false` | Run HTTP checks but skip writing results to the DB. Each check is logged individually for monitoring and debugging |
| `limit` | int \| null | `null` | Maximum number of feeds to process; omit or pass `null` for no limit |
| `concurrency` | int | `10` | Number of parallel HTTP workers |
| `timeout_seconds` | int | `20` | Per-request HTTP timeout in seconds |
| `batch_size` | int | `50` | Number of completed results committed to DB at a time |
| `feed_ids` | list[str] \| null | `null` | If provided, only check these specific feed IDs |

The response includes an `elapsed_seconds` field indicating how long the task took to complete.

## Response Content Type

When the request includes the header `Accept: text/csv`, the server returns the response as a CSV file generated from the handler’s output.
If the header is not provided, the default response content type is `application/json`.