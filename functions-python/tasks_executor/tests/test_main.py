# tests/test_tasks_executor_unittest.py

import unittest
from unittest.mock import patch, MagicMock
import flask

from main import get_task, tasks_executor


class TestTasksExecutor(unittest.TestCase):
    def create_mock_request(self, json_data):
        mock_request = MagicMock(spec=flask.Request)
        mock_request.get_json.return_value = json_data
        return mock_request

    def test_get_task_valid(self):
        request = self.create_mock_request(
            {"task": "list_tasks", "payload": {"example": "data"}}
        )
        task, payload = get_task(request)
        self.assertEqual(task, "list_tasks")
        self.assertEqual(payload, {"example": "data"})

    def test_get_task_valid_with_no_payload(self):
        request = self.create_mock_request({"task": "list_tasks"})
        task, payload = get_task(request)
        self.assertEqual(task, "list_tasks")
        self.assertEqual(payload, {})  # Default empty payload

    def test_get_task_invalid_json(self):
        request = self.create_mock_request(None)
        with self.assertRaises(ValueError) as context:
            get_task(request)
        self.assertIn("Invalid JSON", str(context.exception))

    def test_get_task_not_found(self):
        request = self.create_mock_request(
            {
                "task": "YOU_SHOULD_NOT_PASS",
            }
        )
        with self.assertRaises(ValueError) as context:
            get_task(request)
        self.assertIn("Task not supported", str(context.exception))

    def test_get_task_missing_task(self):
        request = self.create_mock_request({"payload": {}})
        with self.assertRaises(ValueError) as context:
            get_task(request)
        self.assertIn("Task not provided", str(context.exception))

    def test_tasks_executor_success(self):
        request = self.create_mock_request({"task": "list_tasks"})
        app = flask.Flask(__name__)
        with app.app_context():
            response = tasks_executor(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("tasks", response.get_json())

    def test_tasks_executor_value_error(self):
        request = self.create_mock_request({})
        app = flask.Flask(__name__)
        with app.app_context():
            response = tasks_executor(request)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], 400)

    @patch(
        "tasks.validation_reports.rebuild_missing_validation_reports.rebuild_missing_validation_reports"
    )
    def test_tasks_executor_handler_exception(self, rebuild_missing_validation_reports):
        rebuild_missing_validation_reports.side_effect = Exception("Boom!")
        request = self.create_mock_request(
            {"task": "rebuild_missing_validation_reports"}
        )
        app = flask.Flask(__name__)
        with app.app_context():
            response = tasks_executor(request)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], 500)
        self.assertIn("Boom!", str(data["error"]))


if __name__ == "__main__":
    unittest.main()
