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

from shared.helpers.logger import get_logger


STOP_TIMES_FILE = "stop_times.txt"
SHAPES_FILE = "shapes.txt"
TRIPS_FILE = "trips.txt"
ROUTES_FILE = "routes.txt"
STOPS_FILE = "stops.txt"
AGENCY_FILE = "agency.txt"
class Shapes(TypedDict):
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
        self.trip_to_stops = None
        self.route_to_trip = None
        self.route_to_shape: Dict[str, Dict[str, List[str]]] = None
        self.stop_to_route = None
        self.stop_to_coordinates = None
        self.trips_no_shapes = Dict[str, List[str]]

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

    def get_trip_from_route(self, route_id):
        if self.route_to_trip is None:
            self.route_to_trip = {}
            for row in self.get_file(TRIPS_FILE):
                route_id = row["route_id"]
                trip_id = row["trip_id"]
                if trip_id:
                    if self.route_to_trip.get(route_id):
                        self.route_to_trip[route_id] = trip_id
                    else:
                        self.route_to_trip.setdefault(route_id, trip_id)
        return self.route_to_trip.get(route_id, "")

    def get_shape_from_route(self, route_id) -> str:
        """
        Returns the first shape_id associated with a given route_id from the trips file.
        The relationship from the route to the shape is via the trips file.
        Parameters:
            route_id (str): The route identifier to look up.

        Returns:
            The corresponding shape id.
        """
        if self.route_to_shape is None:
            self.route_to_shape = {}
            for row in self.get_file(TRIPS_FILE):
                route_id = row["route_id"]
                shape_id = row["shape_id"]
                trip_id = row["trip_id"]
                if route_id and trip_id:
                    if shape_id:
                        route_shapes = self.route_to_shape.get(route_id, {})
                        if shape_id not in route_shapes:
                            route_shapes[shape_id] = []
                        route_shapes[shape_id].append(trip_id)
                        self.route_to_shape[route_id] = route_shapes
                    else:
                        trip_no_shapes = self.trip_to_stops.get(route_id, [])
                        trip_no_shapes.append(trip_id)
                        self.trips_no_shapes[route_id] = trip_no_shapes
        return self.route_to_shape.get(route_id, [])

    def get_trips_without_shape_from_route(self, route_id) -> List[str]:
        return self.trips_no_shapes[route_id] if route_id in self.trips_no_shapes else []

    def get_stops_from_trip(self, trip_id):
        # Lazy instantiation of the dictionary, because we may not need it al all if there is a shape.
        if self.trip_to_stops is None:
            self.trip_to_stops = {}
            for row in self.get_file(STOP_TIMES_FILE):
                self.trip_to_stops.setdefault(row["trip_id"], []).append(row["stop_id"])
        return self.trip_to_stops.get(trip_id, [])

    def get_coordinates_for_stop(self, stop_id) -> tuple[float, float] | None:
        if self.stop_to_coordinates is None:
            self.stop_to_coordinates = {
                s["stop_id"]: (float(s["stop_lon"]), float(s["stop_lat"]))
                for s in self.get_file(STOPS_FILE)
            }
        return self.stop_to_coordinates.get(stop_id, None)

    def set_workdir(self, workdir):
        self.workdir = workdir
