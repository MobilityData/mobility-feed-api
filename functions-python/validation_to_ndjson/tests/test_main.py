import unittest
from unittest.mock import patch, MagicMock
from cloudevents.http import CloudEvent
from main import (
    convert_reports_to_ndjson,
    batch_convert_reports_to_ndjson,
    parse_resource_data,
)


class TestReportConversionFunctions(unittest.TestCase):
    @patch("main.Logger.init_logger")
    @patch("main.ValidationReportConverter.get_converter")
    @patch("main.parse_resource_data")
    def test_convert_reports_to_ndjson(
        self, mock_parse_resource_data, mock_get_converter, mock_init_logger
    ):
        # Setup mocks
        mock_converter_class = MagicMock()
        mock_converter_instance = MagicMock()
        mock_get_converter.return_value = mock_converter_class
        mock_converter_class.return_value = mock_converter_instance
        mock_parse_resource_data.return_value = (
            "stable_id",
            "dataset_id",
            "report_id",
            "url",
        )

        # Create a mock CloudEvent
        cloud_event_data = {
            "protoPayload": {
                "resourceName": "projects/project_id/buckets/bucket_name/objects/stable_id/dataset_id/report_id.json",
            },
            "resource": {"labels": {"bucket_name": "bucket_name"}},
        }
        cloud_event = CloudEvent(
            data=cloud_event_data, attributes={"source": "test", "type": "test_event"}
        )

        # Call the function
        result = convert_reports_to_ndjson(cloud_event)

        # Assertions
        mock_init_logger.assert_called_once()
        mock_parse_resource_data.assert_called_once_with(cloud_event.data)
        mock_get_converter.assert_called_once()
        mock_converter_class.assert_called_once_with(
            "stable_id", "dataset_id", "report_id", "url"
        )
        mock_converter_instance.process.assert_called_once()
        self.assertEqual(result, ("stable_id", "dataset_id", "url"))

    @patch("main.Logger.init_logger")
    @patch("main.storage.Client")
    @patch("main.convert_reports_to_ndjson")
    def test_batch_convert_reports_to_ndjson(
        self, mock_convert_reports_to_ndjson, mock_storage_client, mock_init_logger
    ):
        # Setup mocks
        mock_blob1 = MagicMock()
        mock_blob1.name = "stable_id/dataset_id/report_1.json"

        mock_blob2 = MagicMock()
        mock_blob2.name = "stable_id/dataset_id/report_2.json"

        mock_storage_client().list_blobs.return_value = [mock_blob1, mock_blob2]

        # Call the function
        result = batch_convert_reports_to_ndjson(None)

        # Assertions
        mock_init_logger.assert_called_once()
        mock_storage_client().list_blobs.assert_called_once()
        self.assertEqual(mock_convert_reports_to_ndjson.call_count, 2)
        self.assertEqual(result, "Success converting reports to NDJSON")

    def test_parse_resource_data(self):
        # Test data
        cloud_event_data = {
            "protoPayload": {
                "resourceName": "projects/project_id/buckets/bucket_name/objects/stable_id/dataset_id/report_id.json",
            },
            "resource": {"labels": {"bucket_name": "bucket_name"}},
        }

        # Call the function
        result = parse_resource_data(cloud_event_data)

        # Assertions
        self.assertEqual(
            result,
            (
                "stable_id",
                "dataset_id",
                "report_id",
                "https://storage.googleapis.com/bucket_name/stable_id/dataset_id/report_id.json",
            ),
        )
