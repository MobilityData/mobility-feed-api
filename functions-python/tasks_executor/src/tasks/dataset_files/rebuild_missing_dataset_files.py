import logging
import os
import traceback
import uuid

from sqlalchemy.orm import joinedload

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsdataset, Gtfsfeed
from shared.helpers.pub_sub import publish_messages


def rebuild_missing_dataset_files_handler(payload) -> dict:
    """
    Entry point for rebuilding missing GTFS dataset files.

    Args:
        payload (dict): Task parameters including 'dry_run' and 'after_date'.

    Returns:
        dict: Result message and number of datasets processed.
    """
    dry_run = payload.get("dry_run", True)
    after_date = payload.get("after_date", None)
    latest_only = payload.get("latest_only", True)

    return rebuild_missing_dataset_files(
        dry_run=dry_run, after_date=after_date, latest_only=latest_only
    )


def get_datasets_with_missing_files_query(db_session, after_date, latest_only):
    """
    Query GTFS datasets missing zipped/unzipped size or extracted files.

    Args:
        db_session: SQLAlchemy DB session.
        after_date (str): Filter datasets downloaded after this ISO date.
        latest_only (bool): Whether to include only latest datasets.

    Returns:
        Query: SQLAlchemy query object.
    """
    query = db_session.query(Gtfsdataset)
    if latest_only:
        query = query.join(Gtfsfeed, Gtfsfeed.latest_dataset_id == Gtfsdataset.id)

    query = (
        query.filter(~Gtfsdataset.hosted_url.is_(None))
        .filter(
            Gtfsdataset.zipped_size_bytes.is_(None)
            | Gtfsdataset.unzipped_size_bytes.is_(None)
            | ~Gtfsdataset.gtfsfiles.any()
        )
        .options(joinedload(Gtfsdataset.feed))
    )

    if after_date:
        query = query.filter(Gtfsdataset.downloaded_at >= after_date)

    return query


@with_db_session
def rebuild_missing_dataset_files(
    db_session,
    dry_run: bool = True,
    after_date: str = None,
    latest_only: bool = True,
) -> dict:
    """
    Processes GTFS datasets missing extracted files and updates database.

    Args:
        db_session: SQLAlchemy DB session.
        dry_run (bool): If True, only logs how many would be processed.
        after_date (str): Only consider datasets downloaded after this ISO date.
        latest_only (bool): Whether to include only latest datasets.

    Returns:
        dict: Result summary.
    """
    datasets = get_datasets_with_missing_files_query(
        db_session, after_date=after_date, latest_only=latest_only
    )

    if dry_run:
        total = datasets.count()
        logging.info(
            "Dry run mode: %d datasets found with missing files. After date filter: %s",
            total,
            after_date,
        )
        return {
            "message": f"Dry run: {total} datasets with missing files found.",
            "total_processed": total,
        }

    total_processed = 0
    count = 0
    batch_count = 5
    logging.info("Starting to process datasets with missing files...")
    execution_id = f"task-executor-uuid-{uuid.uuid4()}"
    messages = []
    for dataset in datasets.all():
        try:
            message = {
                "execution_id": execution_id,
                "producer_url": dataset.feed.producer_url,
                "feed_stable_id": dataset.feed.stable_id,
                "feed_id": dataset.feed.id,
                "dataset_stable_id": dataset.stable_id,
                "dataset_hash": dataset.hash,
                "authentication_type": dataset.feed.authentication_type,
                "authentication_info_url": dataset.feed.authentication_info_url,
                "api_key_parameter_name": dataset.feed.api_key_parameter_name,
                "use_bucket_latest": True,
            }
            messages.append(message)
        except Exception:
            logging.error("Error processing dataset %s:", dataset.stable_id)
            traceback.print_exc()
            continue
        count += 1
        total_processed += 1

        if count % batch_count == 0:
            publish_messages(
                messages,
                os.getenv("PROJECT_ID"),
                os.getenv("DATASET_PROCESSING_TOPIC_NAME"),
            )
            messages = []
            logging.info(
                "Published message for %d datasets. Total processed: %d",
                batch_count,
                total_processed,
            )

    logging.info("All datasets processed. Total: %d", total_processed)

    result = {
        "message": "Rebuild missing dataset files completed.",
        "total_processed": total_processed,
        "params": {
            "dry_run": dry_run,
            "after_date": after_date,
            "latest_only": latest_only,
            "datasets_bucket_name": os.environ.get("DATASETS_BUCKET_NAME"),
        },
    }
    logging.info("Task summary: %s", result)
    return result
