from typing import Any, Final

import flask
import functions_framework

from tasks.validation_reports.rebuild_missing_validation_reports import (
    rebuild_missing_validation_reports_handler,
)

LIST_COMMAND: Final[str] = "list"
tasks = {
    "list_tasks": {
        "description": "List all available tasks.",
        "handler": lambda payload: flask.jsonify(
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
        raise ValueError("Invalid JSON payload")
    if not request_json.get("task"):
        raise ValueError("Task not provided")
    task = request_json.get("task")
    if task not in tasks:
        raise ValueError("Task not supported")
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
        return flask.jsonify({"error": str(error), "status": 400})
    # Execute task
    handler = tasks[task]["handler"]
    try:
        return handler(payload=payload)
    except Exception as error:
        return flask.jsonify({"error": str(error), "status": 500})
