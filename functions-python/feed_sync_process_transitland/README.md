# Feed Sync Process

Subscribed to the topic set in the `feed-sync-dispatcher` function, `feed-sync-process` is triggered for each message published. It handles the processing of feed updates, ensuring data consistency and integrity. The function performs the following operations:

1. **Feed Status Check**: It verifies the current state of the feed in the database using external_id and source.
2. **URL Validation**: Checks if the feed URL already exists in the database.
3. **Feed Processing**: Based on the current state:
   - If no existing feed is found, creates a new feed entry
   - If feed exists with a different URL, creates a new feed and deprecates the old one
   - If feed exists with the same URL, no action is taken
4. **Batch Processing Trigger**: For non-authenticated feeds, publishes events to the dataset batch topic for further processing.

The function maintains feed history through the `redirectingid` table and ensures proper status tracking with 'active' and 'deprecated' states.

# Message Format
The function expects a Pub/Sub message with the following format:
```json
{
    "message": {
        "data": {
            "external_id": "feed-identifier",
            "feed_id": "unique-feed-id",
            "feed_url": "http://example.com/feed",
            "execution_id": "execution-identifier",
            "spec": "gtfs",
            "auth_info_url": null,
            "auth_param_name": null,
            "type": null,
            "operator_name": "Transit Agency Name",
            "country": "Country Name",
            "state_province": "State/Province",
            "city_name": "City Name",
            "source": "TLD",
            "payload_type": "new|update"
        }
    }
}
```

# Function Configuration
The function is configured using the following environment variables:
- `PROJECT_ID`: The Google Cloud project ID
- `DATASET_BATCH_TOPIC_NAME`: The name of the topic for batch processing triggers
- `FEEDS_DATABASE_URL`: The URL of the feeds database
- `ENV`: [Optional] Environment identifier (e.g., 'dev', 'prod')

# Database Schema
The function interacts with the following tables:
1. `feed`: Stores feed information
   - Contains fields like id, data_type, feed_name, producer_url, etc.
   - Tracks feed status ('active' or 'deprecated')
   - Uses CURRENT_TIMESTAMP for created_at

2. `externalid`: Maps external identifiers to feed IDs
   - Links external_id and source to feed entries
   - Maintains source tracking

3. `redirectingid`: Tracks feed updates
   - Maps old feed IDs to new ones
   - Maintains update history

# Local development
The local development of this function follows the same steps as the other functions.

Install Google Pub/Sub emulator, please refer to the [README.md](../README.md) file for more information.

## Python requirements

- Install the requirements
```bash
    pip install -r ./functions-python/feed_sync_process_transitland/requirements.txt
```

## Test locally with Google Cloud Emulators

- Execute the following commands to start the emulators:
```bash
    gcloud beta emulators pubsub start --project=test-project --host-port='localhost:8043'
```

- Create a Pub/Sub topic in the emulator:
```bash
    curl -X PUT "http://localhost:8043/v1/projects/test-project/topics/feed-sync-transitland"
```

- Start function
```bash
  export PUBSUB_EMULATOR_HOST=localhost:8043 && ./scripts/function-python-run.sh --function_name feed_sync_process_transitland
```

- [Optional]: Create a local subscription to print published messages:
```bash
./scripts/pubsub_message_print.sh feed-sync-process-transitland
```

- Execute function
```bash
   curl http://localhost:8080
```

- To run/debug from your IDE use the file `main_local_debug.py`

# Test
- Run the tests
```bash
  ./scripts/api-tests.sh --folder functions-python/feed_sync_dispatcher_transitland 
```
