# Mission Control

This directory contains Google Cloud Functions used as a single point of access to multiple _tasks_.

## Usage
The function receive the following payload:
```
  {
   "name": "string", # [required] Name of the task to execute
   "payload": { } [optional] Payload to pass to the task
  }
```
Example:
```
{
  "name": "rebuild_missing_validation_reports",
  "payload": {
    "dry_run": true,
    "filter_after_in_days": 14,
    "filter_statuses": ["active", "inactive", "future"]
  }
}
```
To get the list of supported tasks use:
``
{
  "name": "list_tasks",
  "payload": {}
}
`````
