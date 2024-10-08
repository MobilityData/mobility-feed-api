# GBFS Validator Pipeline

This pipeline consists of two functions that work together to validate GBFS feeds:

1. **`gbfs-validator-batch`**: This function is HTTP-triggered by a Cloud Scheduler.
2. **`gbfs-validator-pubsub`**: This function is triggered by a Pub/Sub message.

### Pipeline Overview

- **`gbfs-validator-batch`**: This function checks all GBFS feeds in the database and publishes a message to the Pub/Sub topic for each feed to initiate its validation.
- **`gbfs-validator-pubsub`**: This function is triggered by the Pub/Sub message generated by the batch function. It handles the validation of the individual feed.

### Message Format

The message published by the batch function to the Pub/Sub topic follows this format:

```json
{
    "message": {
        "data": {
            "execution_id": "execution_id",
            "stable_id": "stable_id",
            "feed_id": "id",
            "url": "auto_discovery_url",
            "latest_version": "version"
        }            
    }
}
```

### Functionality Details

- **`gbfs-validator-batch`**: Triggered per execution ID, this function iterates over all GBFS feeds, preparing and publishing individual messages to the Pub/Sub topic.
- **`gbfs-validator-pubsub`**: Triggered per feed, this function performs the following steps:
  1. **Download the feed snapshot to GCP**: It uploads all related files to the specified Cloud Storage bucket and updates the `gbfs.json` file to point to the newly uploaded files.
  2. **Validate the feed**: Run the GBFS validator on the feed snapshot.
  3. **Update the database**: The function updates the database with the snapshot information and validation report details.

## Function Configuration

### Batch Function Environment Variables

The `gbfs-validator-batch` function requires the following environment variables:

- **`PUBSUB_TOPIC_NAME`**: The name of the Pub/Sub topic where messages will be published.
- **`PROJECT_ID`**: The Google Cloud Project ID used to construct the full topic path.
- **`FEEDS_DATABASE_URL`**: The database connection string for accessing the GBFS feeds.

### Pub/Sub Function Environment Variables

The `gbfs-validator-pubsub` function requires the following environment variables:

- **`BUCKET_NAME`**: The name of the Cloud Storage bucket where the GBFS snapshots will be stored. Defaults to `"mobilitydata-gbfs-snapshots-dev"` if not set.
- **`FEEDS_DATABASE_URL`**: The database connection string for accessing the GBFS feeds.
- **`MAXIMUM_EXECUTIONS`**: The maximum number of times a trace can be executed before it is considered as having reached its limit. Defaults to `1` if not set.

## Local Development

For local development, these functions should be developed and tested according to standard practices for GCP serverless functions. Refer to the main [README.md](../README.md) file for general instructions on setting up the development environment.
