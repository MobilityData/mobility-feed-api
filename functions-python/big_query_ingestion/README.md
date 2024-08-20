# GTFS and GBFS Data Transfer Cloud Functions

This project includes two HTTP-triggered Google Cloud Functions designed to process and load GTFS (General Transit Feed Specification) and GBFS (General Bikeshare Feed Specification) data into Google BigQuery.
## Overview

These Cloud Functions automate the ingestion of GTFS and GBFS data into BigQuery by:

1. **Retrieving**: Downloading JSON report files from a Google Cloud Storage bucket.
2. **Processing**: Enriching the data with additional fields such as location details and ensuring it adheres to predefined schemas (defined in `src/gbfs/gbfs_schema.json` and `src/gtfs/gtfs_schema.json`).
3. **Loading**: Converting the processed data to NDJSON format and loading it into BigQuery.

### Cloud Functions

- **`ingest_data_to_big_query_gtfs`**: Handles the GTFS data transfer process.
- **`ingest_data_to_big_query_gbfs`**: Handles the GBFS data transfer process.

Both functions are triggered via HTTP and are typically invoked automatically by a Cloud Scheduler on a predefined schedule.

## Project Structure

- **`main.py`**: Defines the HTTP-triggered Cloud Functions that initiate the GTFS and GBFS data transfer processes.
- **`gbfs_big_query_ingest.py`**: Contains the logic for processing and loading GBFS data into BigQuery.
- **`gtfs_big_query_ingest.py`**: Contains the logic for processing and loading GTFS data into BigQuery.
- **`common/`**: Shared utilities and helper functions, including schema loading, data filtering, and BigQuery data transfer logic.
- **`tests/`**: Unit tests for all modules and functions, ensuring correct functionality and robustness.

## Function Configuration

The following environment variables are required for the functions to operate:

- **`PROJECT_ID`**: Google Cloud project ID where the BigQuery dataset and table reside.
- **`BUCKET_NAME`**: Name of the Google Cloud Storage bucket where the JSON report files are stored.
- **`DATASET_ID`**: BigQuery dataset ID where the processed data will be loaded.
- **`TABLE_ID`**: BigQuery table ID where the processed data will be loaded.
- **`BQ_DATASET_LOCATION`**: Location of the BigQuery dataset.
- **`FEEDS_DATABASE_URL`**: Database URL for retrieving location details associated with the feeds.

## Local Development

For local development, follow the same steps as for other functions in the project. Please refer to the [README.md](../README.md) file in the parent directory for detailed instructions.
