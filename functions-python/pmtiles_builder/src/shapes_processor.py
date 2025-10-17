import collections
import csv
import os
import psutil

import numpy as np

from csv_cache import SHAPES_FILE
from fast_csv_parser import FastCsvParser
from shared.helpers.logger import get_logger
from shared.helpers.runtime_metrics import track_metrics
from shared.helpers.utils import detect_encoding


class ShapesProcessor:
    def __init__(
        self,
        csv_cache,
        logger=None,
    ):
        # Use a dict for agencies to safely .get()
        self.csv_cache = csv_cache
        if logger:
            self.logger = logger
        else:
            self.logger = get_logger(ShapesProcessor.__name__)

        self.coordinates_arrays: dict[
            str, tuple[np.ndarray, np.ndarray, np.ndarray]
        ] = {}
        self.unique_shape_id_counts = collections.Counter()

    def process(self):
        csv_cache = self.csv_cache
        filepath = csv_cache.get_path(SHAPES_FILE)
        csv_parser = FastCsvParser()
        line_count = 0

        process = psutil.Process(os.getpid())

        try:
            encoding = detect_encoding(filename=filepath, logger=self.logger)
            with open(filepath, "r", encoding=encoding, newline="") as f:
                header = f.readline()
                if not header:
                    return
                columns = next(csv.reader([header]))
                shape_id_index = csv_cache.get_index(columns, "shape_id")
                lon_idx = csv_cache.get_index(columns, "shape_pt_lon")
                lat_idx = csv_cache.get_index(columns, "shape_pt_lat")
                seq_idx = csv_cache.get_index(columns, "shape_pt_sequence")

                for line in f:
                    try:
                        if not line.strip():
                            continue

                        row = csv_parser.parse(line)

                        shape_id = csv_cache.get_safe_value_from_index(
                            row, shape_id_index
                        )

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
                            f"Skipping line {line_count} of shapes.txt in first pass because of error: {e}"
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

                        row = csv_parser.parse(line)
                        shape_id = self.csv_cache.get_safe_value_from_index(
                            row, shape_id_index
                        )

                        position = positions_in_coordinates_arrays[shape_id]
                        lon_arr, lat_arr, seq_arr = self.coordinates_arrays[shape_id]
                        lon_arr[position] = csv_cache.get_safe_float_from_index(
                            row, lon_idx
                        )
                        lat_arr[position] = csv_cache.get_safe_float_from_index(
                            row, lat_idx
                        )
                        seq_value = csv_cache.get_safe_int_from_index(row, seq_idx)
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
                            f"Skipping line {line_count} of shapes.txt in 2nd pass because of error: {e}"
                        )
                if needs_sorting:
                    self.sort_coordinate_arrays()

            if csv_parser.lines_with_quotes > 0:
                self.logger.debug(
                    f"Found {csv_parser.lines_with_quotes} lines with quotes while creating shapes index"
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

    def get_shape_points(self, shape_in: str):
        """Return a tuple of (lon, lat, seq) for a given shape_in (empty tuple if missing)."""
        lon_array, lat_array, seq_array = self.coordinates_arrays.get(
            shape_in, (np.array([]), np.array([]), np.array([]))
        )
        return np.column_stack((lon_array, lat_array)).tolist()
