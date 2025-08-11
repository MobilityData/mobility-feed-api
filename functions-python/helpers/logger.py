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
import logging
import threading

import google.cloud.logging

from shared.common.logging_utils import get_env_logging_level


def is_local_env():
    return os.getenv("K_SERVICE") is None


class StableIdFilter(logging.Filter):
    """
    Add a stable_id to the log record with format: [stable_id] log_message
    """

    def __init__(self, stable_id=None):
        super().__init__()
        self.stable_id = stable_id

    def filter(self, record):
        if self.stable_id:
            record.msg = f"[{self.stable_id}] {record.msg}"
        return True


lock = threading.Lock()
lock_logger = threading.Lock()
_logging_initialized = False


def init_logger():
    """
    Initializes the logger with level INFO if not set in the environment.
    On cloud environment it will also initialize the GCP logger.
    """
    logging_level = get_env_logging_level()
    logging.basicConfig(level=logging_level)
    logging.info("Logger initialized with level: %s", logging_level)
    global _logging_initialized
    if not is_local_env() and not _logging_initialized:
        # Avoids initializing the logs multiple times due to performance concerns
        with lock:
            if _logging_initialized:
                return
            try:
                client = google.cloud.logging.Client()
                client.setup_logging()
            except Exception as error:
                # This might happen when the GCP authorization credentials are not available.
                # Example, when running the tests locally
                logging.error(f"Error initializing the logger: {error}")
            _logging_initialized = True


def get_logger(name: str, stable_id: str = None):
    """
    Get the logger instance for the specified name.
    If stable_id is provided, the StableIdFilter is added.
    This method can be called multiple times for the same logger name without creating a side effect.
    """
    with lock_logger:
        # Create the logger with the provided name to avoid retuning the same logger instance
        logger = (
            logging.getLogger(f"{name}_{stable_id}")
            if stable_id
            else logging.getLogger(name)
        )
        logger.setLevel(level=get_env_logging_level())
        if stable_id and not any(
            isinstance(log_filter, StableIdFilter) for log_filter in logger.filters
        ):
            logger.addFilter(StableIdFilter(stable_id))
        return logger
