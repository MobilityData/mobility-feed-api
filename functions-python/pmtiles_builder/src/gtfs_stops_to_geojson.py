import json
import logging

from csv_cache import CsvCache, ROUTES_FILE, STOPS_FILE
from gtfs import stop_txt_is_lat_lon_required
from shared.helpers.runtime_metrics import track_metrics
from shared.helpers.transform import get_safe_float_from_csv, get_safe_value_from_csv

logger = logging.getLogger(__name__)


def create_routes_map(routes_data):
    """Creates a dictionary of routes from route data."""
    routes = {}
    for row in routes_data:
        route_id = get_safe_value_from_csv(row, "route_id")
        if route_id:
            routes[route_id] = row
    return routes


# def build_stop_to_routes(stop_times_data, trips_data):
#     """Builds a mapping from stop_id to a set of route_ids."""
#     # Build trip_id -> route_id mapping
#     trip_to_route = {}
#     for row in trips_data:
#         trip_id = get_safe_value_from_csv(row, "trip_id")
#         route_id = get_safe_value_from_csv(row, "route_id")
#         if trip_id and route_id:
#             trip_to_route[trip_id] = route_id
#
#     # Build stop_id -> set of route_ids
#     stop_to_routes = defaultdict(set)
#     for row in stop_times_data:
#         trip_id = get_safe_value_from_csv(row, "trip_id")
#         stop_id = get_safe_value_from_csv(row, "stop_id")
#         if trip_id and stop_id:
#             route_id = trip_to_route.get(trip_id)
#             if route_id:
#                 stop_to_routes[stop_id].add(route_id)
#
#     return stop_to_routes


@track_metrics(metrics=("time", "memory", "cpu"))
def convert_stops_to_geojson(csv_cache: CsvCache, output_file):
    """Converts GTFS stops data to a GeoJSON file."""
    routes_map = create_routes_map(csv_cache.get_file(ROUTES_FILE))
    stop_to_routes = csv_cache.stop_to_routes

    csv_cache.debug_log_size(
        f"stops_to_route length {len(stop_to_routes)}", stop_to_routes
    )

    features = []
    for row in csv_cache.get_file(STOPS_FILE):
        stop_id = row.get("stop_id")
        if not stop_id:
            continue

        if (
            "stop_lat" not in row
            or "stop_lon" not in row
            or get_safe_float_from_csv(row, "stop_lat") is None
            or get_safe_float_from_csv(row, "stop_lon") is None
        ):
            if stop_txt_is_lat_lon_required(row):
                logger.warning(
                    "Missing coordinates for stop_id {%s}, skipping.", stop_id
                )
            continue

        # Routes serving this stop
        route_ids = sorted(stop_to_routes.get(stop_id, []))
        route_colors = [
            routes_map[r].get("route_color", "") for r in route_ids if r in routes_map
        ]

        try:
            stop_lon = float(row["stop_lon"])
            stop_lat = float(row["stop_lat"])
        except (ValueError, TypeError):
            logger.warning(f"Invalid coordinates for stop_id {stop_id}, skipping.")
            continue

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [stop_lon, stop_lat],
            },
            "properties": {
                "stop_id": stop_id,
                "stop_code": get_safe_value_from_csv(row, "stop_code", ""),
                "stop_name": get_safe_value_from_csv(row, "stop_name", ""),
                "stop_desc": get_safe_value_from_csv(row, "stop_desc", ""),
                "zone_id": get_safe_value_from_csv(row, "zone_id", ""),
                "stop_url": get_safe_value_from_csv(row, "stop_url", ""),
                "wheelchair_boarding": get_safe_value_from_csv(
                    row, "wheelchair_boarding", ""
                ),
                "location_type": get_safe_value_from_csv(row, "location_type", ""),
                "route_ids": route_ids,
                "route_colors": route_colors,
            },
        }
        features.append(feature)

    geojson = {"type": "FeatureCollection", "features": features}
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2, ensure_ascii=False)
    logger.info(f"✅ GeoJSON file saved to {output_file} with {len(features)} stops")
