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
import threading
import logging

from shared.common.logging_utils import get_env_logging_level


class StableIdFilter(logging.Filter):
    """Add a stable_id to the log record"""

    def __init__(self, stable_id=None):
        super().__init__()
        self.stable_id = stable_id

    def filter(self, record):
        if self.stable_id:
            record.msg = f"[{self.stable_id}] {record.msg}"
        return True


_logger_initialized = False
lock = threading.Lock()


def init_logger():
    """
    Initializes the logger
    """
    with lock:
        global _logger_initialized
        if _logger_initialized:
            return
        logging.basicConfig(level=get_env_logging_level())
        _logger_initialized = True


def get_logger(name: str, stable_id: str = None):
    logger = logging.getLogger(name)
    if stable_id and not any(
        isinstance(handler, StableIdFilter) for handler in logger.handlers
    ):
        logger.addFilter(StableIdFilter(stable_id))
    return logger
