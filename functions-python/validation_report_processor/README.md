# Validation Report Processing
This directory contains the Google Cloud Platform function designed for processing GTFS dataset validation reports to create and update entities in the database based on the contents of these reports. The function is triggered via an HTTP request, parses the report data, and stores validation results.

## Function Workflow
1. **HTTP Request Trigger**: The function is invoked through an HTTP request that includes identifiers for a dataset and feed.
2. **Report Validation**: Validates the JSON format and content of the report fetched from a predefined URL.
3. **Entity Creation**: Based on the contents of the validation report, the function creates several entities including validation reports, features, and notices associated with the dataset.
4. **Database Update**: Adds new entries to the database or updates existing ones based on the validation report.

## Function Configuration
The function depends on several environment variables:
- `FILES_ENDPOINT`: The endpoint URL where report files are located.
- `FEEDS_DATABASE_URL`: The database URL for connecting to the database containing GTFS datasets and related entities.

## Local Development
Follow standard practices for local development of GCP serverless functions. Refer to the main [README.md](../README.md) for general setup instructions for the development environment.

### Testing
For testing, simulate HTTP requests using tools like Postman or curl. Ensure to include both `dataset_id` and `feed_id` in the JSON payload:
```json
{
  "dataset_id": "example_dataset_id",
  "feed_id": "example_feed_id"
}
```
