import json
import logging
import os
import tempfile
import traceback
import uuid
import zipfile

from google.cloud import storage
from sqlalchemy.orm import joinedload

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsdataset, Gtfsfile
from shared.helpers.utils import get_hash_from_file, download_and_get_hash


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
    query = (
        db_session.query(Gtfsdataset)
        .filter(~Gtfsdataset.hosted_url.is_(None))
        .filter(
            Gtfsdataset.zipped_size_bytes.is_(None)
            | Gtfsdataset.unzipped_size_bytes.is_(None)
            | ~Gtfsdataset.gtfsfiles.any()
        )
        .options(joinedload(Gtfsdataset.feed))
    )

    if after_date:
        query = query.filter(Gtfsdataset.downloaded_at >= after_date)

    if latest_only:
        query = query.filter(Gtfsdataset.latest)

    return query


def process_dataset(dataset: Gtfsdataset, credentials=None):
    """
    Downloads, extracts, uploads, and indexes files for a GTFS dataset.

    Args:
        dataset (Gtfsdataset): The dataset to process.
        credentials (str): Optional credentials for authentication.
    """
    hosted_url = dataset.hosted_url
    stable_id = dataset.stable_id
    logging.info("Processing dataset %s with URL %s", stable_id, hosted_url)
    bucket_name = os.getenv("DATASETS_BUCKET_NAME")

    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = os.path.join(tmp_dir, "dataset.zip")
        download_and_get_hash(
            hosted_url,
            zip_path,
            authentication_type=dataset.feed.authentication_type,
            api_key_parameter_name=dataset.feed.api_key_parameter_name,
            credentials=credentials,
            trusted_certs=True,
        )
        dataset.zipped_size_bytes = os.path.getsize(zip_path)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmp_dir)

        dataset.unzipped_size_bytes = sum(
            os.path.getsize(os.path.join(root, f))
            for root, _, files in os.walk(tmp_dir)
            for f in files
        )

        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        gtfs_files = []

        for root, _, files in os.walk(tmp_dir):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                # Only store files in GCS for latest datasets
                if dataset.latest:
                    logging.info("Storing latest dataset file %s", file_name)
                    blob_path = f"{'-'.join(stable_id.split('-')[:2])}/{stable_id}/extracted/{file_name}"
                    blob = bucket.blob(blob_path)
                    blob.upload_from_filename(file_path)
                    blob.make_public()

                gtfs_files.append(
                    Gtfsfile(
                        id=str(uuid.uuid4()),
                        file_name=file_name,
                        file_size_bytes=os.path.getsize(file_path),
                        hash=get_hash_from_file(file_path),
                        hosted_url=blob.public_url if dataset.latest else None,
                    )
                )

        dataset.gtfsfiles = gtfs_files
        extracted_data = {
            "zipped_size_bytes": dataset.zipped_size_bytes,
            "unzipped_size_bytes": dataset.unzipped_size_bytes,
            "file_count": len(gtfs_files),
            "files": [
                {
                    "file_name": file.file_name,
                    "file_size_bytes": file.file_size_bytes,
                    "hash": file.hash,
                    "hosted_url": file.hosted_url,
                }
                for file in gtfs_files
            ],
        }
        logging.info(extracted_data)


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
    credentials = json.loads(os.getenv("FEEDS_CREDENTIALS", "{}"))
    logging.info("Starting to process datasets with missing files...")

    for dataset in datasets.all():
        try:
            process_dataset(
                dataset, credentials=credentials.get(dataset.feed.stable_id)
            )
        except Exception:
            logging.error("Error processing dataset %s:", dataset.stable_id)
            traceback.print_exc()
            continue
        count += 1
        total_processed += 1

        if count % batch_count == 0:
            db_session.commit()
            logging.info(
                "Committed %d datasets. Total processed: %d",
                batch_count,
                total_processed,
            )

    db_session.commit()
    logging.info("All datasets processed and committed. Total: %d", total_processed)

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
