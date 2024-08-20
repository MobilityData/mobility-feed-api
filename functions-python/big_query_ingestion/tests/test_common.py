import unittest
from unittest.mock import mock_open
from unittest.mock import patch, MagicMock

from google.cloud import bigquery

from big_query_ingestion.src.common.bg_schema import (
    json_schema_to_bigquery,
    filter_json_by_schema,
    load_json_schema,
)
from big_query_ingestion.src.common.bq_data_transfer import BigQueryDataTransfer
from big_query_ingestion.src.common.feeds_locations import get_feeds_locations_map


class TestFeedsLocations(unittest.TestCase):
    @patch("big_query_ingestion.src.common.feeds_locations.start_db_session")
    @patch("big_query_ingestion.src.common.feeds_locations.os.getenv")
    @patch("big_query_ingestion.src.common.feeds_locations.joinedload")
    def test_get_feeds_locations_map(self, _, mock_getenv, mock_start_db_session):
        mock_getenv.return_value = "fake_database_url"

        mock_session = MagicMock()
        mock_start_db_session.return_value = mock_session

        mock_feed = MagicMock()
        mock_feed.stable_id = "feed1"
        mock_location1 = MagicMock()
        mock_location2 = MagicMock()
        mock_feed.locations = [mock_location1, mock_location2]

        mock_query = MagicMock()
        mock_query.filter.return_value.options.return_value.all.return_value = [
            mock_feed
        ]

        mock_session.query.return_value = mock_query
        result = get_feeds_locations_map("gtfs")

        mock_start_db_session.assert_called_once_with("fake_database_url")
        mock_session.query.assert_called_once()  # Verify that query was called
        mock_query.filter.assert_called_once()  # Verify that filter was applied
        mock_query.filter.return_value.options.assert_called_once()
        mock_query.filter.return_value.options.return_value.all.assert_called_once()  # Verify that all() was called

        self.assertIn("feed1", result)  # Check if the key exists in the result
        self.assertEqual(
            result["feed1"], [mock_location1, mock_location2]
        )  # Verify the mapping

    @patch("big_query_ingestion.src.common.feeds_locations.start_db_session")
    def test_get_feeds_locations_map_no_feeds(self, mock_start_db_session):
        mock_session = MagicMock()
        mock_start_db_session.return_value = mock_session

        mock_query = MagicMock()
        mock_query.filter.return_value.options.return_value.all.return_value = []

        mock_session.query.return_value = mock_query

        result = get_feeds_locations_map("test_data_type")

        mock_start_db_session.assert_called_once()
        self.assertEqual(result, {})  # The result should be an empty dictionary


