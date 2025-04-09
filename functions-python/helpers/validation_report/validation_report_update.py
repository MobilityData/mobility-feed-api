import os
import logging
import json
from time import sleep

from google.cloud import workflows_v1
from google.cloud.workflows import executions_v1
from google.cloud.workflows.executions_v1 import Execution

env = os.getenv("ENV", "dev").lower()
bucket_name = f"mobilitydata-datasets-{env}"

def execute_workflow(
    project: str,
    location: str = "northamerica-northeast1",
    workflow: str = "gtfs_validator_execution",
    input_data: dict = None,
) -> Execution:
    """
    Executes a workflow with input data and print the execution results.
    @param project: The Google Cloud project id which contains the workflow to execute.
    @param location: The location for the workflow.
    @param workflow: The ID of the workflow to execute.
    @param input_data: A dictionary containing input data for the workflow.
    @return: The execution response.
    """
    execution_client = executions_v1.ExecutionsClient()
    workflows_client = workflows_v1.WorkflowsClient()
    parent = workflows_client.workflow_path(project, location, workflow)

    # Prepare the execution input as a JSON string.
    input_json = json.dumps(input_data) if input_data else "{}"

    # Create and configure the execution request with input data.
    execution_request = Execution(argument=input_json)
    response = execution_client.create_execution(
        parent=parent, execution=execution_request
    )
    logging.info(f"Created execution: {response.name}")
    execution = execution_client.get_execution(request={"name": response.name})
    return execution


def execute_workflows(
    latest_datasets,
    validator_endpoint=None,
    bypass_db_update=False,
    reports_bucket_name=None,
):
    """
    Execute the workflow for the latest datasets that need their validation report to be updated
    :param latest_datasets: List of tuples containing the feed stable id and dataset stable id
    :param validator_endpoint: The URL of the validator
    :param bypass_db_update: Whether to bypass the database update
    :param reports_bucket_name: The name of the bucket where the reports are stored
    :return: List of dataset stable ids for which the workflow was executed
    """
    project_id = f"mobility-feeds-{env}"
    location = os.getenv("LOCATION", "northamerica-northeast1")
    execution_triggered_datasets = []
    batch_size = int(os.getenv("BATCH_SIZE", 5))
    sleep_time = int(os.getenv("SLEEP_TIME", 5))
    count = 0
    logging.info(f"Executing workflow for {len(latest_datasets)} datasets")
    for feed_id, dataset_id in latest_datasets:
        try:
            input_data = {
                "data": {
                    "bypass_db_update": bypass_db_update,
                    "protoPayload": {
                        "resourceName": "projects/_/"
                        f"buckets/{bucket_name}/"
                        f"objects/{feed_id}/{dataset_id}/{dataset_id}.zip"
                    },
                    "resource": {
                        "labels": {"location": location, "project_id": project_id},
                    },
                }
            }
            if validator_endpoint:
                input_data["data"]["validator_endpoint"] = validator_endpoint
            if reports_bucket_name:
                input_data["data"]["reports_bucket_name"] = reports_bucket_name
            logging.info(f"Executing workflow for {feed_id}/{dataset_id}")
            execute_workflow(project_id, input_data=input_data)
            execution_triggered_datasets.append(dataset_id)
        except Exception as e:
            logging.error(
                f"Error while executing workflow for {feed_id}/{dataset_id}: {e}"
            )
        count += 1
        logging.info(f"Triggered workflow execution for {count} datasets")
        if count % batch_size == 0:
            logging.info(
                f"Sleeping for {sleep_time} seconds before next batch to avoid rate limiting.."
            )
            sleep(sleep_time)
    return execution_triggered_datasets