# Bounding Box Extraction
This directory contains the GCP function responsible for processing GTFS dataset uploads to extract and update the bounding box information in the database. The function is triggered by a `CloudEvent`, parses the event data to identify the dataset, and calculates the bounding box from the GTFS feed.

## Function Workflow
1. **Event Trigger**: The function is triggered by a `CloudEvent` indicating a GTFS dataset upload.
2. **Data Parsing**: Extracts `stable_id`, `dataset_id`, and the GTFS feed `url` from the CloudEvent data.
3. **GTFS Feed Processing**: Retrieves bounding box coordinates from the GTFS feed located at the provided URL.
4. **Database Update**: Updates the bounding box information for the dataset in the database.

## Function Configuration
The function relies on the following environment variables:
- `FEEDS_DATABASE_URL`: The database URL for connecting to the database containing GTFS datasets.

## Local Development
Local development of this function should follow standard practices for GCP serverless functions.
For general instructions on setting up the development environment, refer to the main [README.md](../README.md) file.
