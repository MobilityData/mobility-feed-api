# Backfill Dataset Service Date Range
This directory contains the GCP serverless function that will backfill the GTFS Datasets to include the service date range based off their latest validation report.
It will only fill `NULL` values and not over write existing values

## Function Workflow
1. **HTTP Request Trigger**: The function is invoked through an HTTP request that includes identifiers for a dataset and feed.
2. **Dataset Query**: Retreives all gtfs datasets which have a missing service date range value
3. **Validation Report Retrieval**: For each dataset, get download the latest validaiton json report to retrieve service date ranges
4. **Database Update**: Updates the dataset with the values retrieved from the validation report

## Function Configuration
The function depends on several environment variables:
- `FEEDS_DATABASE_URL`: The database URL for connecting to the database containing GTFS datasets and related entities.

## Local Development
Follow standard practices for local development of GCP serverless functions. Refer to the main [README.md](../README.md) for general setup instructions for the development environment.

## Testing
To run it locally `./scripts/function-python-run.sh --function_name backfill_dataset_service_date_range`

In postman or similar service, with a `POST` call `v1/backfill-dataset-service-date-range`