import csv
import json
import argparse
from collections import defaultdict
from geojson import Feature, FeatureCollection, LineString

def read_gtfs_file(file_path):
    """Reads a GTFS file and returns a list of dictionaries."""
    with open(file_path, mode='r', encoding='utf-8-sig') as file:
        return list(csv.DictReader(file))

def build_shapes(shapes_file):
    """Parses shapes.txt and returns a dictionary of shape_id -> ordered coordinates."""
    shapes = defaultdict(list)
    for row in read_gtfs_file(shapes_file):
        shape_id = row['shape_id']
        lat, lon = float(row['shape_pt_lat']), float(row['shape_pt_lon'])
        sequence = int(row['shape_pt_sequence'])
        shapes[shape_id].append((sequence, lon, lat))
    
    for shape_id in shapes:
        shapes[shape_id].sort()  # Sort by shape_pt_sequence
        shapes[shape_id] = [(lon, lat) for _, lon, lat in shapes[shape_id]]
    
    return shapes

def generate_geojson(routes_file, trips_file, shapes_file, output_file):
    """Generates a GeoJSON file from GTFS routes, trips, and shapes."""
    routes = {row['route_id']: row for row in read_gtfs_file(routes_file)}
    trips = read_gtfs_file(trips_file)
    shapes = build_shapes(shapes_file)
    
    route_shapes = defaultdict(set)
    for trip in trips:
        if 'shape_id' in trip and trip['shape_id']:
            route_shapes[trip['route_id']].add(trip['shape_id'])
    
    features = []
    for route_id, shape_ids in route_shapes.items():
        for shape_id in shape_ids:
            if shape_id in shapes:
                feature = Feature(
                    geometry=LineString(shapes[shape_id]),
                    properties={
                        'route_id': route_id,
                        'route_short_name': routes[route_id].get('route_short_name', ''),
                        'route_long_name': routes[route_id].get('route_long_name', ''),
                        'route_type': routes[route_id].get('route_type', ''),
                        'route_color': routes[route_id].get('route_color', '#000000')
                    }
                )
                features.append(feature)
    
    geojson = FeatureCollection(features)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, indent=2)
    
    print(f"GeoJSON file saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert GTFS files to GeoJSON.")
    parser.add_argument("routes_file", help="Path to routes.txt")
    parser.add_argument("trips_file", help="Path to trips.txt")
    parser.add_argument("shapes_file", help="Path to shapes.txt")
    parser.add_argument("output_file", help="Path to output GeoJSON file")
    
    args = parser.parse_args()
    
    generate_geojson(args.routes_file, args.trips_file, args.shapes_file, args.output_file)