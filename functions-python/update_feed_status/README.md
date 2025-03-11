# Update Feed Status
This directory contains the GCP serverless function that will update all the feed statuses according to their associated latest dataset service date range.

It will exclude Feeds with exisiting status 'deprecated' and 'development'

## Function Workflow
1. **HTTP Request Trigger**: The function is invoked through an HTTP request that includes identifiers for a dataset and feed.
2. **Dataset Query**: Retreives all feeds which have latest dataset with exisitng values for the service date range
3. **Feed Update Query**: Update the feed status based on the service date range values comparing vs current date

## Function Configuration
The function depends on several environment variables:
- `FEEDS_DATABASE_URL`: The database URL for connecting to the database containing GTFS datasets and related entities.

## Local Development
Follow standard practices for local development of GCP serverless functions. Refer to the main [README.md](../README.md) for general setup instructions for the development environment.

## Testing
To run it locally `./scripts/function-python-run.sh --function_name update_feed_status`

In postman or similar service, with a `POST` call `v1/update_feed_status`