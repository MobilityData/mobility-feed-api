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
    Return the total size of the filesystem at `mountpoint` in a human-readable string (e.g., "10G").

    Implementation notes
    - Uses the system `df -h` command piped through awk to extract the size column.
    - Requires a valid path; when the mountpoint doesn't exist, a warning is logged and "N/A" is returned.
    - Intended primarily for diagnostics in logs (does not affect processing logic).

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
    Lightweight utility for working-directory file paths and safe CSV extraction helpers.

    What it provides
    - Path resolution: `get_path(filename)` -> absolute path under the configured workdir.
    - Safe CSV accessors: helpers to get values/ints/floats from parsed rows by index without raising.
    - Column index lookup: helper to map header names to indices safely.
    - Diagnostics: optional deep-size logging of objects in DEBUG, and workdir size at initialization.

    Notes
    - This class does not currently implement an in-memory cache of full CSVs; processors stream files
      directly and use these helpers for robust parsing.
    - Constants for common GTFS filenames are exposed at module level (e.g., TRIPS_FILE, STOPS_FILE).
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

        self.logger.info("Using work directory: %s", self.workdir)
        self.logger.info("Size of workdir: %s", get_volume_size(self.workdir))

    def debug_log_size(self, label: str, obj: object) -> None:
        """Log the deep size of `obj` in bytes when DEBUG is enabled (best-effort, may fall back silently)."""
        if self.logger.isEnabledFor(logging.DEBUG):
            try:
                size_bytes = asizeof.asizeof(obj)
                self.logger.debug("asizeof %s size: %d", label, size_bytes)
            except Exception as e:
                self.logger.debug("asizeof Failed to compute size for %s: %s", label, e)

    def get_path(self, filename: str) -> str:
        """Return the absolute path for `filename` under the current workdir."""
        return os.path.join(self.workdir, filename)

    def set_workdir(self, workdir):
        """Update the working directory used to resolve file paths (does not move files)."""
        self.workdir = workdir

    @staticmethod
    def get_index(columns, column_name):
        """Return the index of `column_name` in the header list `columns`, or None if absent."""
        try:
            return columns.index(column_name)
        except ValueError:
            return None

    @staticmethod
    def get_safe_value_from_index(columns, index, default_value: str = None):
        """Safely fetch a value from `columns` at `index`, applying default and transform semantics."""
        return (
            get_safe_value(columns[index], default_value)
            if index is not None and index < len(columns)
            else default_value
        )

    @staticmethod
    def get_safe_float_from_index(columns, index):
        """Fetch a value and coerce to float using standard transform rules (returns None on invalid)."""
        raw_value = CsvCache.get_safe_value_from_index(columns, index)
        return get_safe_float(raw_value)

    @staticmethod
    def get_safe_int_from_index(columns, index):
        """Fetch a value and coerce to int using standard transform rules (returns None on invalid)."""
        raw_value = CsvCache.get_safe_value_from_index(columns, index)
        return get_safe_int(raw_value)
