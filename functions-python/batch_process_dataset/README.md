# Bath Process Dataset
Subscribed to the topic set in the `batch-datasets` function, `batch-process-dataset` is triggered for each message published. It handles the processing of each feed individually, ensuring data consistency and integrity. The function performs the following operations:

1. **Download Data**: It retrieves the feed data from the provided URL.
2. **Compare Hashes**: The SHA256 hash of the downloaded data is compared to the hash of the last stored version to detect changes.
   - If the hash is unchanged, the dataset is considered up-to-date, and no further action is taken.
   - If the hash has changed, it is indicative of an update, and a new `Dataset` entity is created and stored with the corresponding feed information.

The URL format for accessing these datasets is standardized as `<bucket-url>/<feed_stable_id>/<dataset_id>.zip`, ensuring a consistent and predictable path for data retrieval.


# Message format
The function expects a Pub/Sub message with the following format:
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
- `DATASETS_BUCKET_NANE`: The name of the bucket where the datasets are stored.
- `FEEDS_DATABASE_URL`: The URL of the feeds database.
- `MAXIMUM_EXECUTIONS`: [Optional] The maximum number of executions per datasets. This controls the number of times a dataset can be processed per execution id. By default, is 1.


# Local development
The local development of this function follows the same steps as the other functions. Please refer to the [README.md](../README.md) file for more information.