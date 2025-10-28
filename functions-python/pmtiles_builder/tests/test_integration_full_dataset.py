import os
import tempfile
import json
import unittest
from unittest.mock import patch, MagicMock

from main import PmtilesBuilder
from csv_cache import CsvCache


class TestIntegrationFullDataset(unittest.TestCase):
    def setUp(self):
        # create temp workdir for each test
        self.td = tempfile.TemporaryDirectory()
        self.workdir = self.td.name
        # ensure builder uses local files and doesn't attempt DB/GCS
        os.environ["NO_GCS"] = "true"
        os.environ["NO_DATABASE"] = "true"

    def tearDown(self):
        self.td.cleanup()
        for v in ("NO_GCS", "NO_DATABASE"):
            if v in os.environ:
                del os.environ[v]

    @patch("main.subprocess.run")
    def test_dataset_with_shape_and_color_and_stops_fallback(self, mock_run):
        # Simulate tippecanoe success
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ok"
        mock_run.return_value = mock_result

        # Prepare simple GTFS files
        csv_cache = CsvCache(workdir=self.workdir, logger=MagicMock())
        # agencies.txt
        with open(csv_cache.get_path("agency.txt"), "w", encoding="utf-8") as f:
            f.write("agency_id,agency_name\n")
            f.write("ag1,Agency One\n")

        # routes.txt: r1 with color and r2 without shape (to be built from stops)
        with open(csv_cache.get_path("routes.txt"), "w", encoding="utf-8") as f:
            f.write(
                "route_id,agency_id,route_long_name,route_color,route_text_color,route_type\n"
            )
            f.write("r1,ag1,Route One,00FF00,FFFFFF,3\n")
            f.write("r2,ag1,Route Two,FF0000,000000,3\n")

        # shapes.txt: s1 for r1
        with open(csv_cache.get_path("shapes.txt"), "w", encoding="utf-8") as f:
            f.write("shape_id,shape_pt_lon,shape_pt_lat,shape_pt_sequence\n")
            f.write("s1,-73.0,45.0,1\n")
            f.write("s1,-73.1,45.1,2\n")

        # trips.txt: t1 uses shape s1 on r1; tA and tB have no shape on r2
        with open(csv_cache.get_path("trips.txt"), "w", encoding="utf-8") as f:
            f.write("route_id,trip_id,shape_id\n")
            f.write("r1,t1,s1\n")
            f.write("r2,tA,\n")
            f.write("r2,tB,\n")

        # stops.txt: s1,s2 used for tA/tB fallback
        with open(csv_cache.get_path("stops.txt"), "w", encoding="utf-8") as f:
            f.write("stop_id,stop_lat,stop_lon\n")
            f.write("sA,45.0,-73.0\n")
            f.write("sB,45.1,-73.1\n")

        # stop_times.txt: map tA and tB to same stop sequence (so tB becomes alias)
        with open(csv_cache.get_path("stop_times.txt"), "w", encoding="utf-8") as f:
            f.write("trip_id,stop_sequence,stop_id\n")
            f.write("tA,1,sA\n")
            f.write("tA,2,sB\n")
            # tB inverted order to ensure sorting/aliasing works
            f.write("tB,2,sB\n")
            f.write("tB,1,sA\n")

        # create builder and run build_pmtiles
        builder = PmtilesBuilder(
            feed_stable_id="feedX", dataset_stable_id="feedX_ds1", workdir=self.workdir
        )
        # ensure no uploads
        builder.upload_to_gcs = False
        builder.download_from_gcs = False
        builder.use_database = False

        status, message = builder.build_pmtiles()
        self.assertEqual(status.name, "SUCCESS")

        # Validate outputs exist
        geojson_path = csv_cache.get_path("routes-output.geojson")
        json_path = csv_cache.get_path("routes.json")
        self.assertTrue(os.path.exists(geojson_path))
        self.assertTrue(os.path.exists(json_path))

        with open(geojson_path, "r", encoding="utf-8") as fh:
            gj = json.load(fh)
        self.assertEqual(gj.get("type"), "FeatureCollection")
        features = gj.get("features", [])
        # Expect two features: one for r1 (shape) and one for r2 (stops fallback)
        self.assertEqual(len(features), 2)

        # find r1 / shape feature
        f_r1 = next(
            (f for f in features if f.get("properties", {}).get("route_id") == "r1"),
            None,
        )
        self.assertIsNotNone(f_r1)
        self.assertEqual(f_r1.get("properties", {}).get("shape_id"), "s1")

        # find r2 fallback feature
        f_r2 = next(
            (f for f in features if f.get("properties", {}).get("route_id") == "r2"),
            None,
        )
        self.assertIsNotNone(f_r2)
        # coords should come from stops sA/sB in correct order
        self.assertEqual(
            f_r2.get("geometry", {}).get("coordinates"), [[-73.0, 45.0], [-73.1, 45.1]]
        )
        # trip_ids should include the alias tB
        self.assertIn("tB", f_r2.get("properties", {}).get("trip_ids", []))

        # Check routes.json colors
        with open(json_path, "r", encoding="utf-8") as jf:
            jr = json.load(jf)
        # jr is a list of routes; find r1 and r2
        r1 = next((r for r in jr if r.get("routeId") == "r1"), None)
        r2 = next((r for r in jr if r.get("routeId") == "r2"), None)
        self.assertIsNotNone(r1)
        self.assertIsNotNone(r2)
        self.assertEqual(r1.get("color"), "#00FF00")
        self.assertEqual(r2.get("color"), "#FF0000")

        # Check stops-output.geojson
        stops_path = csv_cache.get_path("stops-output.geojson")
        self.assertTrue(os.path.exists(stops_path))
        with open(stops_path, "r", encoding="utf-8") as sf:
            sj = json.load(sf)
        self.assertEqual(sj.get("type"), "FeatureCollection")
        sfeatures = sj.get("features", [])
        # Expect two stop features (sA and sB)
        self.assertEqual(len(sfeatures), 2)

        sA = next(
            (s for s in sfeatures if s.get("properties", {}).get("stop_id") == "sA"),
            None,
        )
        sB = next(
            (s for s in sfeatures if s.get("properties", {}).get("stop_id") == "sB"),
            None,
        )
        self.assertIsNotNone(sA)
        self.assertIsNotNone(sB)

        # Coordinates are [stop_lon, stop_lat]
        self.assertEqual(sA.get("geometry", {}).get("coordinates"), [-73.0, 45.0])
        self.assertEqual(sB.get("geometry", {}).get("coordinates"), [-73.1, 45.1])

        # route_ids for these stops should include r2 and route_colors should contain the route color
        self.assertIn("r2", sA.get("properties", {}).get("route_ids", []))
        self.assertIn("r2", sB.get("properties", {}).get("route_ids", []))
        self.assertIn("FF0000", sA.get("properties", {}).get("route_colors", []))
        self.assertIn("FF0000", sB.get("properties", {}).get("route_colors", []))


if __name__ == "__main__":
    unittest.main()
