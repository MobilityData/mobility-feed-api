import unittest
import tempfile
import os
import json
from unittest.mock import patch
from pmtiles_builder.src import gtfs_stops_to_geojson


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
        routes_map = gtfs_stops_to_geojson.load_routes(self.routes)
        self.assertIn("r1", routes_map)
        self.assertEqual(routes_map["r1"]["route_color"], "FF0000")

    def test_build_stop_to_routes(self):
        stop_to_routes = gtfs_stops_to_geojson.build_stop_to_routes(
            self.stop_times, self.trips
        )
        self.assertEqual(stop_to_routes["1"], {"r1"})
        self.assertEqual(stop_to_routes["2"], {"r2"})

    def test_convert_stops_to_geojson(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "stops.geojson")
            gtfs_stops_to_geojson.convert_stops_to_geojson(
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
            gtfs_stops_to_geojson.convert_stops_to_geojson(
                bad_stops, self.stop_times, self.trips, self.routes, output_file
            )
            with open(output_file) as f:
                geojson = json.load(f)
            self.assertEqual(len(geojson["features"]), 0)

    def test_empty_inputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "empty.geojson")
            gtfs_stops_to_geojson.convert_stops_to_geojson([], [], [], [], output_file)
            with open(output_file) as f:
                geojson = json.load(f)
            self.assertEqual(len(geojson["features"]), 0)

    def test_main_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stops_file = os.path.join(tmpdir, "stops.txt")
            stop_times_file = os.path.join(tmpdir, "stop_times.txt")
            trips_file = os.path.join(tmpdir, "trips.txt")
            routes_file = os.path.join(tmpdir, "routes.txt")
            output_file = os.path.join(tmpdir, "output.geojson")

            with open(stops_file, "w") as f:
                f.write("stop_id,stop_name,stop_lat,stop_lon\n")
                f.write("s1,stop1,45.5,-73.6\n")

            for f_path in [stop_times_file, trips_file, routes_file]:
                with open(f_path, "w") as f:
                    pass  # create empty files

            with patch(
                "sys.argv",
                [
                    "gtfs_stops_to_geojson.py",
                    stops_file,
                    stop_times_file,
                    trips_file,
                    routes_file,
                    output_file,
                ],
            ):
                with self.assertRaises(SystemExit) as cm:
                    gtfs_stops_to_geojson.main()
                self.assertEqual(cm.exception.code, 0)

            with open(output_file) as f:
                geojson = json.load(f)
            self.assertEqual(len(geojson["features"]), 1)

    def test_main_entrypoint_invalid_args(self):
        with patch("sys.argv", ["gtfs_stops_to_geojson.py"]):
            with self.assertRaises(SystemExit) as cm:
                gtfs_stops_to_geojson.main()
            self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
