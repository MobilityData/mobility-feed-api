# GTFS and GBFS Data Transfer Cloud Functions

This directory includes two HTTP-triggered Google Cloud Functions designed to transfer GTFS and GBFS data into Google BigQuery.

## Overview

These Cloud Functions automate the transfer of GTFS and GBFS data into BigQuery by:

1. **Retrieving**: Collecting all NDJSON files from a Google Cloud Storage bucket.
2. **Loading**: Ingesting the NDJSON data into a new BigQuery table. The table name includes a date string suffix, ensuring that data is grouped by date (with GTFS and GBFS data handled separately).
3. **Cleaning Up**: Deleting the processed NDJSON files from the bucket to prevent reprocessing.

### Cloud Functions

- **`ingest_data_to_big_query_gtfs`**: Handles the transfer of GTFS data to BigQuery.
- **`ingest_data_to_big_query_gbfs`**: Handles the transfer of GBFS data to BigQuery.

Both functions are triggered via HTTP and can be invoked manually or automatically by a Cloud Scheduler on a predefined schedule.

## Project Structure

- **`main.py`**: Defines the HTTP-triggered Cloud Functions that initiate the GTFS and GBFS data transfer processes.
- **`gbfs_big_query_ingest.py`**: Contains the logic for retrieving NDJSON files, loading GBFS data into BigQuery, and deleting the processed files.
- **`gtfs_big_query_ingest.py`**: Contains the logic for retrieving NDJSON files, loading GTFS data into BigQuery, and deleting the processed files.
- **`common/`**: Shared utilities and helper functions for interacting with Google Cloud Storage and BigQuery.
- **`tests/`**: Unit tests for all modules and functions, ensuring correct functionality and robustness.

## Function Configuration

The following environment variables are required for the functions to operate:

- **`PROJECT_ID`**: Google Cloud project ID where the BigQuery dataset and table reside.
- **`BUCKET_NAME`**: Name of the Google Cloud Storage bucket where the NDJSON files are stored.
- **`DATASET_ID`**: BigQuery dataset ID where the NDJSON data will be loaded.
- **`TABLE_ID`**: Prefix for the BigQuery table ID. The actual table name will include a date string suffix.
- **`BQ_DATASET_LOCATION`**: Location of the BigQuery dataset.

## Local Development

For local development, follow the same steps as for other functions in the project. Please refer to the [README.md](../README.md) file in the parent directory for detailed instructions.
