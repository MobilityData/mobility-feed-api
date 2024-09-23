# Batch Datasets
This directory contains the GCP serverless function that triggers the sync feeds in transitland. 
The function publish one Pub/Sub message per transitland feed to be synced.
```json
    {
        "message": {
            "data": 
            {
                "execution_id":  "execution_id",
                "feed_stable_id":  "feed_stable_id",
                "feed_id":  "feed_id",
                "feed_onestop_id":  "feed_onestop_id"
            }            
        }
    }
``` 

# Function configuration
The function is configured using the following environment variables:
- `PUBSUB_TOPIC`: The Pub/Sub topic to publish the messages to.
- `PROJECT_ID`: The GCP Project id.

# Local development
The local development of this function follows the same steps as the other functions. Please refer to the [README.md](../README.md) file for more information.

## Test locally with Google Cloud Emulators

```bash
gcloud components install cloud-datastore-emulator
```

- Install the Pub/Sub emulator
```bash
gcloud components install pubsub-emulator
```
- Install the Cloud Datastore emulator
```bash

```

- Execute the following commands to start the emulators:
```bash
    gcloud beta emulators pubsub start --project=project-id --host-port='localhost:8043'
    gcloud beta emulators datastore start --project=project-id --host-port='localhost:8044'
```
- Start function
```bash
  ./scripts/function-python-run.sh --function_name feed_sync_dispatcher_transitland
```
- Execute function
```bash
   curl http://localhost:8080
```

# Test
- Run the tests
```bash
  ./scripts/api-tests.sh --folder functions-python/feed_sync_dispatcher_transitland 
```