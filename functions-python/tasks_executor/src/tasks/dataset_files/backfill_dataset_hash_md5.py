import base64
import logging
import os
from urllib.parse import urlparse, unquote

from google.cloud import storage
from google.cloud.exceptions import NotFound
from sqlalchemy.orm import Session, joinedload

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsdataset, Gtfsfeed

BATCH_COMMIT_SIZE = 50


def backfill_dataset_hash_md5_handler(payload) -> dict:
    """
    Entry point for backfilling the MD5 hash on existing GTFS datasets.

    Args:
        payload (dict): Task parameters.
            dry_run (bool): If True, log changes without writing to DB. Default: True.
            only_latest (bool): Process only datasets that are the latest for their feed. Default: True.
            only_missing_hashes (bool): Skip datasets that already have hash_md5 set. Default: True.
            limit (int | None): Maximum number of datasets to process.
                Omit or pass null to process all matching datasets without a limit. Default: 10.

    Returns:
        dict: Result summary.
    """
    dry_run = payload.get("dry_run", True)
    only_latest = payload.get("only_latest", True)
    only_missing_hashes = payload.get("only_missing_hashes", True)

    limit = None
    raw_limit = payload.get("limit", 10)
    if raw_limit is not None:
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            logging.warning("Invalid limit value %r, using no limit.", raw_limit)

    return backfill_dataset_hash_md5(
        dry_run=dry_run,
        only_latest=only_latest,
        only_missing_hashes=only_missing_hashes,
        limit=limit,
    )


def _get_blob_path_from_hosted_url(hosted_url: str, bucket_name: str) -> str | None:
    """
    Derives the GCS blob path from a hosted_url.

    Supports three URL formats:
    1. Standard GCS: https://storage.googleapis.com/{bucket_name}/{blob_path}
    2. Storage API:  https://storage.googleapis.com/storage/v1/b/{bucket}/o/{blob}?alt=media
    3. Custom CDN/domain (PUBLIC_HOSTED_DATASETS_URL env var prefix stripped)

    Args:
        hosted_url: The public URL of the dataset hosted on GCS.
        bucket_name: The GCS bucket name.

    Returns:
        The blob path (e.g. "mdb-10/mdb-10-202402080058/mdb-10-202402080058.zip"),
        or None if the URL cannot be parsed.
    """
    try:
        parsed = urlparse(hosted_url)

        # Standard GCS URL: https://storage.googleapis.com/{bucket_name}/{blob_path}
        prefix = f"/{bucket_name}/"
        if parsed.path.startswith(prefix):
            return parsed.path[len(prefix) :]

        # Storage API URL: .../b/{bucket}/o/{blob}?alt=media
        if "/b/" in parsed.path and "/o/" in parsed.path:
            blob_part = parsed.path.split("/o/", 1)[1]
            return unquote(blob_part)

        # Custom CDN/domain: strip the PUBLIC_HOSTED_DATASETS_URL prefix
        public_url = os.environ.get("PUBLIC_HOSTED_DATASETS_URL", "").rstrip("/")
        if public_url and hosted_url.startswith(public_url + "/"):
            return hosted_url[len(public_url) + 1 :]
    except Exception:
        pass
    return None


def _read_md5_from_gcs(bucket, blob_path: str) -> str | None:
    """
    Reads the MD5 hash from a GCS blob and returns it as a hex string.

    Args:
        bucket: GCS bucket object.
        blob_path: Path to the blob within the bucket.

    Returns:
        Hex-encoded MD5 string, or None if the blob is missing or has no MD5.
    """
    try:
        blob = bucket.blob(blob_path)
        blob.reload()
        if blob.md5_hash:
            return base64.b64decode(blob.md5_hash).hex()
    except NotFound:
        logging.warning("GCS blob not found: %s", blob_path)
    except Exception as e:
        logging.warning("Failed to read MD5 from GCS blob %s: %s", blob_path, e)
    return None


def _build_query(db_session: Session, only_latest: bool, only_missing_hashes: bool):
    """Build the SQLAlchemy query for datasets to backfill."""
    query = db_session.query(Gtfsdataset).filter(~Gtfsdataset.hosted_url.is_(None))

    if only_latest:
        query = query.join(Gtfsfeed, Gtfsfeed.latest_dataset_id == Gtfsdataset.id)

    if only_missing_hashes:
        query = query.filter(Gtfsdataset.hash_md5.is_(None))

    return query.options(joinedload(Gtfsdataset.feed))


@with_db_session
def backfill_dataset_hash_md5(
    db_session: Session,
    dry_run: bool = True,
    only_latest: bool = True,
    only_missing_hashes: bool = True,
    limit: int | None = 10,
) -> dict:
    """
    Backfills the MD5 hash for existing GTFS datasets by reading it from GCS blob metadata.

    Commits progress in batches of BATCH_COMMIT_SIZE so partial progress is preserved
    if the function fails mid-run.

    Args:
        db_session: SQLAlchemy DB session.
        dry_run: If True, log changes without writing to DB.
        only_latest: Process only datasets that are the latest for their feed.
        only_missing_hashes: Skip datasets that already have hash_md5 set.
        limit: Maximum number of datasets to process. None means no limit.

    Returns:
        dict: Result summary.
    """
    bucket_name = os.environ.get("DATASETS_BUCKET_NAME")

    query = _build_query(db_session, only_latest, only_missing_hashes)
    total_candidates = query.count()

    if dry_run:
        logging.info(
            "Dry run: %d datasets eligible for MD5 backfill (limit=%s).",
            total_candidates,
            limit if limit is not None else "none",
        )
        return {
            "message": f"Dry run: {total_candidates} datasets eligible for MD5 backfill.",
            "total_candidates": total_candidates,
            "limit": limit,
            "params": {
                "dry_run": dry_run,
                "only_latest": only_latest,
                "only_missing_hashes": only_missing_hashes,
            },
        }

    datasets = (query.limit(limit) if limit is not None else query).all()
    gcs_client = storage.Client()
    bucket = gcs_client.bucket(bucket_name)

    total_updated = 0
    total_skipped = 0
    pending_commit: list[Gtfsdataset] = []

    for dataset in datasets:
        blob_path = _get_blob_path_from_hosted_url(dataset.hosted_url, bucket_name)
        if not blob_path:
            logging.warning(
                "Could not derive blob path from hosted_url for dataset %s: %s",
                dataset.stable_id,
                dataset.hosted_url,
            )
            total_skipped += 1
            continue

        md5_hex = _read_md5_from_gcs(bucket, blob_path)
        if not md5_hex:
            logging.warning(
                "No MD5 found in GCS for dataset %s (blob: %s).",
                dataset.stable_id,
                blob_path,
            )
            total_skipped += 1
            continue

        dataset.hash_md5 = md5_hex
        pending_commit.append(dataset)
        total_updated += 1
        logging.info("Dataset %s: MD5 set to %s", dataset.stable_id, md5_hex)

        if len(pending_commit) >= BATCH_COMMIT_SIZE:
            db_session.commit()
            logging.info("Committed batch of %d datasets.", len(pending_commit))
            pending_commit = []

    # Commit any remaining datasets
    if pending_commit:
        db_session.commit()
        logging.info("Committed final batch of %d datasets.", len(pending_commit))

    result = {
        "message": "MD5 hash backfill completed.",
        "total_updated": total_updated,
        "total_skipped": total_skipped,
        "params": {
            "dry_run": dry_run,
            "only_latest": only_latest,
            "only_missing_hashes": only_missing_hashes,
            "limit": limit,
            "bucket_name": bucket_name,
        },
    }
    logging.info("Task summary: %s", result)
    return result
