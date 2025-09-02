import unittest
import tempfile
import os
import json
from gtfs_stops_to_geojson import (
    load_routes,
    build_stop_to_routes,
    convert_stops_to_geojson,
)


class TestGtfsStopsToGeoJson(unittest.TestCase):
    def setUp(self):
        # Minimal GTFS-like data
        self.stops = [
            {
                "stop_id": "1",
                "stop_lat": "40.0",
                "stop_lon": "-75.0",
                "stop_name": "Stop 1",
            },
            {
                "stop_id": "2",
                "stop_lat": "41.0",
                "stop_lon": "-76.0",
                "stop_name": "Stop 2",
            },
            {"stop_id": "3", "stop_lat": "", "stop_lon": "", "stop_name": "NoCoords"},
        ]
        self.stop_times = [
            {"trip_id": "t1", "stop_id": "1"},
            {"trip_id": "t2", "stop_id": "2"},
        ]
        self.trips = [
            {"trip_id": "t1", "route_id": "r1"},
            {"trip_id": "t2", "route_id": "r2"},
        ]
        self.routes = [
            {"route_id": "r1", "route_color": "FF0000"},
            {"route_id": "r2", "route_color": "00FF00"},
        ]

    def test_load_routes(self):
        routes_map = load_routes(self.routes)
        self.assertIn("r1", routes_map)
        self.assertEqual(routes_map["r1"]["route_color"], "FF0000")

    def test_build_stop_to_routes(self):
        stop_to_routes = build_stop_to_routes(self.stop_times, self.trips)
        self.assertEqual(stop_to_routes["1"], {"r1"})
        self.assertEqual(stop_to_routes["2"], {"r2"})

    def test_convert_stops_to_geojson(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "stops.geojson")
            convert_stops_to_geojson(
                self.stops, self.stop_times, self.trips, self.routes, output_file
            )
            with open(output_file) as f:
                geojson = json.load(f)
            self.assertEqual(geojson["type"], "FeatureCollection")
            self.assertEqual(len(geojson["features"]), 2)  # skips stop with no coords
            props = geojson["features"][0]["properties"]
            self.assertIn("stop_id", props)
            self.assertIn("route_ids", props)
            self.assertIn("route_colors", props)

    def test_convert_stops_to_geojson_invalid_coords(self):
        bad_stops = [{"stop_id": "4", "stop_lat": "bad", "stop_lon": "bad"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "bad.geojson")
            convert_stops_to_geojson(
                bad_stops, self.stop_times, self.trips, self.routes, output_file
            )
            with open(output_file) as f:
                geojson = json.load(f)
            self.assertEqual(len(geojson["features"]), 0)
