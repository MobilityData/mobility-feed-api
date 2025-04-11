# Rebuild Missing Validation Reports

This task generates the missing reports in the GTFS datasets. 
The reports are generated using the _gtfs_validator_ GCP workflow.

## Usage
The function receive the following payload:
```
    {
        "dry_run": bool,  # [optional] If True, do not execute the workflow
        "filter_after_in_days": int, # [optional] Filter datasets older than this number of days(default: 14 days ago)
        "filter_statuses": list[str] # [optional] Filter datasets by status(in)
    }
```
Example:
``
{
    "dry_run": true,
    "filter_after_in_days": 14,
    "filter_statuses": ["active", "inactive", "future"]
}
`````