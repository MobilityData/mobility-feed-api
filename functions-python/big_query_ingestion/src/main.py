import logging

import functions_framework

from helpers.logger import Logger
from .gtfs.gtfs_big_query_ingest import BiqQueryDataTransferGTFS

logging.basicConfig(level=logging.INFO)


@functions_framework.http
def ingest_data_to_big_query_gtfs(_):
    Logger.init_logger()
    logging.info("Function triggered")
    return BiqQueryDataTransferGTFS().send_data_to_bigquery()
