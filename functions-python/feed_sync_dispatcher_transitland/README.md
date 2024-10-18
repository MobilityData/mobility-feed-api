# Batch Datasets
This directory contains the GCP serverless function that triggers the sync feeds in transitland. 
The function publish one Pub/Sub message per transitland feed to be synced.
```json
    {
        "message": {
            "data": 
            {
                external_id=data["feeds_onestop_id"],
                feed_id=data["feed_id"],
                execution_id=execution_id,
                feed_url=data["feed_url"],
                spec=data["spec"],
                auth_info_url=data["auth_info_url"],
                auth_param_name=data["auth_param_name"],
                type=data["type"],
                operator_name=data["operator_name"],
                country=data["country"],
                state_province=data["state_province"],
                city_name=data["city_name"],
                payload_type=payload_type
            }            
        }
    }
``` 

# Function configuration
The function is configured using the following environment variables:
- `PUBSUB_TOPIC`: The Pub/Sub topic to publish the messages to.
- `PROJECT_ID`: The GCP Project id.
- `TRANSITLAND_API_KEY`: The Transitland API key(secret).

# Local development
The local development of this function follows the same steps as the other functions.

Install Google Pub/Sub emulator, please refer to the [README.md](../README.md) file for more information.

## Python requirements

- Install the requirements
```bash
    pip install -r ./functions-python/feed_sync_dispatcher_transitland/requirements.txt
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
  export PUBSUB_EMULATOR_HOST=localhost:8043 && ./scripts/function-python-run.sh --function_name feed_sync_dispatcher_transitland
```

- [Optional]: Create a local subscription to print published messages:
```bash
./scripts/pubsub_message_print.sh feed-sync-transitland
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