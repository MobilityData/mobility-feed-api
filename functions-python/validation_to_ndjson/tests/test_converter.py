import json
import unittest
from unittest.mock import patch, MagicMock
from validation_to_ndjson.src.validation_report_converter import (
    ValidationReportConverter,
    GTFSValidationReportConverter,
    GBFSValidationReportConverter,
)


class TestValidationReportConverter(unittest.TestCase):
    @patch("requests.get")
    @patch("validation_to_ndjson.src.validation_report_converter.get_feed_location")
    @patch("validation_to_ndjson.src.validation_report_converter.load_json_schema")
    def setUp(self, mock_load_json_schema, mock_get_feed_location, mock_requests_get):
        # Mock the JSON schema loading
        mock_json_schema = {
            "fields": [
                {"name": "feedId", "type": "STRING"},
                {"name": "datasetId", "type": "STRING"},
                {"name": "validatedAt", "type": "STRING"},
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
                {
                    "name": "notices",
                    "type": "RECORD",
                    "mode": "REPEATED",
                    "fields": [{"name": "sampleNotices", "type": "STRING"}],
                },
            ]
        }
        mock_load_json_schema.return_value = mock_json_schema

        # Mock the locations
        mock_get_feed_location.return_value = [
            MagicMock(
                country="Country1",
                country_code="C1",
                subdivision_name="Subdivision1",
                municipality="City1",
            )
        ]

        # Mock the HTTP response for the validation report
        mock_validation_report = {
            "summary": {"validatedAt": "2024-01-01T00:00:00Z"},
            "notices": [{"sampleNotices": [{"id": 1}, {"id": 2}]}],
        }
        mock_requests_get.return_value.json.return_value = mock_validation_report

        self.gtfs_converter = GTFSValidationReportConverter(
            stable_id="feed1",
            dataset_id="123",
            report_id="report1",
            validation_report_url="http://example.com/report.json",
        )
        self.gbfs_converter = GBFSValidationReportConverter(
            stable_id="feed2",
            dataset_id="456",
            report_id="report2",
            validation_report_url="http://example.com/report.json",
        )

    @patch("validation_to_ndjson.src.validation_report_converter.filter_json_by_schema")
    @patch("validation_to_ndjson.src.validation_report_converter.storage.Client")
    def test_process_gtfs_report(self, mock_storage_client, mock_filter_json_by_schema):
        mock_filter_json_by_schema.return_value = {
            "feedId": "feed1",
            "datasetId": "123",
            "validatedAt": "2024-01-01T00:00:00Z",
            "locations": [
                {
                    "country": "Country1",
                    "countryCode": "C1",
                    "subdivisionName": "Subdivision1",
                    "municipality": "City1",
                }
            ],
            "notices": [{"sampleNotices": '[{"id":1},{"id":2}]'}],
        }
        mock_bucket = MagicMock()
        mock_storage_client().get_bucket.return_value = mock_bucket

        self.gtfs_converter.process()

        ndjson_blob_name = "ndjson/feed1/123/report1.ndjson"
        expected_ndjson_content = (
            json.dumps(mock_filter_json_by_schema.return_value, separators=(",", ":"))
            + "\n"
        )
        mock_bucket.blob.assert_called_once_with(ndjson_blob_name)
        mock_bucket.blob().upload_from_string.assert_called_once_with(
            expected_ndjson_content
        )

    @patch("validation_to_ndjson.src.validation_report_converter.filter_json_by_schema")
    @patch("validation_to_ndjson.src.validation_report_converter.storage.Client")
    def test_process_gbfs_report(self, mock_storage_client, mock_filter_json_by_schema):
        mock_filter_json_by_schema.return_value = {
            "feedId": "feed2",
            "snapshotId": "456",
            "locations": [
                {
                    "country": "Country1",
                    "countryCode": "C1",
                    "subdivisionName": "Subdivision1",
                    "municipality": "City1",
                }
            ],
            "notices": [{"sampleNotices": '[{"id":1},{"id":2}]'}],
        }
        mock_bucket = MagicMock()
        mock_storage_client().get_bucket.return_value = mock_bucket

        self.gbfs_converter.process()

        ndjson_blob_name = "ndjson/feed2/456/report2.ndjson"
        expected_ndjson_content = (
            json.dumps(mock_filter_json_by_schema.return_value, separators=(",", ":"))
            + "\n"
        )
        mock_bucket.blob.assert_called_once_with(ndjson_blob_name)
        mock_bucket.blob().upload_from_string.assert_called_once_with(
            expected_ndjson_content
        )

    def test_get_converter(self):
        gtfs_type_converter = ValidationReportConverter.get_converter("gtfs")
        self.assertEqual(gtfs_type_converter, GTFSValidationReportConverter)
        gbfs_type_converter = ValidationReportConverter.get_converter("gbfs")
        self.assertEqual(gbfs_type_converter, GBFSValidationReportConverter)
        with self.assertRaises(ValueError):
            ValidationReportConverter.get_converter("invalid_type")
