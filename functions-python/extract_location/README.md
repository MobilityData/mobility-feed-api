## Function Workflow

1. **Eventarc Trigger**: The original function is triggered by a `CloudEvent` indicating a GTFS dataset upload. It parses the event data to identify the dataset and calculates the bounding box and location information from the GTFS feed.

2. **Pub/Sub Triggered Function**: A new function is triggered by Pub/Sub messages. This allows for batch processing of dataset extractions, enabling multiple datasets to be processed in parallel without waiting for each one to complete sequentially.

3. **HTTP Triggered Batch Function**: Another function, triggered via HTTP request, identifies all latest datasets lacking bounding box or location information. It then publishes messages to the Pub/Sub topic to trigger the extraction process for these datasets.

4. **Data Parsing**: Extracts `stable_id`, `dataset_id`, and the GTFS feed `url` from the triggering event or message.

5. **GTFS Feed Processing**: Retrieves bounding box coordinates and other location-related information from the GTFS feed located at the provided URL.

6. **Database Update**: Updates the bounding box and location information for the dataset in the database.

## Expected Behavior

- Bounding boxes and location information are extracted for the latest datasets that are missing them, improving the efficiency of the process by utilizing both batch and individual dataset processing mechanisms.

## Function Configuration

The functions rely on the following environment variables:
- `FEEDS_DATABASE_URL`: The database URL for connecting to the database containing GTFS datasets.

## Local Development

Local development of these functions should follow standard practices for GCP serverless functions. For general instructions on setting up the development environment, refer to the main [README.md](../README.md) file.