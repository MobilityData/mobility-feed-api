import unittest
from unittest.mock import patch, MagicMock

from faker import Faker

faker = Faker()


class TestReverseGeolocation(unittest.TestCase):
    @patch("reverse_geolocation.Logger")
    def test_init(self, mock_logger):
        from reverse_geolocation import init

        init(MagicMock())
        mock_logger.init_logger.assert_called_once()

    def test_parse_resource_data(self):
        from reverse_geolocation import parse_resource_data

        dataset_id = "test_dataset_id"
        stable_id = "test_stable_id"
        data = {
            "protoPayload": {
                "resourceName": f"{stable_id}/{dataset_id}/{dataset_id}.zip"
            },
            "resource": {"labels": {"bucket_name": "test_bucket"}},
        }
        stable_id_result, dataset_id_result, url_result = parse_resource_data(data)
        self.assertEqual(stable_id_result, stable_id)
        self.assertEqual(dataset_id_result, dataset_id)
        self.assertEqual(
            url_result,
            f"https://storage.googleapis.com/test_bucket/{stable_id}/{dataset_id}/"
            f"{dataset_id}.zip",
        )

    @patch("reverse_geolocation.init")
    @patch("reverse_geolocation.jsonify_pubsub")
    @patch("reverse_geolocation.reverse_geolocation")
    def test_reverse_geolocation_pubsub_success(
        self, reverse_geolocation_mock, jsonify_pubsub_mock, _
    ):
        request = MagicMock()
        jsonify_pubsub_mock.return_value = {
            "stable_id": "test_stable_id",
            "dataset_id": "test_dataset_id",
            "url": "test_url",
        }
        from reverse_geolocation import reverse_geolocation_pubsub

        reverse_geolocation_pubsub(request)
        reverse_geolocation_mock.assert_called_once_with(
            "test_stable_id", "test_dataset_id", "test_url"
        )

    @patch("reverse_geolocation.init")
    @patch("reverse_geolocation.jsonify_pubsub")
    @patch("reverse_geolocation.reverse_geolocation")
    def test_reverse_geolocation_pubsub_fail(
        self, reverse_geolocation_mock, jsonify_pubsub_mock, _
    ):
        request = MagicMock()
        jsonify_pubsub_mock.return_value = {}
        from reverse_geolocation import reverse_geolocation_pubsub

        reverse_geolocation_pubsub(request)
        reverse_geolocation_mock.assert_not_called()
        jsonify_pubsub_mock.return_value = None
        reverse_geolocation_pubsub(request)
        reverse_geolocation_mock.assert_not_called()

    @patch("reverse_geolocation.init")
    @patch("reverse_geolocation.parse_resource_data")
    @patch("reverse_geolocation.reverse_geolocation")
    def test_reverse_geolocation_storage_trigger_fail(
        self, reverse_geolocation_mock, __, _
    ):
        request = MagicMock()
        from reverse_geolocation import reverse_geolocation_storage_trigger

        reverse_geolocation_storage_trigger(request)
        reverse_geolocation_mock.assert_not_called()

    @patch("reverse_geolocation.init")
    @patch("reverse_geolocation.parse_resource_data")
    @patch("reverse_geolocation.reverse_geolocation")
    def test_reverse_geolocation_storage_trigger_success(
        self, reverse_geolocation_mock, parse_resource_data_mock, _
    ):
        request = MagicMock()
        parse_resource_data_mock.return_value = (
            "test_stable_id",
            "test_dataset_id",
            "test_url",
        )
        from reverse_geolocation import reverse_geolocation_storage_trigger

        reverse_geolocation_storage_trigger(request)
        reverse_geolocation_mock.assert_called_once()

    @patch("reverse_geolocation.gtfs_kit", autospec=True)
    @patch("reverse_geolocation.storage", autospec=True)
    @patch("reverse_geolocation.tasks_v2")
    @patch("reverse_geolocation.create_http_task")
    def test_reverse_geolocation(self, create_http_task, _, cloud_storage, __):
        from reverse_geolocation import reverse_geolocation

        cloud_storage.Client.return_value.bucket.return_value.blob.return_value = (
            MagicMock(public_url="test_public_url")
        )
        reverse_geolocation("test_stable_id", "test_dataset_id", "test_url")
        create_http_task.assert_called_once()
