import logging
import os
from google.cloud import tasks_v2
from google.protobuf.timestamp_pb2 import Timestamp


def create_refresh_materialized_view_task():
    """
    Asynchronously refresh a materialized view.
    Ensures deduplication by generating a unique task name.

    Returns:
        dict: Response message and status code.
    """
    from google.protobuf import timestamp_pb2
    from datetime import datetime, timedelta

    try:
        logging.info("Creating materialized view refresh task.")
        now = datetime.now()

        # BOUNCE WINDOW: next :00 or :30
        minute = now.minute
        if minute < 30:
            bucket_time = now.replace(minute=30, second=0, microsecond=0)
        else:
            bucket_time = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

        timestamp_str = bucket_time.strftime("%Y-%m-%d-%H-%M")
        task_name = f"refresh-materialized-view-{timestamp_str}"

        # Convert to protobuf timestamp
        proto_time = timestamp_pb2.Timestamp()
        proto_time.FromDatetime(bucket_time)

        # Cloud Tasks setup

        project = os.getenv("PROJECT_ID")
        logging.info(f"!@##$%^^^^!@Loaded PROJECT_ID: {project}")
        location = os.getenv("LOCATION")
        logging.info(f"!@##$%^^^^!@Loaded LOCATION: {location}")
        queue = os.getenv("MATERIALIZED_VIEW_QUEUE")
        logging.info(f"!@##$%^^^^!@Loaded MATERIALIZED_VIEW_QUEUE: {queue}")
        gcp_region = os.getenv("GCP_REGION")
        logging.info(f"!@##$%^^^^!@Loaded GCP_REGION: {gcp_region}")
        environment_name = os.getenv("ENVIRONMENT_NAME")
        logging.info(f"!@##$%^^^^!@Loaded ENVIRONMENT_NAME: {environment_name}")
        service_account_email = os.getenv("SERVICE_ACCOUNT_EMAIL")
        logging.info(f"!@##$%^^^^!@Loaded SERVICE_ACCOUNT_EMAIL: {service_account_email}")
        url = f"https://{gcp_region}-" f"{project}.cloudfunctions.net/" f"tasks-executor-{environment_name}"
        logging.info(f"!@##$%^^^^!@Constructed Cloud Task URL: {url}")

        # Create the Cloud Tasks client only before enqueuing the task
        try:
            logging.info("!@##$%^^^^!@Creating Cloud Tasks client.")
            client = tasks_v2.CloudTasksClient()
        except Exception as e:
            error_msg = f"!@##$%^^^^!@Error creating Cloud Tasks client: {e}"
            logging.error(error_msg)
            return {"error": error_msg}, 500

        # Enqueue the task
        try:
            create_http_task_with_name(
                client=client,
                body=b"",
                url=url,
                project_id=project,
                gcp_region=location,
                queue_name=queue,
                task_name=task_name,
                task_time=proto_time,
                http_method=tasks_v2.HttpMethod.GET,
            )
            logging.info(f"Scheduled refresh materialized view task for {timestamp_str}")
            return {"message": f"Refresh task for {timestamp_str} scheduled."}, 200
        except Exception as e:
            if "ALREADY_EXISTS" in str(e):
                logging.info(f"Task already exists for {timestamp_str}, skipping.")

    except Exception as error:
        error_msg = f"Error enqueuing task: {error}"
        logging.error(error_msg)
        return {"error": error_msg}, 500


def create_http_task_with_name(
    client: "tasks_v2.CloudTasksClient",
    body: bytes,
    url: str,
    project_id: str,
    gcp_region: str,
    queue_name: str,
    task_name: str,
    task_time: Timestamp,
    http_method: "tasks_v2.HttpMethod",
):
    """Creates a GCP Cloud Task."""

    token = tasks_v2.OidcToken(service_account_email=os.getenv("SERVICE_ACCOUNT_EMAIL"))

    # Build the full task path for the name field
    full_task_path = tasks_v2.CloudTasksClient.task_path(project_id, gcp_region, queue_name, task_name)
    task = tasks_v2.Task(
        name=full_task_path,
        schedule_time=task_time,
        http_request=tasks_v2.HttpRequest(
            url=url,
            http_method=http_method,
            oidc_token=token,
            body=body,
            headers={"Content-Type": "application/json"},
        ),
    )
    client.create_task(parent=client.queue_path(project_id, gcp_region, queue_name), task=task)
