#
#
#   MobilityData 2025
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import logging
import os
import subprocess
from pathlib import Path
from typing import TypedDict, List

from pympler import asizeof

from shared.helpers.logger import get_logger
from shared.helpers.transform import get_safe_value, get_safe_float, get_safe_int

STOP_TIMES_FILE = "stop_times.txt"
SHAPES_FILE = "shapes.txt"
TRIPS_FILE = "trips.txt"
ROUTES_FILE = "routes.txt"
STOPS_FILE = "stops.txt"
AGENCY_FILE = "agency.txt"


class ShapeTrips(TypedDict):
    shape_id: str
    trip_ids: List[str]


def get_volume_size(mountpoint: str):
    """
    Returns the total size of the specified filesystem mount point in a human-readable format.

    This function uses the `df` command-line utility to determine the size of the filesystem
    mounted at the path specified by `mountpoint`. If the mount point does not exist, the function
    prints an error message to the standard error and returns "N/A".

    Parameters:
    mountpoint: str
        The filesystem mount point path to check.

    Returns:
    str
        The total size of the specified filesystem mount point in human-readable format. If the
        mount point is not found, returns "N/A".
    """
    mp = Path(mountpoint)
    if not mp.exists():
        logging.warning("Mountpoint not found: %s", mountpoint)
        return "N/A"
    cmd = [
        "bash",
        "-c",
        "df -h \"$1\" | awk 'NR==2 {print $2}'",
        "_",  # $0 placeholder (ignored)
        str(mp),  # $1
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    size = result.stdout.strip()

    return size


class CsvCache:
    """
    CsvCache provides cached access to GTFS CSV files in a specified working directory.
    It lazily loads and caches file contents as lists of dictionaries, and offers
    helper methods to retrieve relationships between routes, trips, stops, and shapes.
    It lazily loads because not all files are necessarily needed.
    """

    def __init__(
        self,
        workdir: str = "./workdir",
        logger=None,
    ):
        if logger:
            self.logger = logger
        else:
            self.logger = get_logger(CsvCache.__name__)

        self.workdir = workdir

        self.file_data = {}

        self.logger.info("Using work directory: %s", self.workdir)
        self.logger.info("Size of workdir: %s", get_volume_size(self.workdir))

    def debug_log_size(self, label: str, obj: object) -> None:
        """Log the deep size of an object in bytes when DEBUG is enabled."""
        if self.logger.isEnabledFor(logging.DEBUG):
            try:
                size_bytes = asizeof.asizeof(obj)
                self.logger.debug("asizeof %s size: %d", label, size_bytes)
            except Exception as e:
                self.logger.debug("asizeof Failed to compute size for %s: %s", label, e)

    def get_path(self, filename: str) -> str:
        return os.path.join(self.workdir, filename)

    def set_workdir(self, workdir):
        self.workdir = workdir

    @staticmethod
    def get_index(columns, column_name):
        try:
            return columns.index(column_name)
        except ValueError:
            return None

    @staticmethod
    def get_safe_value_from_index(columns, index, default_value: str = None):
        return (
            get_safe_value(columns[index], default_value)
            if index is not None and index < len(columns)
            else default_value
        )

    @staticmethod
    def get_safe_float_from_index(columns, index):
        raw_value = CsvCache.get_safe_value_from_index(columns, index)
        return get_safe_float(raw_value)

    @staticmethod
    def get_safe_int_from_index(columns, index):
        raw_value = CsvCache.get_safe_value_from_index(columns, index)
        return get_safe_int(raw_value)
