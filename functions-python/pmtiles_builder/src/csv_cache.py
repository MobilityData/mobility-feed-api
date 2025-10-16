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
import csv
import logging
import os
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import TypedDict, List, Dict, Optional

from fast_csv_parser import FastCsvParser
from gtfs import stop_txt_is_lat_log_required
from pympler import asizeof

from shared.helpers.logger import get_logger
from shared.helpers.transform import get_safe_value, get_safe_float
from shared.helpers.utils import detect_encoding

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
        self.trip_to_stops: Dict[str, List[str]] = None
        self.route_to_trip = None
        self.route_to_shape: Dict[str, Dict[str, ShapeTrips]] = {}
        self.stop_to_coordinates = {}
        self.trips_no_shapes_per_route: Dict[str, List[str]] = {}
        self.trip_to_route = {}
        self.stop_to_routes = defaultdict(set)

        # Canonical trip_id -> list of stop_ids (only one entry kept per unique sequence)
        self._trip_to_stops: Optional[Dict[str, List[str]]] = None
        # Alias mapping for duplicates: duplicate trip_id -> canonical trip_id
        self._trip_same_as: Optional[Dict[str, str]] = None

        # self.routes_processor = RoutesProcessor(self)
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

    def get_file(self, filename) -> list[dict]:
        if self.file_data.get(filename) is None:
            self.file_data[filename] = self._read_csv(self.get_path(filename))
            self.debug_log_size(f"file data for {filename}", self.file_data[filename])
        return self.file_data[filename]

    def add_data(self, filename: str, data: list[dict]):
        self.file_data[filename] = data

    def _read_csv(self, filename) -> list[dict]:
        """
        Reads the content of a CSV file and returns it as a list of dictionaries
        where each dictionary represents a row.

        Parameters:
        filename (str): The file path of the CSV file to be read.

        Raises:
        Exception: If there is an error during file opening or reading. The raised
        exception will include the original error message along with the file name.

        Returns:
        list[dict]: A list of dictionaries, each representing a row in the CSV file.
        """
        try:
            self.logger.debug("Loading %s", filename)
            encoding = detect_encoding(filename, logger=self.logger)
            with open(filename, newline="", encoding=encoding) as f:
                return list(csv.DictReader(f))
        except Exception as e:
            raise Exception(f"Failed to read CSV file {filename}: {e}") from e

    def clear_trip_from_route(self):
        self.route_to_trip = None

    def get_shape_from_route(self, route_id) -> Dict[str, ShapeTrips]:
        """
        Returns a list of shape_ids with associated trip_ids information with a given route_id from the trips file.
        The relationship from the route to the shape is via the trips file.
        Parameters:
            route_id(str): The route identifier to look up.

        Returns:
            The corresponding shape id.
            Example return value: [{'shape_id1': { 'shape_id': 'shape_id1', 'trip_ids': ['trip1', 'trip2']}},
             {'shape_id': 'shape_id2', 'trip_ids': ['trip3']}}]
        """
        return self.route_to_shape.get(route_id, {})

    def clear_shape_from_route(self):
        self.route_to_shape = None

    def get_trips_without_shape_from_route(self, route_id) -> List[str]:
        return self.trips_no_shapes_per_route.get(route_id, [])

    def get_stops_from_trip(self, trip_id):
        if self.is_trip_aliased(trip_id):
            return None
        else:
            return self._trip_to_stops.get(trip_id)

    def get_coordinates_for_stop(self, stop_id) -> tuple[float, float] | None:
        # if self.stop_to_coordinates is None:
        #     self._build_stop_to_coordinates()
        return self.stop_to_coordinates.get(stop_id, None)

    def clear_coordinate_for_stops(self):
        self.stop_to_coordinates = None

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
            else None
        )

    @staticmethod
    def get_safe_float_from_index(columns, index):
        raw_value = CsvCache.get_safe_value_from_index(columns, index)
        return get_safe_float(raw_value)

    def load_trips(self):
        filepath = self.get_path(TRIPS_FILE)
        csv_parser = FastCsvParser()
        encoding = detect_encoding(filename=filepath, logger=self.logger)
        with open(filepath, "r", encoding=encoding, newline="") as f:
            header = f.readline()
            if not header:
                return
            columns = next(csv.reader([header]))
            route_id_index = self.get_index(columns, "route_id")
            trip_id_index = self.get_index(columns, "trip_id")
            shape_id_index = self.get_index(columns, "shape_id")

            for line in f:
                if not line.strip():
                    continue

                row = csv_parser.parse(line)

                route_id = self.get_safe_value_from_index(row, route_id_index)
                trip_id = self.get_safe_value_from_index(row, trip_id_index)
                shape_id = self.get_safe_value_from_index(row, shape_id_index)

                if route_id and trip_id:
                    if shape_id:
                        route_shapes = self.route_to_shape.setdefault(route_id, {})
                        shape_trips = route_shapes.setdefault(
                            shape_id, {"shape_id": shape_id, "trip_ids": []}
                        )
                        shape_trips["trip_ids"].append(trip_id)
                    else:
                        # Register the trip without a shape for this route.
                        trip_no_shapes = self.trips_no_shapes_per_route.setdefault(
                            route_id, []
                        )
                        trip_no_shapes.append(trip_id)

                # Build trip_id -> route_id mapping
                if trip_id and route_id:
                    self.trip_to_route[trip_id] = route_id

    def load_stop_times(self):
        trip_to_stops: Dict[str, List[str]] = {}

        # Build stop_id -> set of route_ids
        filepath = self.get_path(STOP_TIMES_FILE)
        csv_parser = FastCsvParser()
        encoding = detect_encoding(filename=filepath, logger=self.logger)
        with open(filepath, "r", encoding=encoding, newline="") as f:
            header = f.readline()
            if not header:
                return
            columns = next(csv.reader([header]))

            stop_id_index = self.get_index(columns, "stop_id")
            trip_id_index = self.get_index(columns, "trip_id")

            for line in f:
                if not line.strip():
                    continue

                row = csv_parser.parse(line)

                stop_id = self.get_safe_value_from_index(row, stop_id_index)
                trip_id = self.get_safe_value_from_index(row, trip_id_index)
                if trip_id and stop_id:
                    trip_to_stops.setdefault(trip_id, []).append(stop_id)

                    route_id = self.trip_to_route.get(trip_id)
                    if route_id:
                        self.stop_to_routes[stop_id].add(route_id)

            if self.has_trips_without_route():
                canonical: Dict[str, List[str]] = {}
                aliases: Dict[str, str] = {}
                seq_key_to_canonical_trip: Dict[tuple, str] = {}

                for trip_id, stops in trip_to_stops.items():
                    key = tuple(stops)
                    if key in seq_key_to_canonical_trip:
                        can_trip = seq_key_to_canonical_trip[key]
                        aliases[trip_id] = can_trip
                        self.logger.debug(
                            "Trip %s has identical stops as canonical trip %s; alias recorded",
                            trip_id,
                            can_trip,
                        )
                    else:
                        seq_key_to_canonical_trip[key] = trip_id
                        canonical[trip_id] = stops

                self._trip_to_stops = canonical
                self._trip_same_as = aliases

    def has_trips_without_route(self):
        return bool(self.trips_no_shapes_per_route)

    def is_trip_aliased(self, trip_id: str) -> bool:
        """
        Returns True if the given trip_id has an alias entry in the internal
        _trip_same_as mapping, False otherwise.
        """
        return self._trip_same_as is not None and trip_id in self._trip_same_as

    def get_trip_alias(self, trip_id: str) -> str | None:
        """
        Return the direct canonical trip_id for an aliased trip.

        - If `trip_id` is present in `_trip_same_as`, returns its direct canonical trip_id.
        - If not aliased or the mapping is not built, returns None.
        - Does not resolve chained aliases.
        """
        mapping = self._trip_same_as
        if not mapping:
            return None
        return mapping.get(trip_id)

    def load_stops(self):
        # Build stop_id -> set of route_ids
        filepath = self.get_path(STOPS_FILE)
        csv_parser = FastCsvParser()
        encoding = detect_encoding(filename=filepath, logger=self.logger)
        with open(filepath, "r", encoding=encoding, newline="") as f:
            header = f.readline()
            if not header:
                return
            columns = next(csv.reader([header]))

            stop_id_index = self.get_index(columns, "stop_id")
            lon_index = self.get_index(columns, "stop_lon")
            lat_index = self.get_index(columns, "stop_lat")

            for line in f:
                if not line.strip():
                    continue

                row = csv_parser.parse(line)

                stop_id = self.get_safe_value_from_index(row, stop_id_index)
                stop_lon = self.get_safe_float_from_index(row, lon_index)
                stop_lat = self.get_safe_float_from_index(row, lat_index)

                if stop_id is None:
                    self.logger.warning("Missing stop id: %s", line)
                    continue
                if stop_lon is None or stop_lat is None:
                    if stop_txt_is_lat_log_required(f):
                        self.logger.warning(
                            "Missing stop latitude and longitude : %s", line
                        )
                    else:
                        self.logger.debug(
                            "Missing optional stop latitude and longitude : %s", line
                        )
                    continue
                self.stop_to_coordinates[stop_id] = (stop_lon, stop_lat)

            #     # From gtfs_stops_to_geojson
            #     # Routes serving this stop
            #     route_ids = sorted(stop_to_routes.get(stop_id, []))
            #     route_colors = [
            #         routes_map[r].get("route_color", "") for r in route_ids if r in routes_map
            #     ]
            #
            #     try:
            #         stop_lon = float(row["stop_lon"])
            #         stop_lat = float(row["stop_lat"])
            #     except (ValueError, TypeError):
            #         logger.warning(f"Invalid coordinates for stop_id {stop_id}, skipping.")
            #         continue
            #
            #     feature = {
            #         "type": "Feature",
            #         "geometry": {
            #             "type": "Point",
            #             "coordinates": [stop_lon, stop_lat],
            #         },
            #         "properties": {
            #             "stop_id": stop_id,
            #             "stop_code": get_safe_value_from_csv(row, "stop_code", ""),
            #             "stop_name": get_safe_value_from_csv(row, "stop_name", ""),
            #             "stop_desc": get_safe_value_from_csv(row, "stop_desc", ""),
            #             "zone_id": get_safe_value_from_csv(row, "zone_id", ""),
            #             "stop_url": get_safe_value_from_csv(row, "stop_url", ""),
            #             "wheelchair_boarding": get_safe_value_from_csv(
            #                 row, "wheelchair_boarding", ""
            #             ),
            #             "location_type": get_safe_value_from_csv(row, "location_type", ""),
            #             "route_ids": route_ids,
            #             "route_colors": route_colors,
            #         },
            #     }
            #     features.append(feature)
            #
            # geojson = {"type": "FeatureCollection", "features": features}
            # with open(output_file, "w", encoding="utf-8") as f:
            #     json.dump(geojson, f, indent=2, ensure_ascii=False)
            # logger.info(f"✅ GeoJSON file saved to {output_file} with {len(features)} stops")
