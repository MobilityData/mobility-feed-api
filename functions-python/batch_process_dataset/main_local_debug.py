# Code to be able to debug locally without affecting the runtime cloud function
import base64
import json

from cloudevents.http import CloudEvent

#
# Requirements:
# - Google Cloud SDK installed
# - Make sure to have the following environment variables set in your .env.local file
# - Local database in running state
# - Pub/Sub emulator running
#   - gcloud beta emulators pubsub start --project=project-id --host-port='localhost:8043'
# - Google Datastore emulator running
#   - gcloud beta emulators datastore start --project=project-id --host-port='localhost:8042' --no-store-on-disk

# Usage:
# - python batch_process_dataset/main_local_debug.py

from dotenv import load_dotenv
from batch_process_dataset.src.main import process_dataset

# Load environment variables from .env.local
load_dotenv(dotenv_path=".env.local")

if __name__ == "__main__":
    attributes = {
        "type": "com.google.cloud.pubsub.topic.publish",
        "source": "//pubsub.googleapis.com/projects/sample-project/topics/sample-topic",
    }
    data = {
        "message": {
            "data": base64.b64encode(
                json.dumps(
                    {
                        "execution_id": "execution_id",
                        "producer_url": "producer_url",
                        "feed_stable_id": "feed_stable_id",
                        "feed_id": "feed_id",
                        "dataset_id": "dataset_id",
                        "dataset_hash": "dataset_hash",
                        "authentication_type": 0,
                        "authentication_info_url": "authentication_info_url",
                        "api_key_parameter_name": "api_key_parameter_name",
                    }
                ).encode("utf-8")
            ).decode("utf-8")
        }
    }
    cloud_event = CloudEvent(attributes, data)
    process_dataset(cloud_event)
