import logging

import flask
import functions_framework
from cloudevents.http import CloudEvent
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


@functions_framework.cloud_event
def reverse_geolocation(request: CloudEvent):
    """
    Cloud Function that triggers the reverse geolocation process
    Function trigger: A new dataset is uploaded to the storage bucket.
    """
    from reverse_geolocation import reverse_geolocation_storage_trigger

    result = reverse_geolocation_storage_trigger(request)
    logging.info(result)
    return result


@functions_framework.cloud_event
def reverse_geolocation_pubsub(request: CloudEvent):
    """
    Cloud Function that triggers the reverse geolocation process
    Function trigger: A message is sent to a Pub/Sub topic.
    """
    from reverse_geolocation import reverse_geolocation_pubsub

    result = reverse_geolocation_pubsub(request)
    logging.info(result)
    return result
