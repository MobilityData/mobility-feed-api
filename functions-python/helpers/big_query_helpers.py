import logging
import time
from typing import List, Tuple

from google.cloud import bigquery
from google.cloud.bigquery import LoadJobConfig, CopyJobConfig, SourceFormat

MAX_URIS_PER_JOB = 1000


def chunked(seq: List[str], size: int):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def collect_blobs_and_uris(
    storage_client, bucket_name: str, prefix: str
) -> Tuple[List[object], List[str]]:
    """List blobs in GCS with given prefix and construct their URIs."""
    try:
        blobs = list(storage_client.list_blobs(bucket_name, prefix=prefix))
        uris = [f"gs://{bucket_name}/{b.name}" for b in blobs]
        logging.info("Found %s files to load to BigQuery.", len(uris))
        return blobs, uris
    except Exception as e:
        logging.error("Failed to list blobs or construct URIs: %s", e)
        raise


def make_staging_table_ref(
    target_table_ref: bigquery.TableReference,
) -> bigquery.TableReference:
    """Construct a staging table reference in the same dataset with a unique name."""
    try:
        staging_table_id = f"{target_table_ref.table_id}__staging_{int(time.time())}"
        dataset_ref = bigquery.DatasetReference(
            target_table_ref.project, target_table_ref.dataset_id
        )
        return dataset_ref.table(staging_table_id)
    except Exception as e:
        logging.error("Failed to construct staging table reference: %s", e)
        raise


def ensure_staging_table_like_target(
    bigquery_client,
    target_table_ref: bigquery.TableReference,
    staging_table_ref: bigquery.TableReference,
) -> None:
    """Create staging table with same schema (and partitioning/clustering) as target."""
    try:
        target_tbl = bigquery_client.get_table(target_table_ref)

        staging_tbl = bigquery.Table(staging_table_ref, schema=target_tbl.schema)
        staging_tbl.time_partitioning = getattr(target_tbl, "time_partitioning", None)
        staging_tbl.range_partitioning = getattr(target_tbl, "range_partitioning", None)
        staging_tbl.clustering_fields = getattr(target_tbl, "clustering_fields", None)

        bigquery_client.create_table(staging_tbl, exists_ok=True)
        logging.info(
            "Staging table ready: %s.%s.%s",
            staging_table_ref.project,
            staging_table_ref.dataset_id,
            staging_table_ref.table_id,
        )
    except Exception as e:
        logging.error("Failed to create staging table like target: %s", e)
        raise


def load_uris_into_staging(
    bigquery_client,
    staging_table_ref: bigquery.TableReference,
    source_uris: List[str],
) -> None:
    """Load NDJSON files into staging in batches (10k URIs max/job)."""
    try:
        for batch_idx, uri_batch in enumerate(
            chunked(source_uris, MAX_URIS_PER_JOB), start=1
        ):
            logging.info(
                "Loading batch %s into staging (%s files)...", batch_idx, len(uri_batch)
            )
            job_cfg = LoadJobConfig(
                source_format=SourceFormat.NEWLINE_DELIMITED_JSON,
                write_disposition=(
                    bigquery.WriteDisposition.WRITE_TRUNCATE
                    if batch_idx == 1
                    else bigquery.WriteDisposition.WRITE_APPEND
                ),
            )
            job = bigquery_client.load_table_from_uri(
                uri_batch, staging_table_ref, job_config=job_cfg
            )
            job.result()  # fail fast

        staging_loaded = bigquery_client.get_table(staging_table_ref)
        logging.info(
            "All batches loaded into staging. Reported rows: %s",
            staging_loaded.num_rows,
        )
    except Exception as e:
        logging.error("Failed to load URIs into staging: %s", e)
        raise


def publish_staging_to_target(
    bigquery_client,
    staging_table_ref: bigquery.TableReference,
    target_table_ref: bigquery.TableReference,
) -> None:
    """Replace target contents with staging contents (publish moment)."""
    try:
        copy_cfg = CopyJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
        )

        logging.info("Publishing: copying staging to target with WRITE_TRUNCATE...")
        copy_job = bigquery_client.copy_table(
            sources=staging_table_ref,
            destination=target_table_ref,
            job_config=copy_cfg,
        )
        copy_job.result()
        logging.info("Publish complete: target replaced successfully.")
    except Exception as e:
        logging.error("Failed to publish staging to target: %s", e)
        raise


def cleanup_success(
    bigquery_client, staging_table_ref: bigquery.TableReference, blobs: List[object]
) -> None:
    """Delete staging table and source blobs after successful publish."""
    try:
        bigquery_client.delete_table(staging_table_ref, not_found_ok=True)
        logging.info("Deleted staging table.")

        for b in blobs:
            b.delete()
        logging.info("Deleted %s blobs.", len(blobs))
    except Exception as e:
        logging.error("Failed during cleanup after success: %s", e)
        raise


def cleanup_failure(
    bigquery_client, staging_table_ref: bigquery.TableReference
) -> None:
    """Attempt to delete staging table after failure, but log and continue if it fails (to preserve for inspection)."""
    try:
        bigquery_client.delete_table(staging_table_ref, not_found_ok=True)
        logging.info("Deleted staging table after failure.")
    except Exception as e:
        logging.warning(
            "Failed to delete staging table after failure; leaving it for inspection. Exception: %s",
            e,
        )
