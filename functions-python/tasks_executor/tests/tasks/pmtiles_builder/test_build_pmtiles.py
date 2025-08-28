import csv
import json
import logging
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import patch, MagicMock
import os

from tasks.pmtiles_builder.build_pmtiles import (
    PmtilesBuilder,
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


class TestDownloadFilesFromGCS(unittest.TestCase):
    def setUp(self):
        self.builder = PmtilesBuilder(
            feed_stable_id="feed123",
            dataset_stable_id="feed123_dataset456",
            workdir="/tmp",
        )
        self.builder.bucket = MagicMock()
        self.builder.logger = MagicMock()
        self.builder.bucket_name = "test-bucket"  # Ensure bucket_name is set

    @patch("tasks.pmtiles_builder.build_pmtiles.storage.Client")
    @patch("tasks.pmtiles_builder.build_pmtiles.ROUTES_FILE", "routes.txt")
    def test_required_file_missing(self, mock_storage_client):
        mock_storage_client.return_value.get_bucket.return_value = self.builder.bucket
        blob = MagicMock()
        blob.exists.return_value = False
        self.builder.bucket.blob.return_value = blob
        # Simulate directory exists by returning a non-empty list
        self.builder.bucket.list_blobs.return_value = [MagicMock()]
        status, msg = self.builder._download_files_from_gcs("some/path")
        self.assertEqual(status, self.builder.OperationStatus.FAILURE)
        self.assertIn("Required file", msg)
        self.builder.logger.warning.assert_called()

    @patch("tasks.pmtiles_builder.build_pmtiles.SHAPES_FILE", "shapes.txt")
    def test_optional_file_missing(self):
        blob = MagicMock()
        blob.exists.return_value = False
        self.builder.bucket.blob.return_value = blob
        status, msg = self.builder._download_files_from_gcs("some/path")
        self.builder.logger.debug.assert_called()

    @patch("tasks.pmtiles_builder.build_pmtiles.storage.Client")
    @patch("tasks.pmtiles_builder.build_pmtiles.ROUTES_FILE", "routes.txt")
    def test_file_download_success(self, mock_storage_client):
        mock_storage_client.return_value.get_bucket.return_value = self.builder.bucket
        blob = MagicMock()
        blob.exists.return_value = True
        blob.download_to_filename.return_value = None
        self.builder.bucket.blob.return_value = blob
        # Simulate directory exists by returning a non-empty list
        self.builder.bucket.list_blobs.return_value = [MagicMock()]
        status, msg = self.builder._download_files_from_gcs("some/path")
        self.assertEqual(status, self.builder.OperationStatus.SUCCESS)
        self.assertIn("downloaded successfully", msg)

    @patch("tasks.pmtiles_builder.build_pmtiles.storage.Client")
    def test_bucket_not_exist(self, mock_client):
        mock_client.return_value.get_bucket.side_effect = Exception("Bucket not found")
        status, message = self.builder._download_files_from_gcs("some/path")
        self.assertEqual(status, PmtilesBuilder.OperationStatus.FAILURE)
        self.assertIn("Bucket not found", message)

    @patch("tasks.pmtiles_builder.build_pmtiles.storage.Client")
    def test_download_required_file_error(self, mock_storage_client):
        mock_storage_client.return_value.get_bucket.return_value = self.builder.bucket
        blob = MagicMock()
        blob.exists.return_value = True
        blob.download_to_filename.side_effect = Exception("Download failed")
        self.builder.bucket.blob.return_value = blob
        self.builder.bucket.list_blobs.return_value = [MagicMock()]
        # Only required files
        with self.assertRaises(Exception) as context:
            self.builder._download_files_from_gcs("some/path")
        self.assertIn("Error downloading required file", str(context.exception))
        self.builder.logger.error.assert_called()

    @patch("tasks.pmtiles_builder.build_pmtiles.storage.Client")
    def test_download_optional_file_error(self, mock_storage_client):
        mock_storage_client.return_value.get_bucket.return_value = self.builder.bucket
        blob = MagicMock()
        blob.exists.return_value = True

        def download_side_effect(path):
            if path.endswith("shapes.txt"):
                raise Exception("Download failed")
            # Simulate success for other files

        blob.download_to_filename.side_effect = download_side_effect
        self.builder.bucket.blob.return_value = blob
        self.builder.bucket.list_blobs.return_value = [MagicMock()]
        with patch("tasks.pmtiles_builder.build_pmtiles.SHAPES_FILE", "shapes.txt"):
            status, msg = self.builder._download_files_from_gcs("some/path")
        self.assertEqual(status, self.builder.OperationStatus.SUCCESS)
        self.builder.logger.warning.assert_called_with(
            "Cannot download optional file 'some/path/shapes.txt' from bucket 'test-bucket': Download failed"
        )
        self.assertEqual(msg, "All required files downloaded successfully.")


class TestPmtilesBuilder(unittest.TestCase):
    def setUp(self):
        self.feed_stable_id = "feed123"
        self.dataset_stable_id = "feed123_dataset456"
        os.environ["DATASETS_BUCKET_NAME"] = "test-bucket"
        self.builder = PmtilesBuilder(self.feed_stable_id, self.dataset_stable_id)

    @patch("tasks.pmtiles_builder.build_pmtiles.subprocess.run")
    def test_run_tippecanoe_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        self.builder._run_tippecanoe("input.geojson", "output.pmtiles")
        mock_run.assert_called_once()

    @patch("tasks.pmtiles_builder.build_pmtiles.subprocess.run")
    def test_run_tippecanoe_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        with self.assertRaises(Exception), suppress_logging():
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
    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists")
    @patch("os.makedirs")
    def test_build_pmtiles_success(
        self,
        mock_makedirs,
        mock_exists,
        mock_file_open,
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
        mock_download.return_value = (
            PmtilesBuilder.OperationStatus.SUCCESS,
            "All required files downloaded successfully.",
        )
        
        # Mock file existence checks
        mock_exists.return_value = True
        
        # Mock the stops-output.geojson file that will be accessed
        mock_stops_data = '{"type": "FeatureCollection", "features": []}'
        mock_file_open.return_value.__enter__.return_value.read.return_value = mock_stops_data
        
        mock_gtfs_data = {
            "routes": MagicMock(),
            "trips": MagicMock(),
            "stops": MagicMock(),
            "stop_times": MagicMock(),
            "stops-output.geojson": mock_stops_data
        }
        
        status, message = self.builder.build_pmtiles(mock_gtfs_data)
        self.assertEqual(status, PmtilesBuilder.OperationStatus.SUCCESS)
        self.assertEqual(message, "success")

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
        with tempfile.TemporaryDirectory() as temp_dir:
            self.builder.workdir = temp_dir
            shapes_path = os.path.join(temp_dir, "shapes.txt")
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
        with tempfile.TemporaryDirectory() as temp_dir:
            self.builder.workdir = temp_dir
            shapes_path = self.builder.get_path("shapes.txt")

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
        with tempfile.TemporaryDirectory() as temp_dir:
            self.builder.workdir = temp_dir
            with open(self.builder.get_path("routes.txt"), "w", encoding="utf-8") as f:
                f.write(
                    "route_id,route_long_name,route_color,route_text_color,route_type\nr1,Route 1,FF0000,FFFFFF,3\n"
                )
            with open(self.builder.get_path("trips.txt"), "w", encoding="utf-8") as f:
                f.write("route_id,service_id,trip_id,shape_id\nr1,svc1,t1,s1\n")
            with open(self.builder.get_path("stops.txt"), "w", encoding="utf-8") as f:
                f.write(
                    "stop_id,stop_lat,stop_lon\nstop1,45.0,-73.0\nstop2,45.1,-73.1\n"
                )
            with open(
                self.builder.get_path("stop_times.txt"), "w", encoding="utf-8"
            ) as f:
                f.write("trip_id,arrival_time,departure_time,stop_id,stop_sequence\n")
                f.write("t1,08:00:00,08:00:00,stop1,1\n")
                f.write("t1,08:10:00,08:10:00,stop2,2\n")
            with open(self.builder.get_path("shapes.txt"), "w", encoding="utf-8") as f:
                f.write("shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n")
                f.write("s1,45.0,-73.0,1\n")
                f.write("s1,45.1,-73.1,2\n")

            # Call the method
            self.builder._create_routes_geojson()

            # Assert output file exists and is valid GeoJSON
            output_path = self.builder.get_path("routes-output.geojson")
            self.assertTrue(os.path.exists(output_path))
            with open(output_path, "r", encoding="utf-8") as f:
                data = f.read()
        self.assertIn("FeatureCollection", data)

    def test_create_stops_geojson(self):
        # Prepare minimal stops.txt
        with tempfile.TemporaryDirectory() as temp_dir:
            self.builder.workdir = temp_dir
            with open(self.builder.get_path("stops.txt"), "w", encoding="utf-8") as f:
                f.write("stop_id,stop_lat,stop_lon\n")
                f.write("stop1,45.0,-73.0\n")
                f.write("stop2,45.1,-73.1\n")

            # Call the method
            self.builder._create_stops_geojson()

            # Assert output file exists and is valid GeoJSON
            output_path = self.builder.get_path("stops-output.geojson")
            self.assertTrue(os.path.exists(output_path))
            with open(output_path, "r", encoding="utf-8") as f:
                data = f.read()
                self.assertIn("FeatureCollection", data)

    def test_create_routes_json(self):
        # Prepare minimal routes.txt
        with tempfile.TemporaryDirectory() as temp_dir:
            self.builder.workdir = temp_dir
            with open(self.builder.get_path("routes.txt"), "w", encoding="utf-8") as f:
                f.write(
                    "route_id,route_long_name,route_color,route_text_color,route_type\n"
                )
                f.write("r1,Route 1,FF0000,FFFFFF,3\n")

            # Call the method
            self.builder._create_routes_json()

            # Assert output file exists and is valid JSON
            output_path = self.builder.get_path("routes.json")
            self.assertTrue(os.path.exists(output_path))
            with open(output_path, "r", encoding="utf-8") as f:
                data = f.read()
                self.assertIn("routeId", data)
                self.assertIn("routeName", data)

    def test_create_routes_json_exception(self):
        # Ensure routes.txt does not exist to trigger the exception
        routes_path = self.builder.get_path("routes.txt")
        if os.path.exists(routes_path):
            os.remove(routes_path)
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
                with self.assertRaises(Exception) as cm:
                    self.builder.build_pmtiles(gtfs_data={})
            self.assertIn("Download failed", str(cm.exception))

    def test_upload_files_to_gcs_missing_file(self):
        self.builder.bucket = MagicMock()
        self.builder.bucket.blob.return_value = MagicMock()
        self.builder.bucket.list_blobs.return_value = []

        missing_file = "notfound.pmtiles"
        missing_path = self.builder.get_path(missing_file)
        if os.path.exists(missing_path):
            os.remove(missing_path)

        with patch(
            "os.path.exists",
            side_effect=lambda path: False if missing_file in path else True,
        ), self.assertLogs(level="WARNING") as log_cm:
            self.builder._upload_files_to_gcs([missing_file])
            self.assertTrue(
                any(f"File not found: {missing_path}" in msg for msg in log_cm.output)
            )

    def test_create_routes_geojson_fallback_to_stop_coordinates(self):
        # Prepare minimal GTFS files with no shape_id for the trip
        with tempfile.TemporaryDirectory() as temp_dir:
            self.builder.workdir = temp_dir
            with open(self.builder.get_path("routes.txt"), "w", encoding="utf-8") as f:
                f.write(
                    "route_id,route_long_name,route_color,route_text_color,route_type\nr1,Route 1,FF0000,FFFFFF,3\n"
                )
            with open(self.builder.get_path("trips.txt"), "w", encoding="utf-8") as f:
                f.write(
                    "route_id,service_id,trip_id,shape_id\nr1,svc1,t1,\n"
                )  # shape_id is empty
            with open(self.builder.get_path("stops.txt"), "w", encoding="utf-8") as f:
                f.write(
                    "stop_id,stop_lat,stop_lon\nstop1,45.0,-73.0\nstop2,45.1,-73.1\n"
                )
            with open(
                self.builder.get_path("stop_times.txt"), "w", encoding="utf-8"
            ) as f:
                f.write("trip_id,arrival_time,departure_time,stop_id,stop_sequence\n")
                f.write("t1,08:00:00,08:00:00,stop1,1\n")
                f.write("t1,08:10:00,08:10:00,stop2,2\n")
            with open(self.builder.get_path("shapes.txt"), "w", encoding="utf-8") as f:
                f.write("shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n")

            # Call the method
            self.builder._create_routes_geojson()

            # Assert output file exists and contains the expected coordinates
            output_path = self.builder.get_path("routes-output.geojson")
            self.assertTrue(os.path.exists(output_path))
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.assertEqual(data["type"], "FeatureCollection")
                self.assertEqual(len(data["features"]), 1)
                coords = data["features"][0]["geometry"]["coordinates"]
                self.assertEqual(coords, [[-73.0, 45.0], [-73.1, 45.1]])

    def test_create_stops_geojson_invalid_coordinates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.builder.workdir = temp_dir
            stops_path = self.builder.get_path("stops.txt")
            with open(stops_path, "w", encoding="utf-8") as f:
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

            output_path = self.builder.get_path("stops-output.geojson")
            self.assertTrue(os.path.exists(output_path))
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.assertEqual(len(data["features"]), 1)
                self.assertEqual(data["features"][0]["properties"]["stop_id"], "stop1")


class TestBuildPmtilesHandlerIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        os.environ["DATASETS_BUCKET_NAME"] = "test-bucket"
        self.feed_stable_id = "feed123"
        self.dataset_stable_id = "feed123_dataset456"
        self.builder = PmtilesBuilder(
            self.feed_stable_id, self.dataset_stable_id, workdir=self.test_dir.name
        )

        # Create minimal GTFS files using builder.get_path
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
            with open(self.builder.get_path(fname), "w", encoding="utf-8") as f:
                f.write(content)

    def tearDown(self):
        self.test_dir.cleanup()
        if "DATASETS_BUCKET_NAME" in os.environ:
            del os.environ["DATASETS_BUCKET_NAME"]

    def test_build_pmtiles_handler_missing_bucket_env(self):
        os.environ.pop("DATASETS_BUCKET_NAME", None)
        payload = {
            "feed_stable_id": self.feed_stable_id,
            "dataset_stable_id": self.dataset_stable_id,
        }
        with suppress_logging():
            result = build_pmtiles_handler(payload)
        self.assertIn("error", result)
        self.assertIn(
            "DATASETS_BUCKET_NAME environment variable is not defined.", result["error"]
        )

    def test_build_pmtiles_handler_missing_ids(self):
        payload = {}
        with suppress_logging():
            result = build_pmtiles_handler(payload)
        self.assertIn("error", result)
        self.assertIn(
            "Both feed_stable_id and dataset_stable_id must be defined.",
            result["error"],
        )

    def test_build_pmtiles_handler_feed_not_prefix(self):
        payload = {
            "feed_stable_id": "notprefix",
            "dataset_stable_id": self.dataset_stable_id,
        }
        with suppress_logging():
            result = build_pmtiles_handler(payload)
        self.assertIn("error", result)
        self.assertIn("is not a prefix of dataset_stable_id", result["error"])


class TestPmtilesBuilderUpload(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.builder = PmtilesBuilder(
            feed_stable_id="foo",
            dataset_stable_id="foo_bar",
            workdir=self.temp_dir.name,
        )
        self.builder.bucket = MagicMock()
        self.mock_blob = MagicMock()
        self.builder.bucket.blob.return_value = self.mock_blob
        self.builder.bucket.list_blobs.return_value = []

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_upload_files_to_gcs(self):
        test_file = self.builder.get_path("routes.pmtiles")
        with open(test_file, "w") as f:
            f.write("dummy data")

        self.builder._upload_files_to_gcs(["routes.pmtiles"])
        self.builder.bucket.blob.assert_called_with(
            "foo/foo_bar/pmtiles/routes.pmtiles"
        )
        self.mock_blob.upload_from_filename.assert_called_with(test_file)


if __name__ == "__main__":
    unittest.main()
