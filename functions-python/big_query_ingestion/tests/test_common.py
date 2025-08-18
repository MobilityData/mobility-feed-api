import unittest
from unittest.mock import patch, MagicMock

from google.cloud import bigquery

from common.bq_data_transfer import BigQueryDataTransfer


class TestBigQueryDataTransfer(unittest.TestCase):
    @patch("google.cloud.storage.Client")
    @patch("common.bq_data_transfer.bigquery.Client")
    def setUp(self, mock_bq_client, mock_storage_client):
        self.transfer = BigQueryDataTransfer()
        self.transfer.schema_path = "fake_schema_path.json"
        self.mock_bq_client = mock_bq_client
        self.mock_storage_client = mock_storage_client

    @patch("common.bq_data_transfer.bigquery.DatasetReference")
    def test_create_bigquery_dataset_exists(self, _):
        self.mock_bq_client().get_dataset.return_value = True
        self.transfer.create_bigquery_dataset()

        self.mock_bq_client().get_dataset.assert_called_once()
        self.mock_bq_client().create_dataset_entities.assert_not_called()

    @patch("common.bq_data_transfer.bigquery.DatasetReference")
    def test_create_bigquery_dataset_not_exists(self, _):
        self.mock_bq_client().get_dataset.side_effect = Exception("Dataset not found")

        self.transfer.create_bigquery_dataset()

        self.mock_bq_client().get_dataset.assert_called_once()
        self.mock_bq_client().create_dataset_entities.assert_called_once()

    @patch("common.bq_data_transfer.load_json_schema")
    @patch("common.bq_data_transfer.json_schema_to_bigquery")
    @patch("common.bq_data_transfer.bigquery.DatasetReference")
    def test_create_bigquery_table_not_exists(
        self, _, mock_json_schema_to_bigquery, mock_load_json_schema
    ):
        self.mock_bq_client().get_table.side_effect = Exception("Table not found")
        mock_load_json_schema.return_value = {
            "fields": [{"name": "field1", "type": "STRING"}]
        }
        mock_json_schema_to_bigquery.return_value = [
            bigquery.SchemaField("field1", "STRING", mode="NULLABLE")
        ]

        self.transfer.create_bigquery_table()

        self.mock_bq_client().get_table.assert_called_once()
        mock_load_json_schema.assert_called_once_with(self.transfer.schema_path)
        mock_json_schema_to_bigquery.assert_called_once()
        self.mock_bq_client().create_table.assert_called_once()

    @patch("common.bq_data_transfer.bigquery.DatasetReference")
    def test_create_bigquery_table_exists(self, _):
        self.mock_bq_client().get_table.return_value = True

        self.transfer.create_bigquery_table()

        self.mock_bq_client().get_table.assert_called_once()
        self.mock_bq_client().create_table.assert_not_called()

    @patch("common.bq_data_transfer.bigquery.DatasetReference")
    def test_load_data_to_bigquery(self, _):
        mock_blob = MagicMock()
        mock_blob.name = "file1.ndjson"
        self.mock_storage_client().list_blobs.return_value = [mock_blob]

        mock_load_job = MagicMock()
        self.mock_bq_client().load_table_from_uri.return_value = mock_load_job

        self.transfer.load_data_to_bigquery()

        self.mock_storage_client().list_blobs.assert_called_once()
        self.mock_bq_client().load_table_from_uri.assert_called_once()
        mock_load_job.result.assert_called_once()

    @patch("common.bq_data_transfer.bigquery.DatasetReference")
    def test_load_data_to_bigquery_error(self, _):
        mock_blob = MagicMock()
        mock_blob.name = "file1.ndjson"
        self.mock_storage_client().list_blobs.return_value = [mock_blob]

        mock_load_job = MagicMock()
        mock_load_job.result.side_effect = Exception("Load job failed")
        self.mock_bq_client().load_table_from_uri.return_value = mock_load_job

        with self.assertLogs(level="ERROR") as log:
            self.transfer.load_data_to_bigquery()

        self.assertIn(
            "An error occurred while loading data to BigQuery: Load job failed",
            log.output[0],
        )

    @patch("common.bq_data_transfer.BigQueryDataTransfer.create_bigquery_dataset")
    @patch("common.bq_data_transfer.BigQueryDataTransfer.create_bigquery_table")
    @patch("common.bq_data_transfer.BigQueryDataTransfer.load_data_to_bigquery")
    def test_send_data_to_bigquery_success(
        self, mock_load_data, mock_create_table, mock_create_dataset
    ):
        response, status = self.transfer.send_data_to_bigquery()

        mock_create_dataset.assert_called_once()
        mock_create_table.assert_called_once()
        mock_load_data.assert_called_once()
        self.assertEqual(status, 200)
        self.assertEqual(response, "Data successfully loaded to BigQuery")

    @patch(
        "common.bq_data_transfer.BigQueryDataTransfer.create_bigquery_dataset",
        side_effect=Exception("Dataset creation failed"),
    )
    def test_send_data_to_bigquery_failure(self, mock_create_dataset):
        response, status = self.transfer.send_data_to_bigquery()

        mock_create_dataset.assert_called_once()
        self.assertEqual(status, 500)
        self.assertIn("Error while loading data: Dataset creation failed", response)
