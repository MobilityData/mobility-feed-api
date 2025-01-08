import unittest
from unittest.mock import patch

from gbfs.gbfs_big_query_ingest import BigQueryDataTransferGBFS


class TestBigQueryDataTransferGBFS(unittest.TestCase):
    @patch("google.cloud.bigquery.Client")
    @patch("google.cloud.storage.Client")
    def setUp(self, mock_storage_client, _):
        self.mock_storage_client = mock_storage_client
        self.transfer = BigQueryDataTransferGBFS()

    def test_attributes(self):
        self.assertIn("gbfs_schema.json", self.transfer.schema_path)
