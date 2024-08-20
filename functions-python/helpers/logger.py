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
        Initializes the logger
        """
        client = google.cloud.logging.Client()
        client.get_default_handler()
        client.setup_logging()
        return client

    def get_logger(self) -> Client:
        """
        Get the GCP logger instance
        :return: the logger instance
        """
        return self.logger
