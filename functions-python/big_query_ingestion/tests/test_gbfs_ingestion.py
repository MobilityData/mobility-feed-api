import json
import unittest
from unittest.mock import patch, MagicMock

from big_query_ingestion.src.gbfs.gbfs_big_query_ingest import BigQueryDataTransferGBFS


class TestBigQueryDataTransferGBFS(unittest.TestCase):
    @patch("google.cloud.bigquery.Client")
    @patch("google.cloud.storage.Client")
    def setUp(self, mock_storage_client, _):
        self.mock_storage_client = mock_storage_client
        self.transfer = BigQueryDataTransferGBFS()

    @patch("big_query_ingestion.src.gbfs.gbfs_big_query_ingest.get_feeds_locations_map")
    @patch("big_query_ingestion.src.gbfs.gbfs_big_query_ingest.load_json_schema")
    def test_process_bucket_files(
        self, mock_load_json_schema, mock_get_feeds_locations_map
    ):
        # Mocking the JSON schema and locations map
        mock_json_schema = {
            "fields": [
                {"name": "feedId", "type": "STRING"},
                {"name": "snapshotId", "type": "STRING"},
                {
                    "name": "locations",
                    "type": "RECORD",
                    "mode": "REPEATED",
                    "fields": [
                        {"name": "country", "type": "STRING"},
                        {"name": "countryCode", "type": "STRING"},
                        {"name": "subdivisionName", "type": "STRING"},
                        {"name": "municipality", "type": "STRING"},
                    ],
                },
            ]
        }
        mock_load_json_schema.return_value = mock_json_schema

        mock_locations_map = {
            "feed1": [
                MagicMock(
                    country="Country1",
                    country_code="C1",
                    subdivision_name="Subdivision1",
                    municipality="City1",
                )
            ]
        }
        mock_get_feeds_locations_map.return_value = mock_locations_map

        # Mocking the blobs in the bucket
        mock_blob = MagicMock()
        mock_blob.name = "feed1/123/report_file.json"
        mock_blob.download_as_string.return_value = json.dumps({"key": "value"}).encode(
            "utf-8"
        )

        self.mock_storage_client().list_blobs.return_value = [mock_blob]
        self.mock_storage_client().get_bucket.return_value = MagicMock()

        mock_bucket = MagicMock()
        mock_blob.upload_from_string = MagicMock()
        self.mock_storage_client().get_bucket.return_value = mock_bucket

        self.transfer.process_bucket_files()

        mock_load_json_schema.assert_called_once_with(self.transfer.schema_path)
        mock_get_feeds_locations_map.assert_called_once_with("gbfs")
        self.mock_storage_client().list_blobs.assert_called_once()
        mock_blob.download_as_string.assert_called_once()

        expected_json_data = {
            "feedId": "feed1",
            "snapshotId": "123",
            "locations": [
                {
                    "country": "Country1",
                    "countryCode": "C1",
                    "subdivisionName": "Subdivision1",
                    "municipality": "City1",
                }
            ],
        }
        expected_ndjson_content = (
            json.dumps(expected_json_data, separators=(",", ":")) + "\n"
        )
        mock_bucket.blob().upload_from_string.assert_called_once_with(
            expected_ndjson_content
        )
