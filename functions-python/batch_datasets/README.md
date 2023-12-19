# Batch Datasets
This directory GCP serverless function that enqueue datasets all active datasets.
The function is triggered by a Pub/Sub message with the following format:
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

