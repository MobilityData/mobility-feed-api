import csv
import json
import sys
from collections import defaultdict


def read_csv(filepath):
    with open(filepath, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def load_routes(routes_file):
    routes = {}
    for row in read_csv(routes_file):
        route_id = row.get("route_id")
        if route_id:
            routes[route_id] = row
    return routes


def build_stop_to_routes(stop_times_file, trips_file):
    # Build trip_id -> route_id mapping
    trip_to_route = {}
    for row in read_csv(trips_file):
        trip_id = row.get("trip_id")
        route_id = row.get("route_id")
        if trip_id and route_id:
            trip_to_route[trip_id] = route_id

    # Build stop_id -> set of route_ids
    stop_to_routes = defaultdict(set)
    for row in read_csv(stop_times_file):
        trip_id = row.get("trip_id")
        stop_id = row.get("stop_id")
        if trip_id and stop_id:
            route_id = trip_to_route.get(trip_id)
            if route_id:
                stop_to_routes[stop_id].add(route_id)

    return stop_to_routes


def convert_stops_to_geojson(
    stops_file, stop_times_file, trips_file, routes_file, output_file
):
    routes = load_routes(routes_file)
    stop_to_routes = build_stop_to_routes(stop_times_file, trips_file)

    features = []

    for row in read_csv(stops_file):
        stop_id = row.get("stop_id")
        if not stop_id:
            continue

        if (
            "stop_lat" not in row
            or "stop_lon" not in row
            or not row["stop_lat"]
            or not row["stop_lon"]
        ):
            continue  # skip bad coordinates

        # Routes serving this stop
        route_ids = sorted(stop_to_routes.get(stop_id, []))
        route_colors = [
            routes[r].get("route_color", "#000000") for r in route_ids if r in routes
        ]

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(row["stop_lon"]), float(row["stop_lat"])],
            },
            "properties": {
                "stop_id": stop_id,
                "stop_code": row.get("stop_code", ""),
                "stop_name": row.get("stop_name", ""),
                "stop_desc": row.get("stop_desc", ""),
                "zone_id": row.get("zone_id", ""),
                "stop_url": row.get("stop_url", ""),
                "wheelchair_boarding": row.get("wheelchair_boarding", ""),
                # "stop_lat": row.get("stop_lat"),
                # "stop_lon": row.get("stop_lon"),
                "location_type": row.get("location_type", ""),
                "route_ids": route_ids,
                "route_colors": route_colors,
            },
        }
        features.append(feature)

    geojson = {"type": "FeatureCollection", "features": features}

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2, ensure_ascii=False)

    print(f"✅ GeoJSON file saved to {output_file} with {len(features)} stops")


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print(
            "Usage: python script.py stops.txt stop_times.txt trips.txt routes.txt output.geojson"
        )
        sys.exit(1)

    convert_stops_to_geojson(
        sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
    )
