import logging

import functions_framework

from shared.helpers.logger import init_logger
from gbfs.gbfs_big_query_ingest import BigQueryDataTransferGBFS
from gtfs.gtfs_big_query_ingest import BigQueryDataTransferGTFS

init_logger()


@functions_framework.http
def ingest_data_to_big_query_gtfs(_):
    """Google Storage to Big Query data ingestion for GTFS data"""
    logging.info("Function triggered")
    return BigQueryDataTransferGTFS().send_data_to_bigquery()


@functions_framework.http
def ingest_data_to_big_query_gbfs(_):
    """Google Storage to Big Query data ingestion for GBFS data"""
    logging.info("Function triggered")
    return BigQueryDataTransferGBFS().send_data_to_bigquery()
