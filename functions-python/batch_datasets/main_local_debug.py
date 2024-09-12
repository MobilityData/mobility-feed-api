# Code to be able to debug locally without affecting the runtime cloud function

#
# Requirements:
# - Google Cloud SDK installed
# - Make sure to have the following environment variables set in your .env.local file
# - Local database in running state
# - Pub/Sub emulator running
#   - gcloud beta emulators pubsub start --project=project-id --host-port='localhost:8043'
# - Google Datastore emulator running
#   - gcloud beta emulators datastore start --project=project-id --host-port='localhost:8042'

# Usage:
# - python batch_datasets/main_local_debug.py
from src.main import batch_datasets
from dotenv import load_dotenv

# Load environment variables from .env.local
load_dotenv(dotenv_path='.env.local')

if __name__ == "__main__":
    class RequestObject:
        def __init__(self, headers):
            self.headers = headers

    request = RequestObject({"X-Cloud-Trace-Context": "1234567890abcdef"})
    batch_datasets(request)
