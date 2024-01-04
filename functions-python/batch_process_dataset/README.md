# Bath Process Dataset
This function process a dataset and publish a message to the `batch_datasets` topic.
The function download the dataset from the source and compares the previous file hash.
If the hash are different, the function will create a new dataset making it the latest dataset for the related feed.
If the hash is the same, the function will not do anything.

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