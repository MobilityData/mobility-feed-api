import logging
import os
from datetime import datetime, timedelta
from typing import List

import flask
from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsfeed
from shared.helpers.gtfs_validator_common import (
    get_gtfs_validator_results_bucket,
    get_gtfs_validator_url,
)
from shared.helpers.query_helper import get_datasets_with_missing_reports_query
from shared.helpers.validation_report.validation_report_update import execute_workflows

logging.basicConfig(level=logging.INFO)


def rebuild_missing_validation_reports_handler(
    payload, db_session: Session | None = None
) -> flask.Response:
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
        db_session (Session): The database session to use.
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
        db_session=db_session,
        validator_endpoint=validator_endpoint,
        dry_run=dry_run,
        filter_after_in_days=filter_after_in_days,
        filter_statuses=filter_statuses,
        prod_env=prod_env,
    )


@with_db_session
def rebuild_missing_validation_reports(
    db_session: Session,
    validator_endpoint: str,
    dry_run: bool = True,
    filter_after_in_days: int = 14,
    filter_statuses: List[str] | None = None,
    prod_env: bool = False,
):
    """
    Rebuilds missing validation reports for GTFS datasets.
    :param db_session: DB session
    :param validator_endpoint: Validator endpoint URL
    :param dry_run: dry run flag. If True, do not execute the workflow.
    :param filter_after_in_days:  Filter the datasets older than this number of days. Default: 14 days ago
    :param filter_statuses: [optional] Filter datasets by status(in)
    :param prod_env: True if target environment is production, false otherwise
    :return: A message indicating the result of the operation with the total_processed datasets.
    """
    filter_after = datetime.today() - timedelta(days=filter_after_in_days)
    query = get_datasets_with_missing_reports_query(db_session, filter_after)
    if filter_statuses:
        query = query.filter(Gtfsfeed.status.in_(filter_statuses))
    total_processed = 0
    limit = 100
    offset = 0
    while True:
        datasets = query.limit(limit).offset(offset).all()
        logging.debug("Found %s datasets, offset %s", len(datasets), offset)
        if len(datasets) == 0:
            break

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

        # Last page of results
        if len(datasets) < limit:
            break
        offset += limit
    return flask.jsonify(
        {
            "message": "Rebuild missing validation reports task executed successfully.",
            "total_processed": total_processed,
        }
    )


def get_parameters(payload):
    """
    Get parameters from the payload and environment variables.
    :param payload:
    :return: the dry_run, filter_after_in_days, filter_statuses, prod_env, validator_endpoint parameters
    """
    prod_env = os.getenv("ENVIRONMENT", "").lower() == "prod"
    validator_endpoint = get_gtfs_validator_url(prod_env)
    dry_run = payload.get("dry_run")
    filter_after_in_days = payload.get("filter_after_in_days")
    filter_statuses = payload.get("filter_status")
    return dry_run, filter_after_in_days, filter_statuses, prod_env, validator_endpoint
