# Update GeoJSON files

This task adjust the GeoJSON files removing the map IDs and reducing the precision of the coordinates to 5 decimal places. ALso updates the geolocation_file_created_date and geolocation_file_dataset_id fields in the Feed table.

---

## Task ID

Use task ID: `update_geojson_files`

---

## Usage

The function accepts the following payload:

```json
{
  "dry_run": true,                // [optional] If true, do not upload or modify the database (default: true)
  "precision": 5,                 // [optional] Number of decimal places to keep in coordinates (default: 5)
  "limit": 10,                    // [optional] Limit the number of feeds to process (default: no limit)
  "data_type": "gtfs"             // [optional] Type of data to process, either "gtfs" or "gbfs" (default: "gtfs")
}
```

### Example:

```json
{
  "dry_run": true,
  "data_type": "gtfs",
  "limit": 10
}
```

---

## What It Does

List all feeds with GeoJSON files, download each file, remove map IDs, reduce coordinate precision to the specified number of decimal places, and re-upload the modified file.
Also updates the `geolocation_file_created_date` and `geolocation_file_dataset_id` fields in the `Feed` table.

## GCP Environment Variables

The function requires the following environment variables:

| Variable                       | Description                                                             |
|--------------------------------|-------------------------------------------------------------------------|
| `DATASETS_BUCKET_NAME`         | The name of the GCS bucket used to store extracted GTFS files           | 
| `GBFS_SNAPSHOTS_BUCKET_NAME`   | The name of the GCS bucket used to store extracted GBFS snapshots files | 

---

## Additional Notes

* Commits to the database occur in batches of 100 feeds to improve performance and avoid large transaction blocks.
* If `dry_run` is enabled, files are uploads or DB modifications are performed. Only the number of affected feeds is logged.
* The function is safe to rerun. It will only affect feeds with missing geolocation_file_dataset_id.
