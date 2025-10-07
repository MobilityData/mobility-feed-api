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
# This module provides the PmtilesBuilder class and related functions to generate PMTiles files
# from GTFS datasets. It handles downloading required files from Google Cloud Storage, processing
# and indexing GTFS data, generating GeoJSON and JSON outputs, running Tippecanoe to create PMTiles,
# and uploading the results back to GCS.

import csv
import os

import numpy as np
import logging

import psutil

from shared.helpers.transform import get_safe_value, get_safe_float, get_safe_int
from shared.helpers.utils import detect_encoding
from shared.helpers.runtime_metrics import track_metrics


class ShapesIndex:
    def __init__(
        self,
        file_path: str,
        shape_id_column_name: str,
        coordinates_columns: list[str],
        logger=None,
    ):
        self.coordinates_arrays: dict[
            str, tuple[np.ndarray, np.ndarray, np.ndarray]
        ] = {}
        self.file_path = file_path
        self.shape_id_column_name = shape_id_column_name
        self.coordinates_columns = coordinates_columns
        self.unique_shape_id_counts = None
        self.lines_with_quotes = 0
        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger(ShapesIndex.__name__)  # pragma: no cover

    def build_index(self) -> None:
        """
        Build the index from the CSV file.
        This method reads the CSV file twice:
        1. First pass: counts occurrences of each unique key to determine array sizes.
        2. Second pass: fills preallocated numpy arrays with coordinate data.
        numpy arrays are more memory efficient and faster for numerical data and using them allows
        cutting the memory requirements in a major way.
        """
        import collections

        process = psutil.Process(os.getpid())

        self.unique_shape_id_counts = collections.Counter()
        line_count = 0

        try:
            encoding = detect_encoding(filename=self.file_path, logger=self.logger)
            with open(self.file_path, "r", encoding=encoding, newline="") as f:
                header = f.readline()
                if not header:
                    return
                columns = next(csv.reader([header]))
                shape_id_index = columns.index(self.shape_id_column_name)
                for line in f:
                    try:
                        if not line.strip():
                            continue

                        row = self.fast_csv_parse(line)

                        shape_id = get_safe_value(row[shape_id_index])
                        self.unique_shape_id_counts[shape_id] += 1
                        line_count += 1
                        if line_count % 1_000_000 == 0:
                            mem_mb = process.memory_info().rss / (
                                1024 * 1024
                            )  # pragma: no cover
                            self.logger.debug(
                                f"ShapesIndex Processed 1st pass {line_count} lines. "
                                f"Process memory (MB): {mem_mb}"
                            )  # pragma: no cover
                    except Exception as e:
                        self.logger.warning(
                            f"Skipping line {line_count} of shapes.txt because of error: {e}"
                        )

                # Preallocate arrays for each key
                self.coordinates_arrays = {
                    key: (
                        np.zeros(count, dtype=np.float32),  # lon
                        np.zeros(count, dtype=np.float32),  # lat
                        np.zeros(count, dtype=np.int32),  # sequence_number
                    )
                    for key, count in self.unique_shape_id_counts.items()
                }

                # Second pass: fill arrays
                lon_idx = columns.index("shape_pt_lon")
                lat_idx = columns.index("shape_pt_lat")
                seq_idx = columns.index("shape_pt_sequence")
                positions_in_coordinates_arrays = {
                    key: 0 for key in self.unique_shape_id_counts
                }

                f.seek(0)
                line_count = 0
                f.readline()  # Skip header
                needs_sorting = False
                for line in f:
                    try:
                        if not line.strip():
                            continue

                        row = self.fast_csv_parse(line)
                        shape_id = row[shape_id_index]
                        position = positions_in_coordinates_arrays[shape_id]
                        lon_arr, lat_arr, seq_arr = self.coordinates_arrays[shape_id]
                        lon_arr[position] = get_safe_float(row[lon_idx])
                        lat_arr[position] = get_safe_float(row[lat_idx])
                        seq_value = get_safe_int(row[seq_idx])
                        seq_arr[position] = seq_value

                        # If any sequence number goes down, set needs_sorting True.
                        # Just a little low hanging optimization so we don't sort for nothing.
                        if (
                            not needs_sorting
                            and position > 0
                            and seq_value < seq_arr[position - 1]
                        ):
                            needs_sorting = True

                        positions_in_coordinates_arrays[shape_id] = position + 1

                        line_count += 1
                        if line_count % 1_000_000 == 0:
                            mem_mb = process.memory_info().rss / (
                                1024 * 1024
                            )  # pragma: no cover
                            self.logger.debug(
                                f"ShapesIndex Processed 2nd pass {line_count} lines. "
                                f"Process memory (MB): {mem_mb}"
                            )  # pragma: no cover

                    except Exception as e:
                        self.logger.warning(
                            f"Skipping line {line_count} of shapes.txt because of error: {e}"
                        )
                if needs_sorting:
                    self.sort_coordinate_arrays()

            if self.lines_with_quotes > 0:
                self.logger.debug(
                    f"Found {self.lines_with_quotes} lines with quotes while creating shapes index"
                )
        except Exception as e:
            self.logger.warning("Cannot read shapes file: %s", e)

    @track_metrics(metrics=("time", "memory", "cpu"))
    def sort_coordinate_arrays(self):
        """
        Sorts the coordinate arrays in-place for each shape_id according to the sequence number.
        """
        for key, (lon_arr, lat_arr, seq_arr) in self.coordinates_arrays.items():
            sort_idx = np.argsort(seq_arr)
            lon_arr[:] = lon_arr[sort_idx]
            lat_arr[:] = lat_arr[sort_idx]
            seq_arr[:] = seq_arr[sort_idx]

    def get_objects(self, key: str):
        """Return a list of objects for rows matching key, using row_fn or raw row dicts."""
        return self.get_shape_points(key)

    def get_shape_points(self, key: str):
        """Return a tuple of (lon, lat) for a given key (empty tuple if missing)."""
        lon_array, lat_array, seq_array = self.coordinates_arrays.get(
            key, (np.array([]), np.array([]), np.array([]))
        )
        return np.column_stack((lon_array, lat_array)).tolist()

    def fast_csv_parse(self, line: str):  # pragma: no cover
        """
        A fast CSV parser that handles lines with and without quotes and quoted commas.
        Uses csv.reader for lines with quotes, otherwise splits by comma.
        This is a performance optimization to avoid the overhead of csv.reader
        for simple lines without quotes.
        """
        if '"' in line:
            self.lines_with_quotes += 1
            # Use csv.reader for quoted fields
            return next(csv.reader([line]))
        else:
            # Fast path for simple lines
            return line.rstrip("\r\n").split(",")
