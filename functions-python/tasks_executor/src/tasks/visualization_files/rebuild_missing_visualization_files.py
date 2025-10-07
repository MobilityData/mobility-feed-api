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
from typing import List, Final, Optional

from sqlalchemy import func, distinct
from sqlalchemy.orm import Session, selectinload

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsfeed, Gtfsdataset, Gtfsfile
from shared.helpers.utils import create_http_pmtiles_builder_task

REQUIRED_FILES: Final[List[str]] = [
    "stops.txt",
    "routes.txt",
    "trips.txt",
    "stop_times.txt",
]


def rebuild_missing_visualization_files_handler(payload) -> dict:
    """
    Rebuilds missing visualization files for GTFS datasets.
    This function processes datasets missing visualization files and triggers the PMTiles builder workflow.
    The payload structure is:
    {
        "dry_run": bool,  # [optional] If True, do not execute the workflow
        "check_existing": bool,  # [optional] If True, check if visualization files already exist before creating tasks
        "latest_only": bool,  # [optional] If True, include only latest datasets
        "include_deprecated_feeds": bool,  # [optional] If True, include datasets from deprecated feeds
        "include_feed_op_status": list[str],  # [optional] List of feed operational statuses to include
         # e.g., ["published", "wip"]. Default is ["published"].
        "limit": int,  # [optional] Limit the number of datasets to process
    }
    Args:
        payload (dict): The payload containing the task details.
    Returns:
        str: A message indicating the result of the operation with the total_processed datasets.
    """
    (
        dry_run,
        check_existing,
        latest_only,
        include_deprecated_feeds,
        include_feed_op_status,
        limit,
    ) = get_parameters(payload)

    return rebuild_missing_visualization_files(
        dry_run=dry_run,
        check_existing=check_existing,
        latest_only=latest_only,
        include_feed_op_status=include_feed_op_status,
        include_deprecated_feeds=include_deprecated_feeds,
        limit=limit,
    )


@with_db_session
def rebuild_missing_visualization_files(
    dry_run: bool = True,
    check_existing: bool = True,
    latest_only: bool = True,
    include_deprecated_feeds: bool = False,
    include_feed_op_status: list[str] = ["published"],
    limit: Optional[int] = None,
    db_session: Session | None = None,
) -> dict:
    """
    Rebuilds missing visualization files for GTFS datasets.
    Args:
        dry_run (bool): dry run flag. If True, do not execute the workflow. Default: True
        check_existing (bool): If True, check if visualization files already exist before creating tasks. Default: True
        latest_only (bool): If True, include only latest datasets. Default: True
        include_deprecated_feeds (bool): If True, include datasets from deprecated feeds. Default: False
        include_feed_op_status (list[str]): List of feed operational statuses to include. Default: ['published']
        limit (Optional[int]): Limit the number of datasets to process. Default: None (no limit)
        db_session: DB session

    Returns:
        flask.Response: A response with message and total_processed datasets.
    """
    # Query datasets with all required files
    datasets_query = db_session.query(Gtfsdataset)
    if latest_only:
        datasets_query = datasets_query.filter(Gtfsdataset.latest.is_(True))
    if not include_deprecated_feeds:
        datasets_query = datasets_query.filter(
            Gtfsdataset.feed.has(Gtfsfeed.status != "deprecated")
        )
    if include_feed_op_status:
        datasets_query = datasets_query.filter(
            Gtfsdataset.feed.has(
                Gtfsfeed.operational_status.in_(include_feed_op_status)
            )
        )
    if check_existing:
        datasets_query = datasets_query.join(
            Gtfsfeed, Gtfsdataset.feed_id == Gtfsfeed.id
        ).filter(Gtfsfeed.visualization_dataset_id.is_(None))
    datasets_query = (
        datasets_query.join(Gtfsdataset.gtfsfiles)
        .filter(Gtfsfile.file_name.in_(REQUIRED_FILES))
        .group_by(Gtfsdataset.id)
        .having(func.count(distinct(Gtfsfile.file_name)) == len(REQUIRED_FILES))
        .options(selectinload(Gtfsdataset.feed))
    )

    if limit:
        datasets_query = datasets_query.limit(limit)

    datasets = datasets_query.all()
    logging.info(f"Found {len(datasets)} latest datasets with all required files.")

    tasks_to_create = []
    for dataset in datasets:
        tasks_to_create.append(
            {
                "feed_stable_id": dataset.feed.stable_id,
                "dataset_stable_id": dataset.stable_id,
            }
        )
    total_processed = len(tasks_to_create)
    logging.info(f"Total datasets to process: {total_processed}")

    # Create tasks to rebuild visualization files
    if not dry_run:
        for task in tasks_to_create:
            create_http_pmtiles_builder_task(
                task["feed_stable_id"], task["dataset_stable_id"]
            )

    message = (
        "Dry run: no datasets processed."
        if dry_run
        else "Rebuild missing visualization files task executed successfully."
    )
    result = {
        "message": message,
        "total_processed": total_processed,
        "params": {
            "dry_run": dry_run,
            "check_existing": check_existing,
            "latest_only": latest_only,
            "include_deprecated_feeds": include_deprecated_feeds,
            "limit": limit,
        },
    }
    logging.info(result)
    return result


def get_parameters(payload):
    """
    Get parameters from the payload and environment variables.

    Args:
        payload (dict): dictionary containing the payload data.
    Returns:
        tuple: tuple with: dry_run, bucket_name, check_existing parameters
    """
    dry_run = payload.get("dry_run", True)
    dry_run = dry_run if isinstance(dry_run, bool) else str(dry_run).lower() == "true"
    check_existing = payload.get("check_existing", True)
    check_existing = (
        check_existing
        if isinstance(check_existing, bool)
        else str(check_existing).lower() == "true"
    )
    latest_only = payload.get("latest_only", True)
    latest_only = (
        latest_only
        if isinstance(latest_only, bool)
        else str(latest_only).lower() == "true"
    )
    include_deprecated_feeds = payload.get("include_deprecated_feeds", False)
    include_deprecated_feeds = (
        include_deprecated_feeds
        if isinstance(include_deprecated_feeds, bool)
        else str(include_deprecated_feeds).lower() == "true"
    )
    include_feed_op_status = payload.get("include_feed_op_status", ["published"])
    limit = payload.get("limit", None)
    limit = limit if isinstance(limit, int) and limit > 0 else None
    return (
        dry_run,
        check_existing,
        latest_only,
        include_deprecated_feeds,
        include_feed_op_status,
        limit,
    )
