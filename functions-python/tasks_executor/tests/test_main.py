#
#   MobilityData 2025
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import unittest
from unittest.mock import patch, MagicMock
import flask

from main import get_task, tasks_executor


class TestTasksExecutor(unittest.TestCase):
    @staticmethod
    def create_mock_request(json_data, headers=None):
        mock_request = MagicMock(spec=flask.Request)
        mock_request.get_json.return_value = json_data
        mock_request.headers = headers if headers is not None else {}
        return mock_request

    def test_get_task_valid(self):
        request = TestTasksExecutor.create_mock_request(
            {"task": "list_tasks", "payload": {"example": "data"}},
            {"Content-Type": "application/json"},
        )
        task, payload, content_type = get_task(request)
        self.assertEqual(task, "list_tasks")
        self.assertEqual(payload, {"example": "data"})
        self.assertEqual(content_type, "application/json")

    def test_get_task_valid_with_no_payload(self):
        request = TestTasksExecutor.create_mock_request({"task": "list_tasks"})
        task, payload, content_type = get_task(request)
        self.assertEqual(task, "list_tasks")
        self.assertEqual(payload, {})  # Default empty payload
        self.assertEqual(content_type, "application/json")  # Default content type

    def test_get_task_valid_with_content_type(self):
        request = TestTasksExecutor.create_mock_request(
            {"task": "list_tasks"}, {"Content-Type": "text/csv"}
        )
        task, payload, content_type = get_task(request)
        self.assertEqual(task, "list_tasks")
        self.assertEqual(payload, {})  # Default empty payload
        self.assertEqual(content_type, "text/csv")

    def test_get_task_invalid_json(self):
        request = TestTasksExecutor.create_mock_request(None)
        with self.assertRaises(ValueError) as context:
            get_task(request)
        self.assertIn("Invalid JSON", str(context.exception))

    def test_get_task_not_found(self):
        request = TestTasksExecutor.create_mock_request(
            {
                "task": "YOU_SHOULD_NOT_PASS",
            }
        )
        with self.assertRaises(ValueError) as context:
            get_task(request)
        self.assertIn("Task not supported", str(context.exception))

    def test_get_task_missing_task(self):
        request = TestTasksExecutor.create_mock_request({"payload": {}})
        with self.assertRaises(ValueError) as context:
            get_task(request)
        self.assertIn("Task not provided", str(context.exception))

    def test_tasks_executor_success(self):
        request = TestTasksExecutor.create_mock_request({"task": "list_tasks"})
        app = flask.Flask(__name__)
        with app.app_context():
            response = tasks_executor(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("tasks", response.get_json())

    def test_tasks_executor_value_error(self):
        request = TestTasksExecutor.create_mock_request({})
        app = flask.Flask(__name__)
        with app.app_context():
            response = tasks_executor(request)
        self.assertEqual(response.status_code, 400)

    @patch(
        "tasks.validation_reports.rebuild_missing_validation_reports.rebuild_missing_validation_reports"
    )
    def test_tasks_executor_handler_exception(self, rebuild_missing_validation_reports):
        rebuild_missing_validation_reports.side_effect = Exception("Boom!")
        request = TestTasksExecutor.create_mock_request(
            {"task": "rebuild_missing_validation_reports"}
        )
        app = flask.Flask(__name__)
        with app.app_context():
            response = tasks_executor(request)
        self.assertEqual(response.status_code, 500)
        data = response.get_json()
        self.assertIn("Boom!", str(data["error"]))


if __name__ == "__main__":
    unittest.main()
