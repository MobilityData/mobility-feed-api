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
import os
from typing import TypedDict, List, Dict


from gtfs import stop_txt_is_lat_log_required
from shared.helpers.logger import get_logger
from shared.helpers.transform import get_safe_value, get_safe_float

STOP_TIMES_FILE = "stop_times.txt"
SHAPES_FILE = "shapes.txt"
TRIPS_FILE = "trips.txt"
ROUTES_FILE = "routes.txt"
STOPS_FILE = "stops.txt"
AGENCY_FILE = "agency.txt"


class ShapeTrips(TypedDict):
    shape_id: str
    trip_ids: List[str]


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
        self.route_to_shape: Dict[str, Dict[str, ShapeTrips]] = None
        self.stop_to_route = None
        self.stop_to_coordinates = None
        self.trips_no_shapes_per_route: Dict[str, List[str]] = {}

        self.logger.info("Using work directory: %s", self.workdir)

    def get_path(self, filename: str) -> str:
        return os.path.join(self.workdir, filename)

    def get_file(self, filename) -> list[dict]:
        if self.file_data.get(filename) is None:
            self.file_data[filename] = self._read_csv(self.get_path(filename))
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
            with open(filename, newline="", encoding="utf-8") as f:
                return list(csv.DictReader(f))
        except Exception as e:
            raise Exception(f"Failed to read CSV file {filename}: {e}") from e

    def get_shape_from_route(self, route_id) -> Dict[str, List[ShapeTrips]]:
        """
        Returns a list of shape_ids with associated trip_ids information with a given route_id from the trips file.
        The relationship from the route to the shape is via the trips file.
        Parameters:
            route_id (str): The route identifier to look up.

        Returns:
            The corresponding shape id.
            Example return value: [{'shape_id1': { 'shape_id': 'shape_id1', 'trip_ids': ['trip1', 'trip2']}},
             {'shape_id': 'shape_id2', 'trip_ids': ['trip3']}}]
        """
        if self.route_to_shape is None:
            self.route_to_shape = {}
            for row in self.get_file(TRIPS_FILE):
                route_id = get_safe_value(row, "route_id")
                shape_id = get_safe_value(row, "shape_id")
                trip_id = get_safe_value(row, "trip_id")
                if route_id and trip_id:
                    if shape_id:
                        route_shapes = self.route_to_shape.setdefault(route_id, {})
                        shape_trips = route_shapes.setdefault(
                            shape_id, {"shape_id": shape_id, "trip_ids": []}
                        )
                        shape_trips["trip_ids"].append(trip_id)
                    else:
                        # Registering the trip without a shape for this route for later retrieval.
                        trip_no_shapes = (
                            self.trips_no_shapes_per_route.get(route_id)
                            if route_id in self.trips_no_shapes_per_route
                            else None
                        )
                        if trip_no_shapes is None:
                            trip_no_shapes = []
                            self.trips_no_shapes_per_route[route_id] = trip_no_shapes
                        trip_no_shapes.append(trip_id)
        return self.route_to_shape.get(route_id, {})

    def get_trips_without_shape_from_route(self, route_id) -> List[str]:
        return self.trips_no_shapes_per_route.get(route_id, [])

    def get_stops_from_trip(self, trip_id):
        if self.trip_to_stops is None:
            self.trip_to_stops = {}
            for row in self.get_file(STOP_TIMES_FILE):
                trip_id = get_safe_value(row, "trip_id")
                stop_id = get_safe_value(row, "stop_id")
                if trip_id and stop_id:
                    trip_to_stops = (
                        self.trip_to_stops.get(trip_id)
                        if trip_id in self.trip_to_stops
                        else None
                    )
                    if trip_to_stops is None:
                        trip_to_stops = []
                        self.trip_to_stops[trip_id] = trip_to_stops
                    trip_to_stops.append(stop_id)
        return self.trip_to_stops.get(trip_id, [])

    def get_coordinates_for_stop(self, stop_id) -> tuple[float, float] | None:
        if self.stop_to_coordinates is None:
            self.stop_to_coordinates = {}
            for s in self.get_file(STOPS_FILE):
                self.stop_to_coordinates.get(stop_id, [])
                row_stop_id = get_safe_value(s, "stop_id")
                row_stop_lon = get_safe_float(s, "stop_lon")
                row_stop_lat = get_safe_float(s, "stop_lat")
                if row_stop_id is None:
                    self.logger.warning("Missing stop id: %s", s)
                    continue
                if row_stop_lon is None or row_stop_lat is None:
                    if stop_txt_is_lat_log_required(s):
                        self.logger.warning(
                            "Missing stop latitude and longitude : %s", s
                        )
                    else:
                        self.logger.debug(
                            "Missing optional stop latitude and longitude : %s", s
                        )
                    continue
                self.stop_to_coordinates[row_stop_id] = (row_stop_lon, row_stop_lat)
        return self.stop_to_coordinates.get(stop_id, None)

    def set_workdir(self, workdir):
        self.workdir = workdir
