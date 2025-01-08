import logging
import traceback
from datetime import datetime

import flask
import functions_framework
from flask import Response

from shared.helpers.logger import Logger
from processors.base_analytics_processor import NoFeedDataException
from processors.gbfs_analytics_processor import GBFSAnalyticsProcessor
from processors.gtfs_analytics_processor import GTFSAnalyticsProcessor

logging.basicConfig(level=logging.INFO)


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
    Logger.init_logger()
    logging.info(f"{processor_class.__name__} Function triggered")
    compute_date = get_compute_date(request)
    logging.info(f"Compute date: {compute_date}")
    try:
        processor = processor_class(compute_date)
        processor.run()
    except NoFeedDataException as e:
        logging.warning(f"No feed data found for date {compute_date}: {e}")
        return Response(f"No feed data found for date {compute_date}: {e}", status=404)
    except Exception as e:
        # Extracting the traceback details
        tb = traceback.format_exc()
        logging.error(
            f"Error processing {processor_class.__name__} analytics: {e}\nTraceback:\n{tb}"
        )
        return Response(
            f"Error processing analytics for date {compute_date}: {e}", status=500
        )

    return Response(
        f"Successfully processed analytics for date: {compute_date}", status=200
    )


@functions_framework.http
def preprocess_analytics_gtfs(request: flask.Request) -> Response:
    return preprocess_analytics(request, GTFSAnalyticsProcessor)


@functions_framework.http
def preprocess_analytics_gbfs(request: flask.Request) -> Response:
    return preprocess_analytics(request, GBFSAnalyticsProcessor)
