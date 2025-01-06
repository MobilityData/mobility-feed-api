import unittest
from unittest.mock import patch

from gtfs.gtfs_big_query_ingest import BigQueryDataTransferGTFS


class TestBigQueryDataTransferGTFS(unittest.TestCase):
    @patch("google.cloud.bigquery.Client")
    @patch("google.cloud.storage.Client")
    def setUp(self, mock_storage_client, _):
        self.mock_storage_client = mock_storage_client
        self.transfer = BigQueryDataTransferGTFS()

    def test_attributes(self):
        self.assertIn("gtfs_schema.json", self.transfer.schema_path)
