import logging
import traceback
from datetime import datetime

import flask
import functions_framework
from flask import Response

from shared.helpers.logger import init_logger
from processors.base_analytics_processor import NoFeedDataException
from processors.gbfs_analytics_processor import GBFSAnalyticsProcessor
from processors.gtfs_analytics_processor import GTFSAnalyticsProcessor

init_logger()


def get_compute_date(request: flask.Request) -> datetime:
    """
    Get the compute date from the request JSON. If the date is invalid, return today at midnight.
    """
    try:
        json_request = request.get_json()
        compute_date_str = json_request.get("compute_date", None)
        if compute_date_str:
            return datetime.strptime(compute_date_str, "%Y%m%d")
    except Exception as e:
        logging.error(f"Error getting compute date: {e}")
    # Return today at midnight if the date is invalid
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


def preprocess_analytics(request: flask.Request, processor_class) -> Response:
    """
    Common logic to process analytics using the given processor class.
    """
    logging.info("Function triggered: %s", processor_class.__name__)
    compute_date = get_compute_date(request)
    logging.info("Compute date: %s", compute_date)
    try:
        processor = processor_class(compute_date)
        processor.run()
    except NoFeedDataException as e:
        logging.warning("No feed data found for date %s: %s", compute_date, e)
        return Response(f"No feed data found for date {compute_date}: {e}", status=404)
    except Exception as e:
        # Extracting the traceback details
        tb = traceback.format_exc()
        logging.error("Error processing %s analytics: %s", processor_class.__name__, e)
        logging.error(
            "Error trace processing %s analytics: %s", processor_class.__name__, tb
        )
        return Response(
            f"Error processing analytics for date {compute_date}: {e}", status=500
        )

    message = f"Successfully processed analytics for date: {compute_date}"
    logging.info(message)
    return Response(message, status=200)


@functions_framework.http
def preprocess_analytics_gtfs(request: flask.Request) -> Response:
    return preprocess_analytics(request, GTFSAnalyticsProcessor)


@functions_framework.http
def preprocess_analytics_gbfs(request: flask.Request) -> Response:
    return preprocess_analytics(request, GBFSAnalyticsProcessor)
