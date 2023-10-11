from google.cloud import storage
from sqlalchemy import create_engine
import os
from google.cloud import bigquery
from datetime import date
from typing import List, Dict, Union, Any


def create_bucket(bucket_name):
    """
    Creates GCP storage bucket if it doesn't exist
    :param bucket_name: name of the bucket to create
    """
    storage_client = storage.Client()
    bucket = storage_client.lookup_bucket(bucket_name)
    if bucket is None:
        bucket = storage_client.create_bucket(bucket_name)
        print(f'Bucket {bucket} created.')
    else:
        print(f'Bucket {bucket_name} already exists.')


def get_db_engine():
    """
    :return: Database engine
    """
    postgres_user = os.getenv("POSTGRES_USER")
    postgres_password = os.getenv("POSTGRES_PASSWORD")
    postgres_db = os.getenv("POSTGRES_DB")
    postgres_port = os.getenv("POSTGRES_PORT")
    postgres_host = os.getenv("POSTGRES_HOST")

    sqlalchemy_database_url = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}" \
                              f"/{postgres_db}"
    engine = create_engine(sqlalchemy_database_url, echo=True)
    return engine


def create_bigquery_table(
        project_id: str,
        dataset_name: str,
        table_name: str,
        schema: List[bigquery.SchemaField]
) -> bigquery.Table:
    """Create a BigQuery dataset and table with the given schema.
    :param project_id: The ID of the project where the dataset and table will reside.
    :param dataset_name: The name of the dataset to create.
    :param table_name: The name of the table to create.
    :param schema: The schema for the table.
    :return: The created table.
    """
    client = bigquery.Client()

    # Create a Dataset
    dataset_id = f"{project_id}.{dataset_name}"
    dataset = bigquery.Dataset(dataset_id)
    client.create_dataset(dataset, exists_ok=True)

    # Create a Table
    table_id = f"{dataset_id}.{table_name}"
    table = bigquery.Table(table_id, schema=schema)
    return client.create_table(table, exists_ok=True)


def insert_rows_into_table(
        table: bigquery.Table,
        rows: List[Dict[str, Union[str, int, date]]]
):
    """Insert rows into a BigQuery table.
    :param table: The table where rows will be inserted.
    :param rows: The rows to insert.
    :return: list of errors
    """
    client = bigquery.Client()
    return client.insert_rows_json(table, rows)


def query_table(
        project_id: str,
        query: str
) -> List[Dict[str, Any]]:
    """
    Query a BigQuery table and return the results as a list of dictionaries.
    :param project_id: The ID of the project where the table resides.
    :param query: The SQL query string.
    :return: A list of dictionaries containing the query results.
    """
    client = bigquery.Client(project=project_id)
    query_job = client.query(query)
    results = [dict(row) for row in query_job]
    return results
