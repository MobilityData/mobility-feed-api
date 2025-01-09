import unittest
from unittest.mock import patch, mock_open
from google.cloud import bigquery

from bq_schema.schema import (
    filter_json_by_schema,
    load_json_schema,
    json_schema_to_bigquery,
)


class TestSchema(unittest.TestCase):
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
