import csv
import json
from typing import TextIO, Dict, List

from agencies_processor import AgenciesProcessor
from csv_cache import ROUTES_FILE, ShapeTrips

from base_processor import BaseProcessor
from route_coordinates import RouteCoordinates
from routes_processor_for_colors import RoutesProcessorForColors
from shapes_processor import ShapesProcessor
from stop_times_processor import StopTimesProcessor
from stops_processor import StopsProcessor
from trips_processor import TripsProcessor


class RoutesProcessor(BaseProcessor):
    def __init__(
        self,
        csv_cache,
        logger=None,
        agencies_processor: AgenciesProcessor = None,
        shapes_processor: ShapesProcessor = None,
        trips_processor: TripsProcessor = None,
        stops_processor: StopsProcessor = None,
        stop_times_processor: StopTimesProcessor = None,
        routes_processor_for_colors: RoutesProcessorForColors = None,
    ):
        super().__init__(ROUTES_FILE, csv_cache, logger, no_download=True)
        # Track routes missing coordinates in a set
        self.missing_coordinates_routes = set()
        self.geojson_features_count = 0
        self.json_file_items_count = 0
        self.agencies_processor: AgenciesProcessor | None = agencies_processor
        self.trips_processor: TripsProcessor | None = trips_processor
        self.shapes_processor: ShapesProcessor | None = shapes_processor
        self.stops_processor: StopsProcessor | None = stops_processor
        self.stop_times_processor: StopTimesProcessor | None = stop_times_processor
        self.routes_processor_for_colors: RoutesProcessorForColors | None = (
            routes_processor_for_colors
        )

    def process_file(self):
        csv_cache = self.csv_cache

        routes_geojson = csv_cache.get_path("routes-output.geojson")
        routes_json = csv_cache.get_path("routes.json")

        with open(routes_geojson, "w", encoding="utf-8") as geojson_file, open(
            routes_json, "w", encoding="utf-8"
        ) as routes_json_file:
            geojson_file.write('{"type": "FeatureCollection", "features": [\n')
            routes_json_file.write("[\n")
            with open(self.filepath, "r", encoding=self.encoding, newline="") as f:
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

                    row = self.csv_parser.parse(line)
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

                    self.add_to_routes_json(
                        routes_json_file=routes_json_file,
                        route_id=route_id,
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
            routes_json_file.write("\n]")

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
            "Wrote %d features to routes-output.geojson", self.geojson_features_count
        )

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
        agency_name = self.agencies_processor.agencies.get(agency_id, agency_id)
        # self.logger.debug("Processing route_id %s", route_id)
        trips_coordinates: list[RouteCoordinates] = self.get_route_coordinates(route_id)

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

            # Dumping each feature separately to a string ensures it's pretty printed.
            feature_json = json.dumps(feature, ensure_ascii=False, indent=4)

            if self.geojson_features_count != 0:
                geojson_file.write(",\n")
            geojson_file.write(feature_json)
            self.geojson_features_count += 1

    def add_to_routes_json(
        self,
        routes_json_file: TextIO,
        route_id: str,
        route_short_name: str,
        route_long_name: str,
        route_type: str,
        route_color: str,
        route_text_color: str,
    ):
        route = {
            "routeId": route_id,
            "routeName": route_long_name or route_short_name or route_id,
            "color": f"#{route_color}" if route_color else "#000000",
            "textColor": f"#{route_text_color}" if route_text_color else "#FFFFFF",
            "routeType": route_type or "",
        }

        # Since we are printing part of the file "manually" (the [ at the beginning, , the commas, etc),
        # dumping a json object in the file will not format (or pretty print) the object.
        # To have the object formatted, first dump it to a string, then print the string "manually".
        route_json = json.dumps(route, ensure_ascii=False, indent=4)

        if self.json_file_items_count != 0:
            routes_json_file.write(",\n")
        self.json_file_items_count += 1
        routes_json_file.write(route_json)

    def get_route_coordinates(self, route_id) -> List[RouteCoordinates]:
        shapes: Dict[str, ShapeTrips] = self.trips_processor.get_shape_from_route(
            route_id
        )
        result: List[RouteCoordinates] = []
        if shapes:
            for shape_id, trip_ids in shapes.items():
                # shape_id = shape["shape_id"]
                # trip_ids = shape["trip_ids"]
                coordinates = self.shapes_processor.get_shape_points(shape_id)
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
            # The aliases go in the list of trip_ids for that feature along with the canonical trip_id
            canonical_trip_id_to_feature: Dict[str, RouteCoordinates] = {}
            for trip_id in trips_without_shape:
                # Determine canonical trip: if aliased, map to its canonical; else itself
                canonical_trip_id = (
                    self.stop_times_processor.get_trip_alias(trip_id) or trip_id
                )

                feature = canonical_trip_id_to_feature.get(canonical_trip_id)
                if feature is None:
                    # Build coordinates once for the canonical trip
                    stops_for_trip = self.stop_times_processor.get_stops_from_trip(
                        canonical_trip_id
                    )
                    if not stops_for_trip:
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
                            canonical_trip_id,
                            route_id,
                        )
                        continue

                    feature = {
                        "shape_id": "",
                        "trip_ids": [canonical_trip_id],
                        "coordinates": coordinates,
                    }
                    canonical_trip_id_to_feature[canonical_trip_id] = feature
                    result.append(feature)

                # Append the current trip_id if it's an alias (different from canonical)
                if trip_id != canonical_trip_id:
                    feature["trip_ids"].append(trip_id)

        return result
