# Rebuild Missing Visualization Files

This function is responsible for rebuilding missing visualization files (PMTiles) for datasets stored in GCS. It checks for datasets that are missing their corresponding visualization files and triggers a workflow to rebuild them.

## Task ID
Use task Id: `rebuild_missing_visualization_files`

## Usage
The function receive the following payload:
```
    {
        "dry_run": bool,  # [optional] If True, do not execute the workflow,
        "check_existing": bool # [optional] If True, check if the visualization files already exist before rebuilding them. Default is True.
        "latest_only": bool # [optional] If True, only check the latest dataset for each feed. Default is True.
        "include_deprecated_feeds": bool # [optional] If True, include deprecated feeds. Default is False.
        "limit": int # [optional] Limit the number of datasets to process. If not provided, process all datasets.
    }
```
Example:
```
{
    "dry_run": true,
    "check_existing": true
}
```

# GCP environment variables
The function uses the following environment variables:

- `DATASETS_BUCKET_NAME` : The name of the GCS bucket where the datasets are stored.
- `PMTILES_BUILDER_QUEUE` : The name of the GCP Task Queue to publish the messages to build the PMTiles files.
- `PROJECT_ID` : The GCP Project id.
- `ENVIRONMENT` : The environment where the function is running.
- `GCP_REGION` : The GCP region where the function is running.
- `SERVICE_ACCOUNT_EMAIL` : The service account email to use to execute the tasks.
