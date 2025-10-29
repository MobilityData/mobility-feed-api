import os
import tempfile
import unittest
from unittest.mock import MagicMock

from csv_cache import CsvCache
from stops_processor import StopsProcessor


class DummyRoutesProcessorForColors:
    def __init__(self, route_colors_map):
        self.route_colors_map = route_colors_map


class DummyStopTimesProcessor:
    def __init__(self, stop_to_routes):
        # stop_id -> set(route_id)
        self.stop_to_routes = stop_to_routes


class TestStopsProcessor(unittest.TestCase):
    def test_process_writes_geojson_with_features(self):
        with tempfile.TemporaryDirectory() as td:
            csv_cache = CsvCache(workdir=td, logger=MagicMock())
            stops_path = csv_cache.get_path("stops.txt")

            # header must include stop_lon and stop_lat as StopsProcessor expects
            with open(stops_path, "w", encoding="utf-8") as f:
                f.write("stop_id,stop_lon,stop_lat,stop_name\n")
                f.write("stop1,-73.0,45.0,Stop 1\n")
                f.write("stop2,-73.1,45.1,Stop 2\n")

            # dummy supporting processors
            routes_colors = DummyRoutesProcessorForColors({"r1": "FF0000"})
            stop_times = DummyStopTimesProcessor({"stop1": {"r1"}, "stop2": set()})

            processor = StopsProcessor(
                csv_cache,
                logger=MagicMock(),
                routes_processor_for_colors=routes_colors,
                stop_times_processor=stop_times,
            )

            processor.process()

            out_path = csv_cache.get_path("stops-output.geojson")
            self.assertTrue(os.path.exists(out_path))
            with open(out_path, "r", encoding="utf-8") as fh:
                content = fh.read()

            self.assertIn("FeatureCollection", content)
            # basic checks: both stops present
            self.assertIn("stop1", content)
            self.assertIn("stop2", content)

            # load JSON and inspect structure
            import json

            data = json.loads(content)
            self.assertEqual(data.get("type"), "FeatureCollection")
            features = data.get("features", [])
            self.assertEqual(len(features), 2)

            # find stop1 feature and validate coordinates and properties
            stop1_feat = next(
                f for f in features if f.get("properties", {}).get("stop_id") == "stop1"
            )
            self.assertEqual(
                stop1_feat.get("geometry", {}).get("coordinates"), [-73.0, 45.0]
            )
            self.assertIn("route_colors", stop1_feat.get("properties", {}))
            self.assertEqual(
                stop1_feat.get("properties", {}).get("route_colors"), ["FF0000"]
            )

    def test_missing_coords_are_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            csv_cache = CsvCache(workdir=td, logger=MagicMock())
            stops_path = csv_cache.get_path("stops.txt")

            with open(stops_path, "w", encoding="utf-8") as f:
                f.write("stop_id,stop_lon,stop_lat,stop_name\n")
                # stop without coordinates
                f.write("stop_missing,,,NoCoords\n")
                f.write("stop_ok,-73.2,45.2,OK\n")

            routes_colors = DummyRoutesProcessorForColors({"r1": "FF0000"})
            stop_times = DummyStopTimesProcessor(
                {"stop_missing": {"r1"}, "stop_ok": {"r1"}}
            )

            processor = StopsProcessor(
                csv_cache,
                logger=MagicMock(),
                routes_processor_for_colors=routes_colors,
                stop_times_processor=stop_times,
            )

            processor.process()

            out_path = csv_cache.get_path("stops-output.geojson")
            self.assertTrue(os.path.exists(out_path))

            import json

            data = json.load(open(out_path, "r", encoding="utf-8"))
            features = data.get("features", [])
            # only stop_ok should be present
            ids = [f.get("properties", {}).get("stop_id") for f in features]
            self.assertIn("stop_ok", ids)
            self.assertNotIn("stop_missing", ids)


if __name__ == "__main__":
    unittest.main()
