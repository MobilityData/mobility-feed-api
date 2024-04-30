# Update Validation Report
This function activates the process that updates the validation report for all latest datasets that lack the current version of the report.

## Function Workflow
1. **HTTP Request Trigger**: The function is initiated via an HTTP request.
2. **Retrieve Latest Datasets**: Retrieves the latest datasets from the database.
3. **Validate Latest Validation Report**: Verifies whether the latest dataset possesses the current validation report in the GCP bucket.
4. **Trigger Validation Report Processing**: If the latest dataset lacks the current validation report, this function is triggered to update the report by modifying the dataset metadata. This action initiates the `gtfs_validator_execution` workflow.
5. **Return Response**: Outputs a response indicating the status of the validation report update. The response format is as follows:
```json
{
  "message": "Updated [# of datasets] validation report(s)",
  "updated_datasets": ["dataset_id_1", "dataset_id_2", ...],  # List of dataset IDs with updated validation reports
  "ignored_datasets": ["dataset_id_3", "dataset_id_4", ...]  # List of dataset IDs that either already have the latest validation report or are invalid
}
```

## Function Configuration
The function relies on several environmental variables:
- `FEEDS_DATABASE_URL`: URL used to connect to the database that holds GTFS datasets and related data.
- `ENV`: Specifies the environment (`dev`, `qa`, or `prod`), used to determine the appropriate bucket name for retrieving validation reports.
- `MAX_RETRY`: Maximum attempts to update a dataset’s validation report.
- `BATCH_SIZE`: Number of datasets processed in each batch to prevent rate limiting by the web validator, set at a five-second interval.
- `WEB_VALIDATOR_URL`: URL for the web validator that checks for the latest validation report version.
## Local Development
Follow standard practices for local development of GCP serverless functions. Refer to the main [README.md](../README.md) for general setup instructions for the development environment.
