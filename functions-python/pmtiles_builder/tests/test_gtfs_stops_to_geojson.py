import unittest
import tempfile
import os
import json

from csv_cache import CsvCache, ROUTES_FILE, TRIPS_FILE, STOP_TIMES_FILE, STOPS_FILE
from gtfs_stops_to_geojson import convert_stops_to_geojson


class TestGtfsStopsToGeoJson(unittest.TestCase):
    def setUp(self):
        # Minimal GTFS-like data
        stops = [
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
        stop_times = [
            {"trip_id": "t1", "stop_id": "1"},
            {"trip_id": "t2", "stop_id": "2"},
        ]
        trips = [
            {"trip_id": "t1", "route_id": "r1"},
            {"trip_id": "t2", "route_id": "r2"},
        ]
        routes = [
            {"route_id": "r1", "route_color": "FF0000"},
            {"route_id": "r2", "route_color": "00FF00"},
        ]
        self.csv_cache = CsvCache("./workdir")
        self.csv_cache.add_data(STOPS_FILE, stops)
        self.csv_cache.add_data(STOP_TIMES_FILE, stop_times)
        self.csv_cache.add_data(TRIPS_FILE, trips)
        self.csv_cache.add_data(ROUTES_FILE, routes)

    def test_convert_stops_to_geojson(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "stops.geojson")
            convert_stops_to_geojson(self.csv_cache, output_file)
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
        csv_cache = CsvCache()
        csv_cache.add_data(STOPS_FILE, bad_stops)
        csv_cache.add_data(ROUTES_FILE, {})
        csv_cache.add_data(STOP_TIMES_FILE, {})
        csv_cache.add_data(TRIPS_FILE, {})
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "bad.geojson")
            convert_stops_to_geojson(csv_cache, output_file)
            with open(output_file) as f:
                geojson = json.load(f)
            self.assertEqual(len(geojson["features"]), 0)
