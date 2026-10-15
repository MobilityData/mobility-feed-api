import logging

import flask
import functions_framework

from shared.helpers.logger import init_logger

init_logger()


@functions_framework.http
def gtfs_file_data_extractor(request: flask.Request):
    """
    Cloud Function that extracts structured data from a single GTFS file
    (e.g. feed_info.txt) and persists it to the database.

    Function trigger: HTTP request by Cloud Tasks, enqueued by
    batch_process_dataset once a dataset has been processed.
    """
    from processor import process_file_data

    result = process_file_data(request)
    logging.info(result)
    return result
