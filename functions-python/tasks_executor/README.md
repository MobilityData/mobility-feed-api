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
    "filter_after_in_days": 14,
    "filter_statuses": ["active", "inactive", "future"]
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

To populate license rules:

```json
{
  "task": "populate_license_rules",
  "payload": {
    "dry_run": true
  }
}
```
