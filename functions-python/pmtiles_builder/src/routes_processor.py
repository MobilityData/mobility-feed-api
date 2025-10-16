import csv
import json
from typing import TextIO, Dict, List

from csv_cache import ROUTES_FILE, ShapeTrips
from fast_csv_parser import FastCsvParser
from shared.helpers.logger import get_logger
from shared.helpers.utils import detect_encoding

from route_coordinates import RouteCoordinates


class RoutesProcessor:
    def __init__(
        self,
        csv_cache,
        shapes_index=None,
        agencies=None,
        logger=None,
    ):
        # Use a dict for agencies to safely .get()
        self.agencies = agencies if agencies else {}
        self.csv_cache = csv_cache
        if logger:
            self.logger = logger
        else:
            self.logger = get_logger(RoutesProcessor.__name__)
        self.shapes_index = shapes_index
        # Track routes missing coordinates in a set
        self.missing_coordinates_routes = set()
        self.features_count = 0
        self.route_colors_map = {}
        self.trips_processor = None
        self.stops_processor = None
        self.stop_times_processor = None

    def load_routes_colors(self):
        filepath = self.csv_cache.get_path(ROUTES_FILE)
        csv_parser = FastCsvParser()
        encoding = detect_encoding(filename=filepath, logger=self.logger)

        with open(filepath, "r", encoding=encoding, newline="") as f:
            header = f.readline()
            if not header:
                return
            columns = next(csv.reader([header]))

            route_id_index = self.csv_cache.get_index(columns, "route_id")
            route_color_index = self.csv_cache.get_index(columns, "route_color")

            for line in f:
                if not line.strip():
                    continue

                row = csv_parser.parse(line)
                route_id = self.csv_cache.get_safe_value_from_index(row, route_id_index)
                route_color = self.csv_cache.get_safe_value_from_index(
                    row, route_color_index
                )

                if route_id:
                    self.route_colors_map[route_id] = route_color

    def process(
        self,
        trips_processor=None,
        stops_processor=None,
        stop_times_processor=None,
    ):
        self.trips_processor = trips_processor
        self.stops_processor = stops_processor
        self.stop_times_processor = stop_times_processor
        filepath = self.csv_cache.get_path(ROUTES_FILE)
        csv_parser = FastCsvParser()
        encoding = detect_encoding(filename=filepath, logger=self.logger)

        routes_geojson = self.csv_cache.get_path("routes-output.geojson")

        with open(routes_geojson, "w", encoding="utf-8") as geojson_file:
            geojson_file.write('{"type": "FeatureCollection", "features": [')
            csv_cache = self.csv_cache
            with open(filepath, "r", encoding=encoding, newline="") as f:
                header = f.readline()
                if not header:
                    return
                columns = next(csv.reader([header]))

                route_id_index = csv_cache.get_index(columns, "route_id")
                agency_id_index = csv_cache.get_index(columns, "agency_id")
                route_short_name_index = csv_cache.get_index(
                    columns, "route_short_name"
                )
                route_long_name_index = csv_cache.get_index(columns, "route_long_name")
                route_type_index = csv_cache.get_index(columns, "route_type")
                route_text_color_index = csv_cache.get_index(
                    columns, "route_text_color"
                )
                route_color_index = csv_cache.get_index(columns, "route_color")

                line_number = 1
                for line in f:
                    if not line.strip():
                        continue

                    row = csv_parser.parse(line)
                    route_id = csv_cache.get_safe_value_from_index(row, route_id_index)
                    agency_id = csv_cache.get_safe_value_from_index(
                        row, agency_id_index, "default"
                    )
                    route_short_name = csv_cache.get_safe_value_from_index(
                        row, route_short_name_index
                    )
                    route_long_name = csv_cache.get_safe_value_from_index(
                        row, route_long_name_index
                    )
                    route_type = csv_cache.get_safe_value_from_index(
                        row, route_type_index
                    )
                    route_color = csv_cache.get_safe_value_from_index(
                        row, route_color_index
                    )
                    route_text_color = csv_cache.get_safe_value_from_index(
                        row, route_text_color_index
                    )

                    # Pass all parsed values to add_to_routes_geojson
                    self.add_to_routes_geojson(
                        geojson_file=geojson_file,
                        route_id=route_id,
                        agency_id=agency_id,
                        route_short_name=route_short_name,
                        route_long_name=route_long_name,
                        route_type=route_type,
                        route_color=route_color,
                        route_text_color=route_text_color,
                    )
                if line_number % 100 == 0 or line_number == 1:
                    self.logger.debug(
                        "Processed route %d (route_id: %s)", line_number, route_id
                    )

            geojson_file.write("\n]}")
            # Clear the different caches to save memory. They are currently not used anywhere else.
            # self.csv_cache.clear_coordinate_for_stops()
            # self.csv_cache.clear_shape_from_route()
            # # self.csv_cache.clear_stops_from_trip()
            # self.csv_cache.clear_trip_from_route()

        if self.missing_coordinates_routes:
            self.logger.info(
                "Routes without coordinates: %s", list(self.missing_coordinates_routes)
            )
        self.logger.debug(
            "Wrote %d features to routes-output.geojson", self.features_count
        )

    def add_to_routes_colors_map(self, route_id, route_color):
        if route_id:
            self.route_colors_map[route_id] = route_color

    def add_to_routes_geojson(
        self,
        geojson_file: TextIO,
        route_id: str,
        agency_id: str,
        route_short_name: str,
        route_long_name: str,
        route_type: str,
        route_color: str,
        route_text_color: str,
    ):
        agency_name = self.agencies.get(agency_id, agency_id)
        self.logger.debug("Processing route_id %s", route_id)
        trips_coordinates: list[RouteCoordinates] = self.get_route_coordinates(
            route_id, self.shapes_index
        )

        if not trips_coordinates:
            self.missing_coordinates_routes.add(route_id)
            return

        for trip_coordinates in trips_coordinates:
            trip_ids = trip_coordinates["trip_ids"]
            shape_id = trip_coordinates["shape_id"]
            feature = {
                "type": "Feature",
                "properties": {
                    "agency_name": agency_name,
                    "route_id": route_id,
                    "shape_id": shape_id,
                    "trip_ids": trip_ids,
                    "route_short_name": route_short_name or "",
                    "route_long_name": route_long_name or "",
                    "route_type": route_type or "",
                    "route_color": route_color or "",
                    "route_text_color": route_text_color or "",
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": trip_coordinates["coordinates"],
                },
            }
            if self.features_count != 0:
                geojson_file.write(",\n")
            geojson_file.write(json.dumps(feature))
            self.features_count += 1

    def get_route_coordinates(self, route_id, shapes_index) -> List[RouteCoordinates]:
        shapes: Dict[str, ShapeTrips] = self.trips_processor.get_shape_from_route(
            route_id
        )
        result: List[RouteCoordinates] = []
        if shapes:
            for shape_id, trip_ids in shapes.items():
                # shape_id = shape["shape_id"]
                # trip_ids = shape["trip_ids"]
                coordinates = self._get_shape_points(shape_id)
                if coordinates:
                    result.append(
                        {
                            "shape_id": shape_id,
                            "trip_ids": trip_ids.get("trip_ids", []),
                            "coordinates": coordinates,
                        }
                    )

        trips_without_shape = self.trips_processor.trips_no_shapes_per_route.get(
            route_id, []
        )

        if trips_without_shape:
            # One feature per canonical trip ID
            canonical_trip_id_to_feature: Dict[str, RouteCoordinates] = {}
            for trip_id in trips_without_shape:
                # Determine canonical trip: if aliased, map to its canonical; else itself
                canonical_id = (
                    self.stop_times_processor.get_trip_alias(trip_id) or trip_id
                )

                feature = canonical_trip_id_to_feature.get(canonical_id)
                if feature is None:
                    # Build coordinates once for the canonical trip
                    stops_for_trip = self.stop_times_processor.get_stops_from_trip(
                        canonical_id
                    )
                    if not stops_for_trip:
                        self.logger.info(
                            "No stops found for trip_id %s on route_id %s",
                            canonical_id,
                            route_id,
                        )
                        continue

                    coordinates = [
                        coord
                        for stop_id in stops_for_trip
                        if (
                            coord := self.stops_processor.get_coordinates_for_stop(
                                stop_id
                            )
                        )
                        is not None
                    ]
                    if not coordinates:
                        self.logger.info(
                            "Coordinates do not have the right formatting for stops of trip_id %s on route_id %s",
                            canonical_id,
                            route_id,
                        )
                        continue

                    feature = {
                        "shape_id": "",
                        "trip_ids": [canonical_id],
                        "coordinates": coordinates,
                    }
                    canonical_trip_id_to_feature[canonical_id] = feature
                    result.append(feature)

                # Append the current trip_id if it's an alias (different from canonical)
                if trip_id != canonical_id:
                    feature["trip_ids"].append(trip_id)

        return result

    def _get_shape_points(self, shape_id):
        """Retrieve shape points for a given shape_id using the provided index.
        Args:
            shape_id (str): The shape_id to retrieve points for.
            index (ShapesIndex): The index to use for retrieval.
        Returns:
            List of (lon, lat) tuples representing the shape points.
        """
        # Log only on first call and every 1,000,000 calls
        # self._get_shape_points_calls += 1
        # count = self._get_shape_points_calls
        # if count == 1 or (count % 1_000_000 == 0):
        #     self.logger.debug(
        #         "Getting shape points (called #%d times) for shape_id %s",
        #         count,
        #         shape_id,
        #     )
        return self.shapes_index.get_objects(shape_id)
