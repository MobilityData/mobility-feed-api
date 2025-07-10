import logging
import os
import functions_framework
from flask import Request, jsonify
from google.cloud import tasks_v2
from datetime import datetime
from shared.helpers.logger import init_logger
from shared.database.database import with_db_session

init_logger()


@functions_framework.http
def refresh_materialized_view_function(request: Request):
    """
    Enqueues a Cloud Task to refresh a materialized view asynchronously.

    Returns:
        tuple: (response_message, status_code)
    """
    try:
        logging.info("Starting materialized view refresh function.")

        # Generate deduplication key based on current timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
        task_name = f"refresh-feed-search-{timestamp}"

        # Cloud Tasks client setup
        client = tasks_v2.CloudTasksClient()
        project_id = os.getenv("PROJECT_ID")
        queue = os.getenv("QUEUE_NAME")
        location = os.getenv("LOCATION")
        url = os.getenv("FUNCTION_URL")

        parent = client.queue_path(project_id, location, queue)

        # Task payload
        payload = {"view_name": "feedsearch"}

        task = {
            "name": client.task_path(project_id, location, queue, task_name),
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {"Content-Type": "application/json"},
                "body": jsonify(payload).data,
            },
        }

        # Enqueue the task
        response = client.create_task(request={"parent": parent, "task": task})
        logging.info(f"Task {response.name} enqueued successfully.")

        return {"message": f"Task {response.name} enqueued successfully."}, 200

    except Exception as error:
        error_msg = f"Error enqueuing task: {error}"
        logging.error(error_msg)
        return {"error": error_msg}, 500


@with_db_session
@functions_framework.http
def refresh_materialized_view_task(request: Request, db_session):
    """
    Refreshes a materialized view using the CONCURRENTLY command to avoid
    table locks. This function is triggered by a Cloud Task.

    Returns:
        tuple: (response_message, status_code)
    """
    try:
        logging.info("Starting materialized view refresh task.")

        data = request.get_json()
        view_name = data.get("view_name")
        deduplication_key = data.get("deduplication_key")

        logging.info(
            "Refreshing materialized view: "
            f"{view_name} with key: {deduplication_key}"
        )

        # Call the refresh function
        success = refresh_materialized_view(db_session, view_name)

        if success:
            success_msg = "Successfully refreshed materialized view: " f"{view_name}"
            logging.info(success_msg)
            return {"message": success_msg}, 200
        else:
            error_msg = f"Failed to refresh materialized view: {view_name}"
            logging.error(error_msg)
            return {"error": error_msg}, 500

    except Exception as error:
        error_msg = f"Error refreshing materialized view: {error}"
        logging.error(error_msg)
        return {"error": error_msg}, 500


def refresh_materialized_view(db_session, view_name):
    """
    Refreshes the materialized view in the database.

    Args:
        db_session: Database session object.
        view_name (str): Name of the materialized view to refresh.

    Returns:
        bool: True if refresh was successful, False otherwise.
    """
    try:
        db_session.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name};")
        db_session.commit()
        return True
    except Exception as error:
        logging.error("Error refreshing materialized view " f"{view_name}: {error}")
        return False
