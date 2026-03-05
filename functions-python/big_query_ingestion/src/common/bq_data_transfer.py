import logging
import os
from datetime import datetime

from google.cloud import bigquery, storage

from shared.helpers.big_query_helpers import (
    collect_blobs_and_uris,
    make_staging_table_ref,
    ensure_staging_table_like_target,
    load_uris_into_staging,
    publish_staging_to_target,
    cleanup_success,
    cleanup_failure,
)
from shared.helpers.bq_schema.schema import json_schema_to_bigquery, load_json_schema

# Environment variables
project_id = os.getenv("PROJECT_ID")
bucket_name = os.getenv("BUCKET_NAME")
dataset_id = os.getenv("DATASET_ID")
table_id = f"{os.getenv('TABLE_ID')}_{datetime.now().strftime('%Y%m%d')}"
dataset_location = os.getenv("BQ_DATASET_LOCATION")


class BigQueryDataTransfer:
    """Base class for BigQuery data transfer."""

    def __init__(self):
        self.bigquery_client = bigquery.Client(project=project_id)
        self.storage_client = storage.Client(project=project_id)
        self.schema_path = None
        self.nd_json_path_prefix = "ndjson"

    def create_bigquery_dataset(self):
        """Creates a BigQuery dataset if it does not exist."""
        dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
        try:
            self.bigquery_client.get_dataset(dataset_ref)
            logging.info("Dataset %s already exists.", dataset_id)
        except Exception:
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = dataset_location
            self.bigquery_client.create_dataset(dataset)
            logging.info("Created dataset %s", dataset_id)

    def create_bigquery_table(self):
        """Creates a BigQuery table if it does not exist."""
        dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
        table_ref = dataset_ref.table(table_id)

        try:
            self.bigquery_client.get_table(table_ref)
            logging.info("Table %s  already exists.", table_id)
        except Exception:
            if self.schema_path is None:
                raise Exception("Schema path is not provided")
            json_schema = load_json_schema(self.schema_path)
            schema = json_schema_to_bigquery(json_schema)

            table = bigquery.Table(table_ref, schema=schema)
            table = self.bigquery_client.create_table(table)
            logging.info(
                "Created table %s.%s.%s",
                table.project,
                table.dataset_id,
                table.table_id,
            )

    def load_data_to_bigquery(self):
        """Loads data from Cloud Storage to BigQuery atomically via a staging table.
        The process is:
        1. Create a staging table with the same schema as the target.
        2. Load data from GCS to the staging table.
        3. If load is successful, copy data from staging to target (overwriting).
        4. If all steps succeed, delete the blobs and staging table.
        5. If any step fails, delete the staging table and do not touch blobs or target.
        """
        dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
        target_table_ref = dataset_ref.table(table_id)

        blobs, source_uris = collect_blobs_and_uris(
            self.storage_client,
            bucket_name=bucket_name,
            prefix=self.nd_json_path_prefix,
        )

        if not source_uris:
            return

        staging_table_ref = make_staging_table_ref(target_table_ref)

        try:
            ensure_staging_table_like_target(
                self.bigquery_client, target_table_ref, staging_table_ref
            )
            load_uris_into_staging(self.bigquery_client, staging_table_ref, source_uris)
            publish_staging_to_target(
                self.bigquery_client, staging_table_ref, target_table_ref
            )
            cleanup_success(self.bigquery_client, staging_table_ref, blobs)

        except Exception as e:
            logging.error("An error occurred while loading data to BigQuery: %s", e)
            cleanup_failure(self.bigquery_client, staging_table_ref)
            raise

    def send_data_to_bigquery(self):
        """Full process to send data to BigQuery."""
        try:
            self.create_bigquery_dataset()
            self.create_bigquery_table()
            self.load_data_to_bigquery()
            msg = "Data successfully loaded to BigQuery"
            logging.info(msg)
            return msg, 200
        except Exception as e:
            logging.error("An error occurred: %s", e)
            return f"Error while loading data: {e}", 500
