import logging

import flask
import functions_framework

from shared.helpers.logger import init_logger

init_logger()


@functions_framework.http
def reverse_geolocation_processor(request: flask.Request):
    """
    Cloud Function that processes a reverse geolocation request.
    Function trigger: HTTP request by Cloud Tasks.
    """
    from reverse_geolocation_processor import reverse_geolocation_process

    result = reverse_geolocation_process(request)
    logging.info(result)
    return result


@functions_framework.http
def reverse_geolocation_batch(request: flask.Request):
    """
    Cloud Function that batch triggers the reverse geolocation process.
    Function trigger: HTTP request manually triggered.
    """
    from reverse_geolocation_batch import reverse_geolocation_batch

    result = reverse_geolocation_batch(request)
    logging.info(result)
    return result
