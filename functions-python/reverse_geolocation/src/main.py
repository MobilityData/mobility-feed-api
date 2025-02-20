import flask
import functions_framework
from cloudevents.http import CloudEvent


@functions_framework.http
def reverse_geolocation_processor(request: flask.Request):
    """
    Cloud Function that processes a reverse geolocation request.
    """
    from reverse_geolocation_processor import reverse_geolocation_process

    return reverse_geolocation_process(request)


@functions_framework.http
def reverse_geolocation_batch(_: flask.Request):
    """
    Cloud Function that batch triggers the reverse geolocation process.
    """
    from reverse_geolocation_batch import reverse_geolocation_batch

    return reverse_geolocation_batch()


@functions_framework.cloud_event
def reverse_geolocation(request: CloudEvent):
    """
    Cloud Function that triggers the reverse geolocation process
    Function trigger: A new dataset is uploaded to the storage bucket.
    """
    from reverse_geolocation import reverse_geolocation_storage_trigger

    return reverse_geolocation_storage_trigger(request)


@functions_framework.cloud_event
def reverse_geolocation_pubsub(request: CloudEvent):
    """
    Cloud Function that triggers the reverse geolocation process
    Function trigger: A new dataset is uploaded to the storage bucket.
    """
    from reverse_geolocation import reverse_geolocation_pubsub

    return reverse_geolocation_pubsub(request)
