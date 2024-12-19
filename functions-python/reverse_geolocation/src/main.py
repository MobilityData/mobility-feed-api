import logging
from typing import Dict, Tuple

import flask
import functions_framework
from cloudevents.http import CloudEvent

from reverse_geolocation_aggregator import reverse_geolocation_aggregate as aggregator
from reverse_geolocation_processor import reverse_geolocation_process as processor
from reverse_geolocator import reverse_geolocation as geolocator

# Initialize logging
logging.basicConfig(level=logging.INFO)


@functions_framework.cloud_event
def reverse_geolocation(cloud_event: CloudEvent):
    """Function that is triggered when a new dataset is uploaded to extract the location information."""
    return geolocator(cloud_event)


@functions_framework.http
def reverse_geolocation_process(
    request: flask.Request,
) -> Tuple[str, int] | Tuple[Dict, int]:
    """
    Main function to handle reverse geolocation population.
    """
    return processor(request)


@functions_framework.http
def reverse_geolocation_aggregate(
    request: flask.Request,
) -> Tuple[str, int] | Tuple[Dict, int]:
    """
    Main function to handle reverse geolocation population.
    """
    return aggregator(request)
