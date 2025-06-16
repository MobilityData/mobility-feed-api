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

from typing import Any, Final

import flask
import functions_framework
from shared.helpers.logger import init_logger
from tasks.validation_reports.rebuild_missing_validation_reports import (
    rebuild_missing_validation_reports_handler,
)


init_logger()
LIST_COMMAND: Final[str] = "list"
tasks = {
    "list_tasks": {
        "description": "List all available tasks.",
        "handler": lambda payload: (
            {
                "tasks": [
                    {"name": task_name, "description": task_info["description"]}
                    for task_name, task_info in tasks.items()
                ]
            }
        ),
    },
    "rebuild_missing_validation_reports": {
        "description": "Rebuilds missing validation reports for GTFS datasets.",
        "handler": rebuild_missing_validation_reports_handler,
    },
    "identify_missing_bounding_boxes": {
        "description": "Rebuilds missing bounding boxes for GTFS datasets that contain valid stops.txt files.",
        "handler": identify_missing_bounding_boxes_handler,
    },
}


def get_task(request: flask.Request):
    """Verify if the task is valid and has a handler.
    Args:
        request (flask.Request): The incoming request.
    Returns:
        str: The task name.
    Raises:
        ValueError: If the task is invalid or has no handler.
    """
    request_json = request.get_json(silent=True)
    if not request_json:
        raise ValueError("Invalid JSON request")
    if not request_json.get("task"):
        raise ValueError("Task not provided")
    task = request_json.get("task")
    if task not in tasks:
        raise ValueError("Task not supported: %s", task)
    payload = request_json.get("payload")
    if not payload:
        payload = {}
    return task, payload


@functions_framework.http
def tasks_executor(request: flask.Request) -> flask.Response:
    task: Any
    payload: Any
    try:
        task, payload = get_task(request)
    except ValueError as error:
        return flask.make_response(flask.jsonify({"error": str(error)}), 400)
    # Execute task
    handler = tasks[task]["handler"]
    try:
        return flask.make_response(flask.jsonify(handler(payload=payload)), 200)
    except Exception as error:
        return flask.make_response(flask.jsonify({"error": str(error)}), 500)
