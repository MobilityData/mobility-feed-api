import csv
from typing import Dict, List

from csv_cache import TRIPS_FILE, ShapeTrips
from fast_csv_parser import FastCsvParser
from shared.helpers.logger import get_logger
from shared.helpers.utils import detect_encoding


class TripsProcessor:
    """
    Streams trips.txt and populates on the provided csv_cache:
      - route_to_shape: Dict[route_id, Dict[shape_id, {shape_id, trip_ids[]}]]
      - trips_no_shapes_per_route: Dict[route_id, List[trip_id]]
      - trip_to_route: Dict[trip_id, route_id]
    """

    def __init__(self, csv_cache, logger=None):
        self.csv_cache = csv_cache
        self.logger = logger or get_logger(TripsProcessor.__name__)
        self.route_to_shape: Dict[str, Dict[str, ShapeTrips]] = {}
        self.trips_no_shapes_per_route: Dict[str, List[str]] = {}
        self.trip_to_route: Dict[str, str] = {}

    def has_trips_without_route(self):
        return bool(self.trips_no_shapes_per_route)

    def get_shape_from_route(self, route_id) -> Dict[str, ShapeTrips]:
        return self.route_to_shape.get(route_id, {})

    def process(self) -> None:
        filepath = self.csv_cache.get_path(TRIPS_FILE)
        csv_parser = FastCsvParser()
        encoding = detect_encoding(filename=filepath, logger=self.logger)
        with open(filepath, "r", encoding=encoding, newline="") as f:
            header = f.readline()
            if not header:
                return
            columns = next(csv.reader([header]))
            route_id_index = self.csv_cache.get_index(columns, "route_id")
            trip_id_index = self.csv_cache.get_index(columns, "trip_id")
            shape_id_index = self.csv_cache.get_index(columns, "shape_id")

            for line in f:
                if not line.strip():
                    continue

                row = csv_parser.parse(line)

                route_id = self.csv_cache.get_safe_value_from_index(row, route_id_index)
                trip_id = self.csv_cache.get_safe_value_from_index(row, trip_id_index)
                shape_id = self.csv_cache.get_safe_value_from_index(row, shape_id_index)

                # if route_id and trip_id:
                #     if shape_id:
                #         route_shapes = self.csv_cache.route_to_shape.setdefault(route_id, {})
                #         shape_trips = route_shapes.setdefault(
                #             shape_id, {"shape_id": shape_id, "trip_ids": []}
                #         )
                #         shape_trips["trip_ids"].append(trip_id)
                #     else:
                #         # Register the trip without a shape for this route.
                #         self.csv_cache.trips_no_shapes_per_route.setdefault(route_id, []).append(trip_id)
                self.add_to_route_to_shape(route_id, shape_id, trip_id)
                self.add_to_trip_to_route(trip_id, route_id)

    def add_to_trip_to_route(self, trip_id, route_id):
        if trip_id and route_id:
            self.trip_to_route[trip_id] = route_id

    def add_to_route_to_shape(self, route_id, shape_id, trip_id):
        if route_id and trip_id:
            if shape_id:
                route_shapes = self.route_to_shape.setdefault(route_id, {})
                shape_trips = route_shapes.setdefault(
                    shape_id, {"shape_id": shape_id, "trip_ids": []}
                )
                shape_trips["trip_ids"].append(trip_id)
            else:
                # Register the trip without a shape for this route.
                self.trips_no_shapes_per_route.setdefault(route_id, []).append(trip_id)
