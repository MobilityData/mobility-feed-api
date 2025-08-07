import csv
import json
import logging
import pickle
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import patch, MagicMock
import os

from tasks.pmtiles_builder.build_pmtiles import (
    PmtilesBuilder,
    local_dir,
    build_pmtiles_handler,
)


@contextmanager
def suppress_logging(level=logging.CRITICAL):
    previous_level = logging.root.manager.disable
    logging.disable(level)
    try:
        yield
    finally:
        logging.disable(previous_level)


class TestPmtilesBuilder(unittest.TestCase):
    def setUp(self):
        self.feed_stable_id = "feed123"
        self.dataset_stable_id = "feed123_dataset456"
        os.environ["DATASETS_BUCKET_NAME"] = "test-bucket"
        self.builder = PmtilesBuilder(self.feed_stable_id, self.dataset_stable_id)

    @patch("tasks.pmtiles_builder.build_pmtiles.storage.Client")
    def test_download_files_from_gcs_success(self, mock_client):
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.download_to_filename = MagicMock()
        mock_bucket.list_blobs.return_value = [mock_blob] * 5
        mock_client.return_value.get_bucket.return_value = mock_bucket

        with patch("os.path.exists", return_value=True), patch("shutil.rmtree"), patch(
            "os.makedirs"
        ):
            self.builder._download_files_from_gcs("some/path")
            self.assertTrue(mock_bucket.list_blobs.called)

    @patch("tasks.pmtiles_builder.build_pmtiles.subprocess.run")
    def test_run_tippecanoe_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        self.builder._run_tippecanoe("input.geojson", "output.pmtiles")
        mock_run.assert_called_once()

    @patch("tasks.pmtiles_builder.build_pmtiles.subprocess.run")
    def test_run_tippecanoe_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        with self.assertRaises(Exception):
            self.builder._run_tippecanoe("input.geojson", "output.pmtiles")

    @patch(
        "tasks.pmtiles_builder.build_pmtiles.PmtilesBuilder._download_files_from_gcs"
    )
    @patch("tasks.pmtiles_builder.build_pmtiles.PmtilesBuilder._create_shapes_index")
    @patch("tasks.pmtiles_builder.build_pmtiles.PmtilesBuilder._create_routes_geojson")
    @patch("tasks.pmtiles_builder.build_pmtiles.PmtilesBuilder._run_tippecanoe")
    @patch("tasks.pmtiles_builder.build_pmtiles.PmtilesBuilder._create_stops_geojson")
    @patch("tasks.pmtiles_builder.build_pmtiles.PmtilesBuilder._create_routes_json")
    @patch("tasks.pmtiles_builder.build_pmtiles.PmtilesBuilder._upload_files_to_gcs")
    def test_build_pmtiles_success(
        self,
        mock_upload,
        mock_routes_json,
        mock_stops_geojson,
        mock_run_tippecanoe,
        mock_routes_geojson,
        mock_shapes_index,
        mock_download,
    ):
        self.builder.bucket = MagicMock()
        self.builder.bucket.list_blobs.return_value = []
        result = self.builder.build_pmtiles()
        self.assertIn("message", result)

    def test_get_parameters(self):
        payload = {"feed_stable_id": "f", "dataset_stable_id": "d"}
        f, d = PmtilesBuilder._get_parameters(payload)
        self.assertEqual(f, "f")
        self.assertEqual(d, "d")

    def tearDown(self):
        if "DATASETS_BUCKET_NAME" in os.environ:
            del os.environ["DATASETS_BUCKET_NAME"]

    def test_build_pmtiles_creates_correct_shapes_index(self):
        # Prepare shapes.txt
        os.makedirs(local_dir, exist_ok=True)
        shapes_path = os.path.join(local_dir, "shapes.txt")
        with open(shapes_path, "w", encoding="utf-8") as f:
            f.write("shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n")
            f.write("s1,45.0,-73.0,1\n")
            f.write("s1,45.1,-73.1,2\n")
            f.write("s2,46.0,-74.0,1\n")

        index = self.builder._create_shapes_index()
        self.assertIn("columns", index)
        self.assertEqual(
            index["columns"],
            ["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"],
        )
        self.assertIn("s1", index)
        self.assertIn("s2", index)
        self.assertEqual(len(index["s1"]), 2)
        self.assertEqual(len(index["s2"]), 1)

    def test_get_shape_points(self):
        # Prepare shapes.txt
        os.makedirs(local_dir, exist_ok=True)
        shapes_path = os.path.join(local_dir, "shapes.txt")
        with open(shapes_path, "w", encoding="utf-8") as f:
            f.write("shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n")
            f.write("s1,45.0,-73.0,1\n")
            f.write("s1,45.1,-73.1,2\n")

        # Build index with file positions
        index = {}
        with open(shapes_path, "r", encoding="utf-8") as f:
            header = f.readline()
            columns = next(csv.reader([header]))
            pos1 = f.tell()
            f.readline()
            pos2 = f.tell()
            f.readline()
            index["s1"] = [pos1, pos2]
            index["columns"] = columns

        # Call _get_shape_points
        points = self.builder._get_shape_points("s1", index)
        self.assertEqual(points, [(-73.0, 45.0), (-73.1, 45.1)])

    def test_create_routes_geojson(self):
        # Prepare minimal GTFS files
        os.makedirs(local_dir, exist_ok=True)
        with open(os.path.join(local_dir, "routes.txt"), "w", encoding="utf-8") as f:
            f.write(
                "route_id,route_long_name,route_color,route_text_color,route_type\nr1,Route 1,FF0000,FFFFFF,3\n"
            )
        with open(os.path.join(local_dir, "trips.txt"), "w", encoding="utf-8") as f:
            f.write("route_id,service_id,trip_id,shape_id\nr1,svc1,t1,s1\n")
        with open(os.path.join(local_dir, "stops.txt"), "w", encoding="utf-8") as f:
            f.write("stop_id,stop_lat,stop_lon\nstop1,45.0,-73.0\nstop2,45.1,-73.1\n")
        with open(
            os.path.join(local_dir, "stop_times.txt"), "w", encoding="utf-8"
        ) as f:
            f.write("trip_id,arrival_time,departure_time,stop_id,stop_sequence\n")
            f.write("t1,08:00:00,08:00:00,stop1,1\n")
            f.write("t1,08:10:00,08:10:00,stop2,2\n")
        with open(os.path.join(local_dir, "shapes.txt"), "w", encoding="utf-8") as f:
            f.write("shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n")
            f.write("s1,45.0,-73.0,1\n")
            f.write("s1,45.1,-73.1,2\n")
        # Create shapes_index.pkl
        shapes_index = {
            "s1": [
                len("shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n"),
                len(
                    "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\ns1,45.0,-73.0,1\n"
                ),
            ],
            "columns": [
                "shape_id",
                "shape_pt_lat",
                "shape_pt_lon",
                "shape_pt_sequence",
            ],
        }
        with open(os.path.join(local_dir, "shapes_index.pkl"), "wb") as f:
            pickle.dump(shapes_index, f)

        # Call the method
        self.builder._create_routes_geojson()

        # Assert output file exists and is valid GeoJSON
        output_path = os.path.join(local_dir, "routes-output.geojson")
        self.assertTrue(os.path.exists(output_path))
        with open(output_path, "r", encoding="utf-8") as f:
            data = f.read()
            self.assertIn("FeatureCollection", data)

    def test_create_stops_geojson(self):
        # Prepare minimal stops.txt
        os.makedirs(local_dir, exist_ok=True)
        with open(os.path.join(local_dir, "stops.txt"), "w", encoding="utf-8") as f:
            f.write("stop_id,stop_lat,stop_lon\n")
            f.write("stop1,45.0,-73.0\n")
            f.write("stop2,45.1,-73.1\n")

        # Call the method
        self.builder._create_stops_geojson()

        # Assert output file exists and is valid GeoJSON
        output_path = os.path.join(local_dir, "stops-output.geojson")
        self.assertTrue(os.path.exists(output_path))
        with open(output_path, "r", encoding="utf-8") as f:
            data = f.read()
            self.assertIn("FeatureCollection", data)

    def test_create_routes_json(self):
        # Prepare minimal routes.txt
        os.makedirs(local_dir, exist_ok=True)
        with open(os.path.join(local_dir, "routes.txt"), "w", encoding="utf-8") as f:
            f.write(
                "route_id,route_long_name,route_color,route_text_color,route_type\n"
            )
            f.write("r1,Route 1,FF0000,FFFFFF,3\n")

        # Call the method
        self.builder._create_routes_json()

        # Assert output file exists and is valid JSON
        output_path = os.path.join(local_dir, "routes.json")
        self.assertTrue(os.path.exists(output_path))
        with open(output_path, "r", encoding="utf-8") as f:
            data = f.read()
            self.assertIn("routeId", data)
            self.assertIn("routeName", data)

    def test_create_routes_json_exception(self):
        # Ensure routes.txt does not exist to trigger the exception
        if os.path.exists(os.path.join(local_dir, "routes.txt")):
            os.remove(os.path.join(local_dir, "routes.txt"))
        with self.assertRaises(Exception) as cm:
            self.builder._create_routes_json()
        self.assertIn("Failed to create routes JSON for dataset", str(cm.exception))

    def test_build_pmtiles_exception(self):
        # Set up builder with missing bucket_name to trigger an exception in _download_files_from_gcs
        self.builder.bucket_name = "invalid-bucket"
        # Patch _download_files_from_gcs to raise an exception
        with patch.object(
            self.builder,
            "_download_files_from_gcs",
            side_effect=Exception("Download failed"),
        ):
            # This is a test that purposely generates an exception to verify that error handling in build_pmtiles
            # works as expected. The suppress_logging context manager is used to silence log output during the test.
            with suppress_logging():
                result = self.builder.build_pmtiles()
            self.assertIn("error", result)
            self.assertIn("Failed to build PMTiles for dataset", result["error"])

    def test_upload_files_to_gcs_missing_file(self):
        builder = PmtilesBuilder(feed_stable_id="foo", dataset_stable_id="foo_bar")
        builder.bucket = MagicMock()
        builder.bucket.blob.return_value = MagicMock()
        builder.bucket.list_blobs.return_value = []

        missing_file = "notfound.pmtiles"
        if os.path.exists(os.path.join(local_dir, missing_file)):
            os.remove(os.path.join(local_dir, missing_file))

        with patch(
            "os.path.exists",
            side_effect=lambda path: False if missing_file in path else True,
        ), self.assertLogs(level="WARNING") as log_cm:
            builder._upload_files_to_gcs([missing_file])
            self.assertTrue(
                any(
                    f"File not found: {os.path.join(local_dir, missing_file)}" in msg
                    for msg in log_cm.output
                )
            )

    def test_create_routes_geojson_fallback_to_stop_coordinates(self):
        # Prepare minimal GTFS files with no shape_id for the trip
        os.makedirs(local_dir, exist_ok=True)
        with open(os.path.join(local_dir, "routes.txt"), "w", encoding="utf-8") as f:
            f.write(
                "route_id,route_long_name,route_color,route_text_color,route_type\nr1,Route 1,FF0000,FFFFFF,3\n"
            )
        with open(os.path.join(local_dir, "trips.txt"), "w", encoding="utf-8") as f:
            f.write(
                "route_id,service_id,trip_id,shape_id\nr1,svc1,t1,\n"
            )  # shape_id is empty
        with open(os.path.join(local_dir, "stops.txt"), "w", encoding="utf-8") as f:
            f.write("stop_id,stop_lat,stop_lon\nstop1,45.0,-73.0\nstop2,45.1,-73.1\n")
        with open(
            os.path.join(local_dir, "stop_times.txt"), "w", encoding="utf-8"
        ) as f:
            f.write("trip_id,arrival_time,departure_time,stop_id,stop_sequence\n")
            f.write("t1,08:00:00,08:00:00,stop1,1\n")
            f.write("t1,08:10:00,08:10:00,stop2,2\n")
        # shapes.txt and shapes_index.pkl are still needed but not used in this case
        with open(os.path.join(local_dir, "shapes.txt"), "w", encoding="utf-8") as f:
            f.write("shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n")
        with open(os.path.join(local_dir, "shapes_index.pkl"), "wb") as f:
            pickle.dump(
                {
                    "columns": [
                        "shape_id",
                        "shape_pt_lat",
                        "shape_pt_lon",
                        "shape_pt_sequence",
                    ]
                },
                f,
            )

        # Call the method
        self.builder._create_routes_geojson()

        # Assert output file exists and contains the expected coordinates
        output_path = os.path.join(local_dir, "routes-output.geojson")
        self.assertTrue(os.path.exists(output_path))
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(data["type"], "FeatureCollection")
            self.assertEqual(len(data["features"]), 1)
            coords = data["features"][0]["geometry"]["coordinates"]
            self.assertEqual(coords, [[-73.0, 45.0], [-73.1, 45.1]])

    def test_create_stops_geojson_invalid_coordinates(self):
        # Prepare stops.txt with one valid and one invalid stop
        os.makedirs(local_dir, exist_ok=True)
        with open(os.path.join(local_dir, "stops.txt"), "w", encoding="utf-8") as f:
            f.write("stop_id,stop_lat,stop_lon\n")
            f.write("stop1,45.0,-73.0\n")  # valid
            f.write("stop2,not_a_lat,-73.1\n")  # invalid lat

        with self.assertLogs(level="INFO") as log_cm:
            self.builder._create_stops_geojson()
            self.assertTrue(
                any(
                    "Skipping stop stop2: invalid coordinates" in msg
                    for msg in log_cm.output
                )
            )

        # Assert output file exists and only the valid stop is included
        output_path = os.path.join(local_dir, "stops-output.geojson")
        self.assertTrue(os.path.exists(output_path))
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(len(data["features"]), 1)
            self.assertEqual(data["features"][0]["properties"]["stop_id"], "stop1")


