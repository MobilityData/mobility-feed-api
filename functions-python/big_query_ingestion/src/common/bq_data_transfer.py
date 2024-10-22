import logging
import os
from datetime import datetime

from google.cloud import bigquery, storage
from google.cloud.bigquery.job import LoadJobConfig, SourceFormat

from helpers.bq_schema.schema import json_schema_to_bigquery, load_json_schema

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
            logging.info(f"Dataset {dataset_id} already exists.")
        except Exception:
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = dataset_location
            self.bigquery_client.create_dataset(dataset)
            logging.info(f"Created dataset {dataset_id}.")

    def create_bigquery_table(self):
        """Creates a BigQuery table if it does not exist."""
        dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
        table_ref = dataset_ref.table(table_id)

        try:
            self.bigquery_client.get_table(table_ref)
            logging.info(f"Table {table_id} already exists.")
        except Exception:
            if self.schema_path is None:
                raise Exception("Schema path is not provided")
            json_schema = load_json_schema(self.schema_path)
            schema = json_schema_to_bigquery(json_schema)

            table = bigquery.Table(table_ref, schema=schema)
            table = self.bigquery_client.create_table(table)
            logging.info(
                f"Created table {table.project}.{table.dataset_id}.{table.table_id}"
            )

    def load_data_to_bigquery(self):
        """Loads data from Cloud Storage to BigQuery."""
        dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
        table_ref = dataset_ref.table(table_id)
        source_uris = []
        # Get the list of blobs in the bucket
        blobs = list(
            self.storage_client.list_blobs(bucket_name, prefix=self.nd_json_path_prefix)
        )
        for blob in blobs:
            uri = f"gs://{bucket_name}/{blob.name}"
            source_uris.append(uri)
        logging.info(f"Found {len(source_uris)} files to load to BigQuery.")

        if len(source_uris) > 0:
            # Load the data to BigQuery
            job_config = LoadJobConfig()
            job_config.source_format = SourceFormat.NEWLINE_DELIMITED_JSON
            job_config.write_disposition = bigquery.WriteDisposition.WRITE_TRUNCATE

            load_job = self.bigquery_client.load_table_from_uri(
                source_uris, table_ref, job_config=job_config
            )
            try:
                load_job.result()  # Wait for the job to complete
                logging.info(
                    f"Loaded {len(source_uris)} files into "
                    f"{table_ref.project}.{table_ref.dataset_id}.{table_ref.table_id}"
                )
                # If successful, delete the blobs
                for blob in blobs:
                    blob.delete()
                    logging.info(f"Deleted blob: {blob.name}")
            except Exception as e:
                logging.error(f"An error occurred while loading data to BigQuery: {e}")
                for error in load_job.errors:
                    logging.error(f"Error: {error['message']}")
                    if "location" in error:
                        logging.error(f"Location: {error['location']}")
                    if "reason" in error:
                        logging.error(f"Reason: {error['reason']}")

    def send_data_to_bigquery(self):
        """Full process to send data to BigQuery."""
        try:
            self.create_bigquery_dataset()
            self.create_bigquery_table()
            self.load_data_to_bigquery()
            return "Data successfully loaded to BigQuery", 200
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            return f"Error while loading data: {e}", 500
