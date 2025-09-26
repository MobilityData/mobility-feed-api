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
    "data": {
      "execution_id": "execution_id",
      "producer_url": "producer_url",
      "feed_stable_id": "feed_stable_id",
      "feed_id": "feed_id",
      "dataset_id": "dataset_id",
      "dataset_hash": "dataset_hash",
      "authentication_type": "authentication_type",
      "authentication_info_url": "authentication_info_url",
      "api_key_parameter_name": "api_key_parameter_name"
    }
  }
}
```

# Example

```json
{
  "message": {
    "data": {
      "execution_id": "JLU_20250721A",
      "producer_url": "http://api.511.org/transit/datafeeds?operator_id=CE",
      "feed_stable_id": "mdb-2684",
      "feed_id": "2f5d7b4e-bb9b-49ae-a011-b61d7d9b53ff",
      "dataset_id": null,
      "dataset_hash": null,
      "authentication_type": "1",
      "authentication_info_url": "https://511.org/open-data/token",
      "api_key_parameter_name": "api_key"
    }
  }
}

{
  "message": {
    "data": {
      "execution_id": "batch-trace-e5eaa516bd884c0a39861d08de301d97/2153210919778512803;o=1",
      "producer_url": "https://www.stm.info/sites/default/files/gtfs/gtfs_stm.zip",
      "feed_stable_id": "mdb-2126",
      "feed_id": "9f1748c5-b482-4577-819e-ce78c75980b3",
      "dataset_stable_id": "mdb-2126-202504170018",
      "dataset_hash": "7d019543ee12b2a44d580d7780d71546108a2cb1c4f3bfcc5cf3ee97b847fafd",
      "authentication_type": "0",
      "authentication_info_url": "",
      "api_key_parameter_name": ""
    }
  }
}

```

# Function configuration

The function is configured using the following environment variables:

- `DATASETS_BUCKET_NAME`: The name of the bucket where the datasets are stored.
- `FEEDS_DATABASE_URL`: The URL of the feeds database.
- `MAXIMUM_EXECUTIONS`: [Optional] The maximum number of executions per datasets. This controls the number of times a dataset can be processed per execution id. By default, is 1.

# Local development

The local development of this function follows the same steps as the other functions. Please refer to the [README.md](../README.md) file for more information.
