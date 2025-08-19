# Batch Datasets
This directory contains the GCP serverless function that enqueue all active feeds to download datasets.
The function accepts an option request body to limit the feeds to process, otherwise it processes all active feeds:
```json
{
    "feed_stable_ids": ["feed_id_1", "feed_id_2"]
}
```

The function publish one Pub/Sub message per active feed with the following format:
```json
    {
        "message": {
            "data": 
            {
                "execution_id":  "execution_id",
                "producer_url":  "producer_url",
                "feed_stable_id":  "feed_stable_id",
                "feed_id":  "feed_id",
                "dataset_id":  "dataset_id",
                "dataset_hash":  "dataset_hash",
                "authentication_type":  "authentication_type",
                "authentication_info_url":  "authentication_info_url",
                "api_key_parameter_name": "api_key_parameter_name"
            }            
        }
    }
``` 

# Function configuration
The function is configured using the following environment variables:
- `PUBSUB_TOPIC`: The Pub/Sub topic to publish the messages to.
- `PROJECT_ID`: The GCP Project id. 
- `ENVIRONMENT`: The environment where the function is running. It can be `dev`, `qa` or `prod`.
- `FEEDS_LIMIT`:[Optional] The number of message to publish. By default, is 10 unless it's running in `prod` or the parameter is passed.

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
  ./scripts/function-python-run.sh --function_name batch_datasets
```
- Execute function
```bash
   curl http://localhost:8080
```

# Test
- Run the tests
```bash
  ./scripts/api-tests.sh --folder functions-python/batch_datasets 
```