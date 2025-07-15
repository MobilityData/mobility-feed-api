import csv
import json
import argparse
import sys
from collections import defaultdict
from geojson import Feature, FeatureCollection, LineString

# ----------------------------
# Utility readers
# ----------------------------

def read_csv(filepath):
    """Generator that reads a CSV row-by-row as dict."""
    with open(filepath, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row

# ----------------------------
# Agency Loader
# ----------------------------

def load_agencies(agency_file):
    agencies = {}
    default_agency_name = ''
    for row in read_csv(agency_file):
        agency_id = row.get('agency_id') or 'default'
        agency_name = row.get('agency_name', '').strip()
        agencies[agency_id] = agency_name
        if not default_agency_name:
            default_agency_name = agency_name

    if not agencies and default_agency_name:
        agencies['default'] = default_agency_name

    return agencies

# ----------------------------
# Route Loader
# ----------------------------

def load_routes(routes_file):
    routes = {}
    for row in read_csv(routes_file):
        route_id = row.get('route_id')
        if not route_id:
            continue  # skip broken routes
        routes[route_id] = row
    return routes

# ----------------------------
# Shape Loader
# ----------------------------

def load_shapes(shapes_file):
    shapes = defaultdict(list)
    for row in read_csv(shapes_file):
        shape_id = row.get('shape_id')
        try:
            lat = float(row['shape_pt_lat'])
            lon = float(row['shape_pt_lon'])
            seq = int(row['shape_pt_sequence'])
        except (KeyError, ValueError):
            continue  # skip bad rows

        shapes[shape_id].append((seq, lon, lat))

    # Sort shape points
    final_shapes = {}
    for sid, points in shapes.items():
        points.sort()
        final_shapes[sid] = [(lon, lat) for _, lon, lat in points]

    return final_shapes

# ----------------------------
# Route -> Shape mapping
# ----------------------------

def build_route_shapes(trips_file):
    mapping = defaultdict(set)
    for row in read_csv(trips_file):
        route_id = row.get('route_id')
        shape_id = row.get('shape_id')
        if route_id and shape_id:
            mapping[route_id].add(shape_id)
    return mapping

# ----------------------------
# Main converter
# ----------------------------

def generate_geojson(routes_file, trips_file, shapes_file, agency_file, output_file):
    agencies = load_agencies(agency_file)
    routes = load_routes(routes_file)
    shapes = load_shapes(shapes_file)
    route_shapes = build_route_shapes(trips_file)

    features = []

    for route_id, shape_ids in route_shapes.items():
        route = routes.get(route_id)
        if not route:
            continue

        agency_id = route.get('agency_id') or 'default'
        agency_name = agencies.get(agency_id, '')

        for shape_id in shape_ids:
            shape = shapes.get(shape_id)
            if not shape:
                print(f"Warning: shape_id {shape_id} not found for route_id {route_id}", file=sys.stderr)
                continue

            feature = Feature(
                geometry=LineString(shape),
                properties={
                    'agency_name': agency_name,
                    'route_id': route_id,
                    'route_short_name': route.get('route_short_name', ''),
                    'route_long_name': route.get('route_long_name', ''),
                    'route_type': route.get('route_type', ''),
                    'route_color': route.get('route_color', '#000000'),
                    'route_text_color': route.get('route_text_color', '#FFFFFF')
                }
            )
            features.append(feature)

    geojson = FeatureCollection(features)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, indent=2)
    
    print(f"✅ GeoJSON written to {output_file} with {len(features)} features")

# ----------------------------
# CLI
# ----------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert GTFS routes to GeoJSON.")
    parser.add_argument("routes_file")
    parser.add_argument("trips_file")
    parser.add_argument("shapes_file")
    parser.add_argument("agency_file")
    parser.add_argument("output_file")
    args = parser.parse_args()

    generate_geojson(
        args.routes_file,
        args.trips_file,
        args.shapes_file,
        args.agency_file,
        args.output_file
    )
