import csv
import json
from typing import TextIO

from base_processor import BaseProcessor
from csv_cache import STOPS_FILE
from gtfs import stop_txt_is_lat_lon_required, is_lat_lon_required
from routes_processor_for_colors import RoutesProcessorForColors
from stop_times_processor import StopTimesProcessor


class StopsProcessor(BaseProcessor):
    def __init__(
        self,
        csv_cache,
        logger=None,
        routes_processor_for_colors: RoutesProcessorForColors = None,
        stop_times_processor: StopTimesProcessor = None,
    ):
        super().__init__(STOPS_FILE, csv_cache, logger)
        self.routes_processor_for_colors = routes_processor_for_colors
        self.stop_times_processor = stop_times_processor
        self.stop_to_coordinates = {}
        self.features_count = 0

    def process_file(self) -> None:
        stops_geojson = self.csv_cache.get_path("stops-output.geojson")

        with open(stops_geojson, "w", encoding="utf-8") as geojson_file:
            geojson_file.write('{"type": "FeatureCollection", "features": [')
            csv_cache = self.csv_cache
            with open(self.filepath, "r", encoding=self.encoding, newline="") as f:
                header = f.readline()
                if not header:
                    return
                columns = next(csv.reader([header]))
                stop_id_index = csv_cache.get_index(columns, "stop_id")
                lon_index = csv_cache.get_index(columns, "stop_lon")
                lat_index = csv_cache.get_index(columns, "stop_lat")
                location_type_index = csv_cache.get_index(columns, "location_type")
                stop_code_index = csv_cache.get_index(columns, "stop_code")
                stop_name_index = csv_cache.get_index(columns, "stop_name")

                stop_desc_index = csv_cache.get_index(columns, "stop_desc")
                stop_url_index = csv_cache.get_index(columns, "stop_url")
                zone_id_index = csv_cache.get_index(columns, "zone_id")
                wheelchair_boarding_index = csv_cache.get_index(
                    columns, "wheelchair_boarding"
                )

                for line in f:
                    if not line.strip():
                        continue
                    row = self.csv_parser.parse(line)
                    stop_id = csv_cache.get_safe_value_from_index(row, stop_id_index)
                    stop_lon = csv_cache.get_safe_float_from_index(row, lon_index)
                    stop_lat = csv_cache.get_safe_float_from_index(row, lat_index)
                    location_type = csv_cache.get_safe_value_from_index(
                        row, location_type_index, ""
                    )
                    stop_code = csv_cache.get_safe_value_from_index(
                        row, stop_code_index, ""
                    )
                    stop_name = csv_cache.get_safe_value_from_index(
                        row, stop_name_index, ""
                    )
                    stop_desc = csv_cache.get_safe_value_from_index(
                        row, stop_desc_index, ""
                    )
                    zone_id = csv_cache.get_safe_value_from_index(
                        row, zone_id_index, ""
                    )
                    stop_url = csv_cache.get_safe_value_from_index(
                        row, stop_url_index, ""
                    )
                    wheelchair_boarding = csv_cache.get_safe_value_from_index(
                        row, wheelchair_boarding_index, ""
                    )

                    self.add_to_stop_to_coordinates(line, stop_id, stop_lon, stop_lat)

                    self.add_to_stops_geojson(
                        geojson_file=geojson_file,
                        stop_id=stop_id,
                        stop_code=stop_code,
                        stop_name=stop_name,
                        stop_desc=stop_desc,
                        zone_id=zone_id,
                        stop_url=stop_url,
                        wheelchair_boarding=wheelchair_boarding,
                        location_type=location_type,
                        stop_lon=stop_lon,
                        stop_lat=stop_lat,
                    )
                geojson_file.write("\n]}")

    def add_to_stop_to_coordinates(self, line, stop_id, stop_lon, stop_lat):
        if stop_id is None:
            self.logger.warning("Missing stop id: %s", line)
            return
        if stop_lon is None or stop_lat is None:
            if stop_txt_is_lat_lon_required(line):
                self.logger.warning("Missing stop latitude and longitude : %s", line)
            else:
                self.logger.debug(
                    "Missing optional stop latitude and longitude : %s", line
                )
            return
        self.stop_to_coordinates[stop_id] = (stop_lon, stop_lat)

    def add_to_stops_geojson(
        self,
        geojson_file: TextIO,
        stop_id: str,
        stop_code: str = "",
        stop_name: str = "",
        stop_desc: str = "",
        zone_id: str = "",
        stop_url: str = "",
        wheelchair_boarding: str = "",
        location_type: str = "",
        stop_lon: float = 0.0,
        stop_lat: float = 0.0,
    ) -> None:
        if stop_lon is None or stop_lat is None:
            if is_lat_lon_required(location_type):
                self.logger.warning(
                    "Missing coordinates for stop_id {%s}, skipping.", stop_id
                )
                return

        route_ids = sorted(self.stop_times_processor.stop_to_routes.get(stop_id, []))
        route_colors = [
            self.routes_processor_for_colors.route_colors_map[r]
            for r in route_ids
            if r in self.routes_processor_for_colors.route_colors_map
        ]

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [stop_lon, stop_lat],
            },
            "properties": {
                "stop_id": stop_id,
                "stop_code": stop_code,
                "stop_name": stop_name,
                "stop_desc": stop_desc,
                "zone_id": zone_id,
                "stop_url": stop_url,
                "wheelchair_boarding": wheelchair_boarding,
                "location_type": location_type,
                "route_ids": route_ids,
                "route_colors": route_colors,
            },
        }

        # Dumping each feature separately to a string ensures it's pretty printed.
        feature_json = json.dumps(feature, ensure_ascii=False, indent=4)

        if self.features_count != 0:
            geojson_file.write(",\n")
        geojson_file.write(feature_json)
        self.features_count += 1

    def get_coordinates_for_stop(self, stop_id) -> tuple[float, float] | None:
        return self.stop_to_coordinates.get(stop_id, None)
