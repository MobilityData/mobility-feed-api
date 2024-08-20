import json
import os

from big_query_ingestion.src.common.bg_schema import filter_json_by_schema, load_json_schema
from big_query_ingestion.src.common.bq_data_transfer import bucket_name, BiqQueryDataTransfer
from big_query_ingestion.src.common.feeds_locations import get_feeds_locations_map


class BiqQueryDataTransferGBFS(BiqQueryDataTransfer):
    def __init__(self):
        super().__init__()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.schema_path = os.path.join(current_dir, 'gbfs_schema.json')
        self.nd_json_path_prefix = 'ndjson/gbfs'

    def process_bucket_files(self):
        bucket = self.storage_client.get_bucket(bucket_name)
        blobs = list(self.storage_client.list_blobs(bucket_name))
        json_schema = load_json_schema(self.schema_path)
        blob_names = {blob.name for blob in blobs}
        locations_map = get_feeds_locations_map('gbfs')

        for blob in blobs:
            if 'report_' in blob.name and blob.name.endswith('.json'):
                feed_id = blob.name.split('/')[0]
                feed_snapshot_id = blob.name.split('/')[1]
                report_name = '.'.join(blob.name.split('/')[2].split('.')[:-1])
                ndjson_blob_name = f"{self.nd_json_path_prefix}/{feed_id}/{feed_snapshot_id}/{report_name}.ndjson"
                if ndjson_blob_name in blob_names:
                    print(f"NDJSON file {ndjson_blob_name} already exists. Skipping...")
                    continue
                json_data = json.loads(blob.download_as_string().decode('utf-8'))

                json_data['feedId'] = feed_id
                json_data['snapshotId'] = feed_snapshot_id
                locations = locations_map.get(feed_id, [])
                json_data['locations'] = [{
                    'country': location.country,
                    'countryCode': location.country_code,
                    'subdivisionName': location.subdivision_name,
                    'municipality': location.municipality,
                } for location in locations]

                # validated_at = json_data['summary'].get('validatedAt', None)
                # json_data['validatedAt'] = validated_at

                # for notice in json_data.get('notices', []):
                #     if 'sampleNotices' in notice:
                #         notice['sampleNotices'] = json.dumps(notice['sampleNotices'], separators=(',', ':'))
                json_data = filter_json_by_schema(json_schema, json_data)

                ndjson_content = json.dumps(json_data, separators=(',', ':'))
                ndjson_blob = bucket.blob(ndjson_blob_name)
                ndjson_blob.upload_from_string(ndjson_content + '\n')
                print(f"Processed and uploaded {ndjson_blob_name}")


if __name__ == '__main__':
    BiqQueryDataTransferGBFS().send_data_to_bigquery()
