# Build pmtile for a specific GTFS dataset

This function generates the pmtiles for a provided dataset.
pmtiles are used for displaying routes and stops in the UI

## Usage
The function receive the following request:
```
   {
      "feed_stable_id": str, 
      "dataset_stable_id*: str 
   }
```

Example:
```json
   {
      "feed_stable_id": "mdb-1004", 
      "dataset_stable_id": "mdb-1004-202507081807"
   }
```

The function will verify that the dataset stable id starts with the feed stable id (mdb-1004 in our example)

# GCP environment variables
The function uses the following environment variables:
- `ENV`: The environment to use. It can be `dev`, `staging` or `prod`. Default is `dev`.
- `DATASETS_BUCKET_NAME`: The bucket name where the datasets are stored. The task will fail if this is not defined.  The variable has to include the suffix, like `-dev`, `-qa` or `-prod`. 
