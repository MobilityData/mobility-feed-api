import json
import logging
import os

from ..common.bg_schema import filter_json_by_schema, load_json_schema
from ..common.bq_data_transfer import bucket_name, BigQueryDataTransfer
from ..common.feeds_locations import get_feeds_locations_map


class BigQueryDataTransferGTFS(BigQueryDataTransfer):
    def __init__(self):
        super().__init__()
        current_dir = os.path.dirname(
            os.path.abspath(__file__)
        )  # Get the directory of the current file
        self.schema_path = os.path.join(
            current_dir, "gtfs_schema.json"
        )  # Replace 'schema.json' with your file name

    def process_bucket_files(self):
        bucket = self.storage_client.get_bucket(bucket_name)
        blobs = list(self.storage_client.list_blobs(bucket_name))
        json_schema = load_json_schema(self.schema_path)
        blob_names = {blob.name for blob in blobs}
        locations_map = get_feeds_locations_map("gtfs")

        for blob in blobs:
            if "report_" in blob.name and blob.name.endswith(".json"):
                feed_id = blob.name.split("/")[0]
                feed_dataset_id = blob.name.split("/")[1]
                report_id = ".".join(blob.name.split("/")[2].split(".")[:-1])
                ndjson_blob_name = f"{self.nd_json_path_prefix}/{feed_id}/{feed_dataset_id}/{report_id}.ndjson"
                if ndjson_blob_name in blob_names:
                    logging.warning(
                        f"NDJSON file {ndjson_blob_name} already exists. Skipping..."
                    )
                    continue
                json_data = json.loads(blob.download_as_string().decode("utf-8"))

                # Add feedId to the JSON data
                json_data["feedId"] = feed_id
                json_data["datasetId"] = feed_dataset_id
                locations = locations_map.get(feed_id, [])
                json_data["locations"] = [
                    {
                        "country": location.country,
                        "countryCode": location.country_code,
                        "subdivisionName": location.subdivision_name,
                        "municipality": location.municipality,
                    }
                    for location in locations
                ]

                # Extract validatedAt and add it to the same level
                validated_at = json_data.get("summary", {}).get("validatedAt", None)
                json_data["validatedAt"] = validated_at

                # Convert sampleNotices to JSON strings
                for notice in json_data.get("notices", []):
                    if "sampleNotices" in notice:
                        notice["sampleNotices"] = json.dumps(
                            notice["sampleNotices"], separators=(",", ":")
                        )
                json_data = filter_json_by_schema(json_schema, json_data)

                # Convert the JSON data to a single NDJSON record (one line)
                ndjson_content = json.dumps(json_data, separators=(",", ":"))
                ndjson_blob = bucket.blob(ndjson_blob_name)
                ndjson_blob.upload_from_string(ndjson_content + "\n")
                logging.info(f"Processed and uploaded {ndjson_blob_name}")
