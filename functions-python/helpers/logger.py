#
#   MobilityData 2023
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import os

import google.cloud.logging
from google.cloud.logging_v2 import Client
import logging


class StableIdFilter(logging.Filter):
    """Add a stable_id to the log record"""

    def __init__(self, stable_id=None):
        super().__init__()
        self.stable_id = stable_id

    def filter(self, record):
        if self.stable_id:
            record.msg = f"[{self.stable_id}] {record.msg}"
        return True


class Logger:
    """
    Util class for logging information, errors or warnings.
    This class uses the Google Cloud Logging API enhancing the logs with extra request information.
    """

    def __init__(self, name):
        self.init_logger()
        self.logger = self.init_logger().logger(name)

    @staticmethod
    def init_logger() -> Client:
        """
        Initializes the logger for both local debugging and GCP environments.
        """
        try:
            # Check if running in a GCP environment (default credentials available)
            if os.getenv("ENV") == "local":
                # Local environment: use standard logging
                logging.basicConfig(level=logging.DEBUG)
                logging.info("Local logger initialized (standard logging).")
                client = None  # Return None since cloud client is not used
            else:
                client = google.cloud.logging.Client()
                client.setup_logging()
                logging.info("Google Cloud Logging initialized.")
        except Exception as e:
            logging.error(f"Failed to initialize logging: {e}")
            logging.basicConfig(level=logging.DEBUG)
            logging.info("Fallback to standard local logging.")
            client = None
        return client

    def get_logger(self) -> Client:
        """
        Get the GCP logger instance
        :return: the logger instance
        """
        return self.logger
