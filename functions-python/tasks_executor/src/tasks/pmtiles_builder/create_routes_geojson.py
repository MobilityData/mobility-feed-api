# Here’s how to integrate the indexed shape lookup into your full GeoJSON route creation script.
# This version loads shapes_index.pkl once, uses it for fast shape lookups, and prints progress.
import csv
import json
import pickle
import logging


def read_csv(filename):
    print(f"Loading {filename}...")
    with open(filename, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def get_shape_points(shape_id, index, local_dir):
    points = []
    shapes_file = f"{local_dir}/shapes.txt"
    with open(shapes_file, "r", encoding="utf-8") as f:
        for pos in index.get(shape_id, []):
            f.seek(pos)
            line = f.readline()
            row = dict(zip(index["columns"], next(csv.reader([line]))))
            points.append(
                (
                    float(row["shape_pt_lon"]),
                    float(row["shape_pt_lat"]),
                    int(row["shape_pt_sequence"]),
                )
            )
    points.sort(key=lambda x: x[2])
    print(f"  Found {len(points)} points for shape_id {shape_id}")
    return [pt[:2] for pt in points]


def create_routes_geojson(local_dir):
    logging.info("Loading shapes_index.pkl...")
    shapes_index_file = f"{local_dir}/shapes_index.pkl"
    shapes_file = f"{local_dir}/shapes.txt"
    trips_file = f"{local_dir}/trips.txt"
    routes_file = f"{local_dir}/routes.txt"
    stops_file = f"{local_dir}/stops.txt"
    stop_times_file = f"{local_dir}/stop_times.txt"
    with open(shapes_index_file, "rb") as idxf:
        shapes_index = pickle.load(idxf)
    logging.info(f"Loaded index for {len(shapes_index)} shape_ids.")

    # Read header columns for shapes.txt (needed for manual parsing)
    with open(shapes_file, "r", encoding="utf-8") as f:
        header = f.readline()
        shapes_columns = next(csv.reader([header]))
    shapes_index["columns"] = shapes_columns

    routes = {r["route_id"]: r for r in read_csv(routes_file)}
    logging.info(f"Loaded {len(routes)} routes.")

    trips = list(read_csv(trips_file))
    logging.info(f"Loaded {len(trips)} trips.")

    stops = {
        s["stop_id"]: (float(s["stop_lon"]), float(s["stop_lat"]))
        for s in read_csv(stops_file)
    }
    logging.info(f"Loaded {len(stops)} stops.")

    stop_times_by_trip = {}
    print("Grouping stop_times by trip_id...")
    with open(stop_times_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stop_times_by_trip.setdefault(row["trip_id"], []).append(row)
    logging.info(f"Grouped stop_times for {len(stop_times_by_trip)} trips.")

    features = []
    for i, (route_id, route) in enumerate(routes.items(), 1):
        if i % 100 == 0 or i == 1:
            logging.info(
                f"Processing route {i}/{len(routes)} (route_id: {route_id})..."
            )
        trip = next((t for t in trips if t["route_id"] == route_id), None)
        if not trip:
            logging.info(f"  No trip found for route_id {route_id}, skipping.")
            continue
        coordinates = []
        if "shape_id" in trip and trip["shape_id"]:
            logging.info(f"  Using shape_id {trip['shape_id']} for route_id {route_id}")
            coordinates = get_shape_points(trip["shape_id"], shapes_index, local_dir)
        if not coordinates:
            trip_stop_times = stop_times_by_trip.get(trip["trip_id"], [])
            trip_stop_times.sort(key=lambda x: int(x["stop_sequence"]))
            coordinates = [
                stops[st["stop_id"]] for st in trip_stop_times if st["stop_id"] in stops
            ]
            logging.info(
                f"  Used {len(coordinates)} stop coordinates for route_id {route_id}"
            )
        if not coordinates:
            logging.info(f"  No coordinates found for route_id {route_id}, skipping.")
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {k: route[k] for k in route},
                "geometry": {"type": "LineString", "coordinates": coordinates},
            }
        )

    logging.info(f"Writing {len(features)} features to routes-output.geojson...")
    routes_geojson = f"{local_dir}/routes-output.geojson"
    with open(routes_geojson, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f)
    logging.info("Done.")
