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
from tasks.dataset_files.rebuild_missing_dataset_files import (
    rebuild_missing_dataset_files_handler,
)
from tasks.missing_bounding_boxes.rebuild_missing_bounding_boxes import (
    rebuild_missing_bounding_boxes_handler,
)
from tasks.refresh_feedsearch_view.refresh_materialized_view import (
    refresh_materialized_view_handler,
)
from tasks.validation_reports.rebuild_missing_validation_reports import (
    rebuild_missing_validation_reports_handler,
)
from tasks.visualization_files.rebuild_missing_visualization_files import (
    rebuild_missing_visualization_files_handler,
)
from tasks.geojson.update_geojson_files_precision import (
    update_geojson_files_precision_handler,
)
from tasks.data_import.import_jbda_feeds import import_jbda_handler

from tasks.licenses.populate_license_rules import (
    populate_license_rules_handler,
)

from tasks.licenses.populate_licenses import (
    populate_licenses_handler,
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
    "rebuild_missing_bounding_boxes": {
        "description": "Rebuilds missing bounding boxes for GTFS datasets that contain valid stops.txt files.",
        "handler": rebuild_missing_bounding_boxes_handler,
    },
    "refresh_materialized_view": {
        "description": "Refreshes the materialized view.",
        "handler": refresh_materialized_view_handler,
    },
    "rebuild_missing_dataset_files": {
        "description": "Rebuilds missing dataset files for GTFS datasets.",
        "handler": rebuild_missing_dataset_files_handler,
    },
    "update_geojson_files": {
        "description": "Iterate over bucket looking for {feed_stable_id}/geolocation.geojson and update precision.",
        "handler": update_geojson_files_precision_handler,
    },
    "rebuild_missing_visualization_files": {
        "description": "Rebuilds missing visualization files for GTFS datasets.",
        "handler": rebuild_missing_visualization_files_handler,
    },
    "jbda_import": {
        "description": "Imports JBDA data into the system.",
        "handler": import_jbda_handler,
    },
    "populate_license_rules": {
        "description": "Populates license rules in the database from a predefined JSON source.",
        "handler": populate_license_rules_handler,
    },
    "populate_licenses": {
        "description": "Populates licenses and license-rules in the database from a predefined JSON source.",
        "handler": populate_licenses_handler,
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