class TestBuildPmtilesHandlerIntegration(unittest.TestCase):
    def setUp(self):
        # Patch local_dir to a temp directory
        self.test_dir = tempfile.TemporaryDirectory()
        self.old_local_dir = local_dir
        self._patch_local_dir(self.test_dir.name)
        os.environ["DATASETS_BUCKET_NAME"] = "test-bucket"

        # Create minimal GTFS files
        files = {
            "routes.txt": (
                "route_id,route_long_name,route_color,route_text_color,route_type\n"
                "r1,Route 1,FF0000,FFFFFF,3\n"
            ),
            "shapes.txt": (
                "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n"
                "s1,45.0,-73.0,1\n"
                "s1,45.1,-73.1,2\n"
            ),
            "trips.txt": ("route_id,service_id,trip_id,shape_id\n" "r1,svc1,t1,s1\n"),
            "stops.txt": (
                "stop_id,stop_lat,stop_lon\n" "stop1,45.0,-73.0\n" "stop2,45.1,-73.1\n"
            ),
            "stop_times.txt": (
                "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
                "t1,08:00:00,08:00:00,stop1,1\n"
                "t1,08:10:00,08:10:00,stop2,2\n"
            ),
        }
        for fname, content in files.items():
            with open(
                os.path.join(self.test_dir.name, fname), "w", encoding="utf-8"
            ) as f:
                f.write(content)

    def tearDown(self):
        self.test_dir.cleanup()
        self._patch_local_dir(self.old_local_dir)
        if "DATASETS_BUCKET_NAME" in os.environ:
            del os.environ["DATASETS_BUCKET_NAME"]

    def _patch_local_dir(self, new_dir):
        import tasks.pmtiles_builder.build_pmtiles as mod

        mod.local_dir = new_dir

    def test_build_pmtiles_handler_missing_bucket_env(self):
        if "DATASETS_BUCKET_NAME" in os.environ:
            del os.environ["DATASETS_BUCKET_NAME"]
        payload = {
            "feed_stable_id": "feed123",
            "dataset_stable_id": "feed123_dataset456",
        }
        result = build_pmtiles_handler(payload)
        self.assertIn("error", result)
        self.assertIn("DATASETS_BUCKET_NAME", result["error"])

    def test_build_pmtiles_handler_missing_ids(self):
        os.environ["DATASETS_BUCKET_NAME"] = "test-bucket"
        payload = {"feed_stable_id": "", "dataset_stable_id": ""}
        result = build_pmtiles_handler(payload)
        self.assertIn("error", result)
        self.assertIn("must be defined", result["error"])

    def test_build_pmtiles_handler_feed_not_prefix(self):
        os.environ["DATASETS_BUCKET_NAME"] = "test-bucket"
        payload = {"feed_stable_id": "foo", "dataset_stable_id": "barbaz"}
        result = build_pmtiles_handler(payload)
        self.assertIn("error", result)
        self.assertIn("is not a prefix", result["error"])


class TestPmtilesBuilderUpload(unittest.TestCase):
    def test_upload_files_to_gcs(self):
        builder = PmtilesBuilder(feed_stable_id="foo", dataset_stable_id="foo_bar")
        builder.bucket = MagicMock()
        mock_blob = MagicMock()
        builder.bucket.blob.return_value = mock_blob
        builder.bucket.list_blobs.return_value = []

        # Create dummy files in local_dir for the test
        os.makedirs(local_dir, exist_ok=True)
        test_file = os.path.join(local_dir, "routes.pmtiles")
        with open(test_file, "w") as f:
            f.write("dummy data")

        builder._upload_files_to_gcs(["routes.pmtiles"])

        builder.bucket.blob.assert_called_with("foo/foo_bar/pmtiles/routes.pmtiles")
        mock_blob.upload_from_filename.assert_called_with(test_file)


if __name__ == "__main__":
    unittest.main()
