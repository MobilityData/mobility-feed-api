# Validation Report Conversion

This directory contains Google Cloud Functions that automate the retrieval, processing, and conversion of validation reports into NDJSON format, which are then stored in a Google Cloud Storage bucket. The project is designed to handle validation reports for both GTFS and GBFS datasets.

##  Overview

### `convert_reports_to_ndjson`

This Cloud Function is triggered by a Cloud Event when a validation report is added to the Google Cloud Storage bucket. It performs the following steps:

1. **Retrieving**: Downloads the JSON report file from the specified Google Cloud Storage bucket.
2. **Processing**: Enriches the data with additional fields such as location details and ensures the data adheres to predefined schemas (defined in `gbfs_schema.json` and `gtfs_schema.json`).
3. **Loading**: Converts the processed data to NDJSON format and uploads it back to the bucket.

### `batch_convert_reports_to_ndjson`

This HTTP-triggered Cloud Function processes all the validation reports in the bucket by performing the following steps:

1. **Retrieving**: Lists all JSON report files in the Google Cloud Storage bucket.
2. **Processing**: For each report, simulates a Cloud Event and calls `convert_reports_to_ndjson` to handle the conversion, following the same steps as above.
3. **Loading**: The converted NDJSON files are stored back in the same bucket.

## Project Structure
- **`main.py`**: Defines the HTTP-triggered Cloud Functions that initiate the GTFS and GBFS data conversion processes.
- **`validation_report_converter.py`**: Contains the logic for retrieving, processing, and converting validation reports to NDJSON format.
- **`utils/`**: Shared utilities and helper functions for interacting with Google Cloud Storage and BigQuery.
- **`tests/`**: Unit tests for all modules and functions, ensuring correct functionality and robustness.

## Project Configuration

The following environment variables need to be set:

- `PROJECT_ID`: The Google Cloud project ID.
- `BUCKET_NAME`: The name of the Google Cloud Storage bucket where validation reports are stored.
- `DATA_TYPE`: The type of data being processed (`gtfs` or `gbfs`).

## Local Development

Follow standard practices for local development of GCP serverless functions. Refer to the main [README.md](../README.md) for general setup instructions for the development environment.
