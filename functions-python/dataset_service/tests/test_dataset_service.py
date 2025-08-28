import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

from dataset_service_commons import DatasetTrace, Status, BatchExecution
from main import DatasetTraceService, BatchExecutionService


class TestDatasetService(unittest.TestCase):
    @patch("google.cloud.datastore.Client")
    def test_save_dataset_trace(self, mock_datastore_client):
        service = DatasetTraceService(mock_datastore_client)
        dataset_trace = DatasetTrace(
            stable_id="123", status=Status.PUBLISHED, timestamp=datetime.now()
        )
        service.save(dataset_trace)
        mock_datastore_client.put.assert_called_once()

    @patch("google.cloud.datastore.Client")
    def test_validate_and_save_exception(self, mock_datastore_client):
        service = DatasetTraceService(mock_datastore_client)
        dataset_trace = DatasetTrace(
            stable_id="123", status=Status.PUBLISHED, timestamp=datetime.now()
        )
        with self.assertRaises(ValueError):
            service.validate_and_save(dataset_trace, 1)

    @patch("google.cloud.datastore.Client")
    def test_validate_and_save(self, mock_datastore_client):
        service = DatasetTraceService(mock_datastore_client)
        dataset_trace = DatasetTrace(
            stable_id="123",
            execution_id="123",
            status=Status.PUBLISHED,
            timestamp=datetime.now(),
        )
        service.validate_and_save(dataset_trace, 1)
        mock_datastore_client.put.assert_called_once()

    @patch("google.cloud.datastore.Client")
    def test_get_dataset_trace_by_id(self, mock_datastore_client):
        mock_datastore_client.get.return_value = {
            "trace_id": "123",
            "stable_id": "123",
            "status": "PUBLISHED",
            "timestamp": datetime.now(),
        }
        service = DatasetTraceService(mock_datastore_client)
        trace = service.get_by_id("123")
        self.assertEqual(trace.stable_id, "123")

    @patch("google.cloud.datastore.Client")
    def test_get_dataset_trace_by_id_not_exist(self, mock_datastore_client):
        mock_datastore_client.get.return_value = None
        service = DatasetTraceService(mock_datastore_client)
        trace = service.get_by_id("non existent trace")
        self.assertListEqual(trace, [])

    @patch("google.cloud.datastore.Client")
    def test_save_batch_execution(self, mock_datastore_client):
        mock_datastore_client.return_value.key = MagicMock()
        mock_datastore_client.return_value.Entity = MagicMock()
        service = BatchExecutionService()
        service.client = mock_datastore_client
        execution = BatchExecution(
            execution_id="123", timestamp=datetime.now(), feeds_total=10
        )
        service.save(execution)
        mock_datastore_client.key.assert_called_once_with("batch_execution", "123")

    @patch("google.cloud.datastore.Client")
    @patch("main.DatasetTraceService._entity_to_dataset_trace")
    def test_get_by_execution_and_stable_ids(
        self, mock_entity_to_dataset_trace, mock_datastore_client
    ):
        mock_query = MagicMock()
        mock_datastore_client.query.return_value = mock_query

        mock_entity = MagicMock(
            spec=dict,
            **{
                "get.side_effect": lambda key: {
                    "trace_id": "123",
                    "stable_id": "stable_123",
                    "status": "PUBLISHED",
                    "timestamp": datetime.now(),
                }.get(key, None)
            }
        )
        mock_query.fetch.return_value = [mock_entity]
        mock_entity_to_dataset_trace.side_effect = lambda entity: DatasetTrace(
            stable_id=entity.get("stable_id"),
            status=Status(entity.get("status")),
            timestamp=entity.get("timestamp"),
            trace_id=entity.get("trace_id"),
        )
        service = DatasetTraceService(client=mock_datastore_client)

        results = service.get_by_execution_and_stable_ids("exec_id", "stable_123")

        mock_datastore_client.query.assert_called_once_with(kind="dataset_trace")
        mock_query.add_filter.assert_any_call("execution_id", "=", "exec_id")
        mock_query.add_filter.assert_any_call("stable_id", "=", "stable_123")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].stable_id, "stable_123")
