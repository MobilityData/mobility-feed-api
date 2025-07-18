import logging
import os
from google.cloud import tasks_v2
from datetime import datetime, timedelta
import functions_framework
from google.protobuf import timestamp_pb2
from google.auth.transport.requests import Request
from google.oauth2 import id_token

from shared.helpers.logger import init_logger
from shared.database.database import with_db_session

init_logger()


@functions_framework.http
def refresh_materialized_view_function(request):
    """
    Enqueues a Cloud Task to asynchronously refresh a materialized view.
    Ensures deduplication by generating a unique task name.

    Returns:
        dict: Response message and status code.
    """
    try:
        logging.info("Starting materialized view refresh function.")
        now = datetime.now()

        # BOUNCE WINDOW: next :00 or :30
        minute = now.minute
        if minute < 30:
            bucket_time = now.replace(minute=30, second=0, microsecond=0)
        else:
            bucket_time = now.replace(minute=0, second=0, microsecond=0) + timedelta(
                hours=1
            )

        timestamp_str = bucket_time.strftime("%Y-%m-%d-%H-%M")
        task_name = f"refresh-materialized-view-{timestamp_str}"

        # Cloud Tasks setup
        client = tasks_v2.CloudTasksClient()
        project = os.getenv("PROJECT_ID")
        location = os.getenv("LOCATION")
        queue = os.getenv("QUEUE_NAME")
        url = os.getenv("FUNCTION_URL_REFRESH_MV")

        parent = client.queue_path(project, location, queue)
        task_name = client.task_path(project, location, queue, task_name)

        # Convert to protobuf timestamp
        proto_time = timestamp_pb2.Timestamp()
        proto_time.FromDatetime(bucket_time)

        # Fetch an identity token for the target URL
        auth_req = Request()
        token = id_token.fetch_id_token(auth_req, url)

        task = {
            "name": task_name,
            "http_request": {
                "http_method": tasks_v2.HttpMethod.GET,
                "url": url,
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
            },
            "schedule_time": proto_time,
        }

        # Enqueue the task
        try:
            client.create_task(request={"parent": parent, "task": task})
            logging.info(
                f"Scheduled refresh materialized view task for {timestamp_str}"
            )
            return {"message": f"Refresh task for {timestamp_str} scheduled."}, 200
        except Exception as e:
            if "ALREADY_EXISTS" in str(e):
                logging.info(f"Task already exists for {timestamp_str}, skipping.")
                return {
                    "message": f"Task already exists for {timestamp_str}, skipping."
                }, 200
            else:
                raise

    except Exception as error:
        error_msg = f"Error enqueuing task: {error}"
        logging.error(error_msg)
        return {"error": error_msg}, 500


@with_db_session
def refresh_materialized_view_task(request, db_session):
    """
    Refreshes the materialized view using the CONCURRENTLY command to avoid
    table locks. This function is triggered by a Cloud Task.

    Returns:
        dict: Response message and status code.
    """
    try:
        logging.info("Materialized view refresh task initiated.")

        view_name = "feedsearch"
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
        db_session.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}")
        return True
    except Exception as error:
        logging.error("Error refreshing materialized view " f"{view_name}: {error}")
        return False
