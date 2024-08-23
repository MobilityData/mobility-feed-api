# GTFS & GBFS Analytics Processor

This directory contains Google Cloud Functions that automate the retrieval, processing, and analytics generation for GTFS and GBFS datasets. The project is designed to handle and analyze both GTFS and GBFS data, storing the results in Google Cloud Storage.

## Overview

### `process_analytics_gtfs`

This HTTP-triggered Cloud Function processes GTFS datasets by performing the following steps:

1. **Retrieving Data**: Fetches the latest GTFS dataset per feed from the database.
2. **Processing Data**: Analyzes the dataset, extracting metrics related to validation notices, features, and geographical locations.
3. **Storing Analytics**: Saves the processed data as JSON files in the Google Cloud Storage bucket, updating metrics and analytics files.

#### Files Modified/Created:
- **`analytics_YYYY_MM.json`**: Contains the GTFS analytics data for the specific month in JSON format.  
  **Format:**
  ```json
  {
    "feed_id": "string",
    "dataset_id": "string",
    "notices": {
      "errors": ["string"],
      "warnings": ["string"],
      "infos": ["string"]
    },
    "features": ["string"],
    "created_on": "datetime",
    "last_modified": "datetime",
    "provider": "string",
    "locations": [
      {
        "country_code": "string",
        "country": "string",
        "municipality": "string",
        "subdivision_name": "string"
      }
    ]
  }
  ```

- **`feed_metrics.json`**: Stores aggregated feed-level metrics, including error, warning, and info counts.  
  **Format:**
  ```json
  {
    "feed_id": "string",
    "computed_on": ["datetime"],
    "errors_count": ["int"],
    "warnings_count": ["int"],
    "infos_count": ["int"]
  }
  ```

- **`features_metrics.json`**: Tracks feature usage across feeds, showing the number of feeds using specific features.  
  **Format:**
  ```json
  {
    "feature": "string",
    "computed_on": ["datetime"],
    "feeds_count": ["int"]
  }
  ```

- **`notices_metrics.json`**: Records notice metrics by severity level (error, warning, info).  
  **Format:**
  ```json
  {
    "notice": "string",
    "severity": "string",
    "computed_on": ["datetime"],
    "feeds_count": ["int"]
  }
  ```

- **`analytics_files.json`**: Index of all `analytics_YYYY_MM.json` files stored in the bucket.  
  **Format:**
  ```json
  {
    "file_name": "string",
    "created_on": "datetime"
  }
  ```

### `process_analytics_gbfs`

This HTTP-triggered Cloud Function processes GBFS datasets by performing the following steps:

1. **Retrieving Data**: Fetches the latest GBFS snapshot per feed from the database.
2. **Processing Data**: Analyzes the snapshot, extracting metrics related to validation notices, versions, and geographical locations.
3. **Storing Analytics**: Saves the processed data as JSON files in the Google Cloud Storage bucket, updating metrics and analytics files.

#### Files Modified/Created:
- **`analytics_YYYY_MM.json`**: Contains the GBFS analytics data for the specific month in JSON format.  
  **Format:**
  ```json
  {
    "feed_id": "string",
    "snapshot_id": "string",
    "notices": [
      {
        "keyword": "string",
        "gbfs_file": "string",
        "schema_path": "string"
      }
    ],
    "created_on": "datetime",
    "operator": "string",
    "locations": [
      {
        "country_code": "string",
        "country": "string",
        "municipality": "string",
        "subdivision_name": "string"
      }
    ]
  }
  ```

- **`feed_metrics.json`**: Stores aggregated feed-level metrics, including error counts.  
  **Format:**
  ```json
  {
    "feed_id": "string",
    "computed_on": ["datetime"],
    "errors_count": ["int"]
  }
  ```

- **`versions_metrics.json`**: Tracks the usage of different GBFS versions across feeds.  
  **Format:**
  ```json
  {
    "version": "string",
    "computed_on": ["datetime"],
    "feeds_count": ["int"]
  }
  ```

- **`notices_metrics.json`**: Records notice metrics specific to GBFS, categorized by keyword, file, and schema path.  
  **Format:**
  ```json
  {
    "keyword": "string",
    "gbfs_file": "string",
    "schema_path": "string",
    "computed_on": ["datetime"],
    "feeds_count": ["int"]
  }
  ```

- **`analytics_files.json`**: Index of all `analytics_YYYY_MM.json` files stored in the bucket.  
  **Format:**
  ```json
  {
    "file_name": "string",
    "created_on": "datetime"
  }
  ```

## Project Structure

- **`main.py`**: Defines the HTTP-triggered Cloud Functions that initiate the GTFS and GBFS data analytics processes.
- **`processors/base_analytics_processor.py`**: Contains the base class for analytics processing, providing common logic for GTFS and GBFS processors.
- **`processors/gtfs_analytics_processor.py`**: Implements GTFS-specific data retrieval and processing logic.
- **`processors/gbfs_analytics_processor.py`**: Implements GBFS-specific data retrieval and processing logic.
- **`tests/`**: Unit tests for all modules and functions, ensuring correct functionality and robustness.

## Project Configuration

The following environment variables need to be set:

- `FEEDS_DATABASE_URL`: The URL for the database containing GTFS and GBFS feeds.
- `ANALYTICS_BUCKET`: The name of the Google Cloud Storage bucket where analytics results are stored.

## Local Development

Refer to the main [README.md](../README.md) for general setup instructions for the development environment.