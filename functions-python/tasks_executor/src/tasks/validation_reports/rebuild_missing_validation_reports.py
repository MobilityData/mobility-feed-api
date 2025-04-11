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

import logging
import os
from datetime import datetime, timedelta
from typing import List, Final

from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsfeed, Gtfsdataset
from shared.helpers.gtfs_validator_common import (
    get_gtfs_validator_results_bucket,
    get_gtfs_validator_url,
)
from shared.helpers.query_helper import get_datasets_with_missing_reports_query
from shared.helpers.validation_report.validation_report_update import execute_workflows

logging.basicConfig(level=logging.INFO)

QUERY_LIMIT: Final[int] = 100


def rebuild_missing_validation_reports_handler(payload) -> dict:
    """
    Rebuilds missing validation reports for GTFS datasets.
    This function processes datasets with missing validation reports using the GTFS validator workflow.
    The payload structure is:
    {
        "dry_run": bool,  # [optional] If True, do not execute the workflow
        "filter_after_in_days": int, # [optional] Filter datasets older than this number of days(default: 14 days ago)
        "filter_statuses": list[str] # [optional] Filter datasets by status(in)
    }
    Args:
        payload (dict): The payload containing the task details.
    Returns:
        str: A message indicating the result of the operation with the total_processed datasets.
    """
    (
        dry_run,
        filter_after_in_days,
        filter_statuses,
        prod_env,
        validator_endpoint,
    ) = get_parameters(payload)

    return rebuild_missing_validation_reports(
        validator_endpoint=validator_endpoint,
        dry_run=dry_run,
        filter_after_in_days=filter_after_in_days,
        filter_statuses=filter_statuses,
        prod_env=prod_env,
    )


@with_db_session
def rebuild_missing_validation_reports(
    validator_endpoint: str,
    dry_run: bool = True,
    filter_after_in_days: int = 14,
    filter_statuses: List[str] | None = None,
    prod_env: bool = False,
    db_session: Session | None = None,
) -> dict:
    """
    Rebuilds missing validation reports for GTFS datasets.

    Args:
        validator_endpoint: Validator endpoint URL
        dry_run (bool): dry run flag. If True, do not execute the workflow. Default: True
        filter_after_in_days (int):  Filter the datasets older than this number of days. Default: 14 days ago
        filter_statuses: [optional] Filter datasets by status(in). Default: None
        prod_env (bool): True if target environment is production, false otherwise. Default: False
        db_session: DB session

    Returns:
        flask.Response: A response with message and total_processed datasets.
    """
    filter_after = datetime.today() - timedelta(days=filter_after_in_days)
    query = get_datasets_with_missing_reports_query(db_session, filter_after)
    if filter_statuses:
        query = query.filter(Gtfsfeed.status.in_(filter_statuses))
    # Having a snapshot of datasets ids as the execution of the workflow
    # can potentially add reports while this function is still running.
    # This scenario will make the pagination result inconsistent.
    dataset_ids = [row[0] for row in query.with_entities(Gtfsdataset.id).all()]

    total_processed = 0
    limit = QUERY_LIMIT
    offset = 0

    for i in range(0, len(dataset_ids), limit):
        batch_ids = dataset_ids[i : i + limit]
        datasets = (
            db_session.query(Gtfsdataset).filter(Gtfsdataset.id.in_(batch_ids)).all()
        )
        logging.debug("Found %s datasets, offset %s", len(datasets), offset)

        if not dry_run:
            execute_workflows(
                datasets,
                validator_endpoint=validator_endpoint,
                bypass_db_update=False,
                reports_bucket_name=get_gtfs_validator_results_bucket(prod_env),
            )
        else:
            logging.debug("Dry run: %s datasets would be processed", datasets)
        total_processed += len(datasets)

    message = (
        "Rebuild missing validation reports task executed successfully."
        if not dry_run
        else "Dry run: no datasets processed."
    )
    return {
        "message": message,
        "total_processed": total_processed,
    }


def get_parameters(payload):
    """
    Get parameters from the payload and environment variables.

    Args:
        payload (dict): dictionary containing the payload data.
    Returns:
        dict: dict with: dry_run, filter_after_in_days, filter_statuses, prod_env, validator_endpoint parameters
    """
    prod_env = os.getenv("ENVIRONMENT", "").lower() == "prod"
    validator_endpoint = get_gtfs_validator_url(prod_env)
    dry_run = payload.get("dry_run")
    filter_after_in_days = payload.get("filter_after_in_days")
    filter_statuses = payload.get("filter_statuses")
    return dry_run, filter_after_in_days, filter_statuses, prod_env, validator_endpoint
