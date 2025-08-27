import csv
import json
import sys
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


def read_csv(filepath):
    """Reads a CSV file and yields each row as a dictionary."""
    with open(filepath, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def load_routes(routes_data):
    """Creates a dictionary of routes from route data."""
    routes = {}
    for row in routes_data:
        route_id = row.get("route_id")
        if route_id:
            routes[route_id] = row
    return routes


def build_stop_to_routes(stop_times_data, trips_data):
    """Builds a mapping from stop_id to a set of route_ids."""
    # Build trip_id -> route_id mapping
    trip_to_route = {}
    for row in trips_data:
        trip_id = row.get("trip_id")
        route_id = row.get("route_id")
        if trip_id and route_id:
            trip_to_route[trip_id] = route_id

    # Build stop_id -> set of route_ids
    stop_to_routes = defaultdict(set)
    for row in stop_times_data:
        trip_id = row.get("trip_id")
        stop_id = row.get("stop_id")
        if trip_id and stop_id:
            route_id = trip_to_route.get(trip_id)
            if route_id:
                stop_to_routes[stop_id].add(route_id)

    return stop_to_routes


def convert_stops_to_geojson(stops, stop_times, trips, routes, output_file):
    """Converts GTFS stops data to a GeoJSON file."""
    routes_map = load_routes(routes)
    stop_to_routes = build_stop_to_routes(stop_times, trips)

    features = []

    for row in stops:
        stop_id = row.get("stop_id")
        if not stop_id:
            continue

        if (
            "stop_lat" not in row
            or "stop_lon" not in row
            or not row["stop_lat"]
            or not row["stop_lon"]
        ):
            logger.warning(f"Missing coordinates for stop_id {stop_id}, skipping.")
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
                "stop_code": row.get("stop_code", ""),
                "stop_name": row.get("stop_name", ""),
                "stop_desc": row.get("stop_desc", ""),
                "zone_id": row.get("zone_id", ""),
                "stop_url": row.get("stop_url", ""),
                "wheelchair_boarding": row.get("wheelchair_boarding", ""),
                "location_type": row.get("location_type", ""),
                "route_ids": route_ids,
                "route_colors": route_colors,
            },
        }
        features.append(feature)

    geojson = {"type": "FeatureCollection", "features": features}

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2, ensure_ascii=False)

    logger.info(f"✅ GeoJSON file saved to {output_file} with {len(features)} stops")


if __name__ == "__main__":
    if len(sys.argv) != 6:
        logger.info(
            "Usage: python script.py stops stop_times trips routes output.geojson"
        )
        sys.exit(1)

    convert_stops_to_geojson(
        sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
    )
