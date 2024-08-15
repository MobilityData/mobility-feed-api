import base64
import json
import logging
from cloudevents.http import CloudEvent


def jsonify_pubsub(event: CloudEvent):
    """
    Convert the message data passed to a pub/sub triggered function to JSON
    @param event: The Pub/Sub message.
    """
    try:
        message_data = event["message"]["data"]
        message_json = json.loads(base64.b64decode(message_data).decode("utf-8"))
        return message_json
    except Exception as e:
        logging.error(f"Error parsing message data: {e}")
        return None