class TestBigQueryDataTransfer(unittest.TestCase):
    @patch("google.cloud.storage.Client")
    @patch("big_query_ingestion.src.common.bq_data_transfer.bigquery.Client")
    def setUp(self, mock_bq_client, mock_storage_client):
        self.transfer = BigQueryDataTransfer()
        self.transfer.schema_path = "fake_schema_path.json"
        self.mock_bq_client = mock_bq_client
        self.mock_storage_client = mock_storage_client

    @patch("big_query_ingestion.src.common.bq_data_transfer.bigquery.DatasetReference")
    def test_create_bigquery_dataset_exists(self, _):
        self.mock_bq_client().get_dataset.return_value = True
        self.transfer.create_bigquery_dataset()

        self.mock_bq_client().get_dataset.assert_called_once()
        self.mock_bq_client().create_dataset.assert_not_called()

    @patch("big_query_ingestion.src.common.bq_data_transfer.bigquery.DatasetReference")
    def test_create_bigquery_dataset_not_exists(self, _):
        self.mock_bq_client().get_dataset.side_effect = Exception("Dataset not found")

        self.transfer.create_bigquery_dataset()

        self.mock_bq_client().get_dataset.assert_called_once()
        self.mock_bq_client().create_dataset.assert_called_once()

    @patch("big_query_ingestion.src.common.bq_data_transfer.load_json_schema")
    @patch("big_query_ingestion.src.common.bq_data_transfer.json_schema_to_bigquery")
    @patch("big_query_ingestion.src.common.bq_data_transfer.bigquery.DatasetReference")
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

    @patch("big_query_ingestion.src.common.bq_data_transfer.bigquery.DatasetReference")
    def test_create_bigquery_table_exists(self, _):
        self.mock_bq_client().get_table.return_value = True

        self.transfer.create_bigquery_table()

        self.mock_bq_client().get_table.assert_called_once()
        self.mock_bq_client().create_table.assert_not_called()

    @patch("big_query_ingestion.src.common.bq_data_transfer.bigquery.DatasetReference")
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

    @patch("big_query_ingestion.src.common.bq_data_transfer.bigquery.DatasetReference")
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

    @patch(
        "big_query_ingestion.src.common.bq_data_transfer.BigQueryDataTransfer.create_bigquery_dataset"
    )
    @patch(
        "big_query_ingestion.src.common.bq_data_transfer.BigQueryDataTransfer.create_bigquery_table"
    )
    @patch(
        "big_query_ingestion.src.common.bq_data_transfer.BigQueryDataTransfer.load_data_to_bigquery"
    )
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
        "big_query_ingestion.src.common.bq_data_transfer.BigQueryDataTransfer.create_bigquery_dataset",
        side_effect=Exception("Dataset creation failed"),
    )
    def test_send_data_to_bigquery_failure(self, mock_create_dataset):
        response, status = self.transfer.send_data_to_bigquery()

        mock_create_dataset.assert_called_once()
        self.assertEqual(status, 500)
        self.assertIn("Error while loading data: Dataset creation failed", response)


class TestBgSchema(unittest.TestCase):
    def test_json_schema_to_bigquery(self):
        json_schema = {
            "fields": [
                {"name": "name", "type": "STRING"},
                {"name": "age", "type": "INTEGER"},
                {"name": "is_student", "type": "BOOLEAN"},
                {
                    "name": "address",
                    "type": "RECORD",
                    "fields": [
                        {"name": "street", "type": "STRING"},
                        {"name": "city", "type": "STRING"},
                    ],
                },
            ]
        }
        expected_schema = [
            bigquery.SchemaField("name", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("age", "INTEGER", mode="NULLABLE"),
            bigquery.SchemaField("is_student", "BOOLEAN", mode="NULLABLE"),
            bigquery.SchemaField(
                "address",
                "RECORD",
                mode="NULLABLE",
                fields=[
                    bigquery.SchemaField("street", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("city", "STRING", mode="NULLABLE"),
                ],
            ),
        ]
        result = json_schema_to_bigquery(json_schema)
        self.assertEqual(result, expected_schema)

    def test_filter_json_by_schema(self):
        json_schema = {
            "fields": [
                {"name": "name", "type": "STRING"},
                {"name": "age", "type": "INTEGER"},
                {
                    "name": "address",
                    "type": "RECORD",
                    "fields": [
                        {"name": "street", "type": "STRING"},
                        {"name": "city", "type": "STRING"},
                    ],
                },
            ]
        }
        input_json = {
            "name": "John Doe",
            "age": 30,
            "address": {"street": "123 Main St", "city": "Anytown"},
            "extra_field": "should be ignored",
        }
        expected_json = {
            "name": "John Doe",
            "age": 30,
            "address": {"street": "123 Main St", "city": "Anytown"},
        }
        result = filter_json_by_schema(json_schema, input_json)
        self.assertEqual(result, expected_json)

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"fields": [{"name": "field1", "type": "STRING"}]}',
    )
    def test_load_json_schema(self, mock_file):
        json_schema_path = "fake_path.json"
        result = load_json_schema(json_schema_path)
        expected_result = {"fields": [{"name": "field1", "type": "STRING"}]}
        mock_file.assert_called_once_with(json_schema_path, "r")
        self.assertEqual(result, expected_result)
