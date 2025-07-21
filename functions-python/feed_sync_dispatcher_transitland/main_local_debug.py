# Code to be able to debug locally without affecting the runtime cloud function


# Requirements:
# - Google Cloud SDK installed
# - Make sure to have the following environment variables set in your .env.local file
# - Local database in running state
# - Follow the instructions in the README.md file
#
# Usage:
# - python feed_sync_dispatcher_transitland/main_local_debug.py

from main import feed_sync_dispatcher_transitland
from dotenv import load_dotenv

# Load environment variables from .env.local
load_dotenv(dotenv_path=".env.local_test")

if __name__ == "__main__":

    class RequestObject:
        def __init__(self, headers):
            self.headers = headers

    request = RequestObject({"X-Cloud-Trace-Context": "1234567890abcdef"})
    feed_sync_dispatcher_transitland(request)
