import json
import logging
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import patch, MagicMock
import os

from main import (
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

    @patch("main.storage.Client")
    @patch("main.ROUTES_FILE", "routes.txt")
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

    @patch("main.SHAPES_FILE", "shapes.txt")
    def test_optional_file_missing(self):
        blob = MagicMock()
        blob.exists.return_value = False
        self.builder.bucket.blob.return_value = blob
        status, msg = self.builder._download_files_from_gcs("some/path")
        self.builder.logger.debug.assert_called()

    @patch("main.storage.Client")
    @patch("main.ROUTES_FILE", "routes.txt")
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

    @patch("main.storage.Client")
    def test_bucket_not_exist(self, mock_client):
        mock_client.return_value.get_bucket.side_effect = Exception("Bucket not found")
        status, message = self.builder._download_files_from_gcs("some/path")
        self.assertEqual(status, PmtilesBuilder.OperationStatus.FAILURE)
        self.assertIn("Bucket not found", message)

    @patch("main.storage.Client")
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

    @patch("main.storage.Client")
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
        with patch("main.SHAPES_FILE", "shapes.txt"):
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

        # Patch the storage client before instantiating the builder
        self.storage_patcher = patch("main.storage.Client")
        self.mock_storage_client = self.storage_patcher.start()
        self.mock_storage_client.return_value.get_bucket.return_value = MagicMock()

        self.download_patcher = patch("main.PmtilesBuilder._download_files_from_gcs")
        self.mock_download = self.download_patcher.start()
        self.mock_download.return_value = (
            PmtilesBuilder.OperationStatus.SUCCESS,
            "success",
        )

        self.builder = PmtilesBuilder(self.feed_stable_id, self.dataset_stable_id)

    @patch("main.subprocess.run")
    def test_run_tippecanoe_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        self.builder._run_tippecanoe("input.geojson", "output.pmtiles")
        mock_run.assert_called_once()

    @patch("main.subprocess.run")
    def test_run_tippecanoe_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        with self.assertRaises(Exception), suppress_logging():
            self.builder._run_tippecanoe("input.geojson", "output.pmtiles")

    @patch("main.convert_stops_to_geojson")
    @patch("main.PmtilesBuilder._download_files_from_gcs")
    @patch("main.PmtilesBuilder._create_shapes_index")
    @patch("main.PmtilesBuilder._create_routes_geojson")
    @patch("main.PmtilesBuilder._run_tippecanoe")
    @patch("main.PmtilesBuilder._create_routes_json")
    @patch("main.PmtilesBuilder._upload_files_to_gcs")
    def test_build_pmtiles_success(
        self,
        mock_upload,
        mock_routes_json,
        mock_run_tippecanoe,
        mock_routes_geojson,
        mock_shapes_index,
        mock_download,
        mock_convert_stops,
    ):
        self.builder.bucket = MagicMock()
        self.builder.bucket.list_blobs.return_value = []
        mock_download.return_value = (
            PmtilesBuilder.OperationStatus.SUCCESS,
            "All required files downloaded successfully.",
        )
        # Configure all mocks to return a success status
        mock_shapes_index.return_value = (
            PmtilesBuilder.OperationStatus.SUCCESS,
            {},
        )
        mock_routes_geojson.return_value = (
            PmtilesBuilder.OperationStatus.SUCCESS,
            "success",
        )
        mock_routes_json.return_value = (
            PmtilesBuilder.OperationStatus.SUCCESS,
            "success",
        )
        mock_run_tippecanoe.return_value = (
            PmtilesBuilder.OperationStatus.SUCCESS,
            "success",
        )
        mock_upload.return_value = (
            PmtilesBuilder.OperationStatus.SUCCESS,
            "success",
        )
        mock_convert_stops.return_value = (
            PmtilesBuilder.OperationStatus.SUCCESS,
            "success",
        )

        status, message = self.builder.build_pmtiles()

        self.assertEqual(status, PmtilesBuilder.OperationStatus.SUCCESS)
        self.assertEqual(message, "success")

    def tearDown(self):
        self.storage_patcher.stop()
        self.download_patcher.stop()
        if "DATASETS_BUCKET_NAME" in os.environ:
            del os.environ["DATASETS_BUCKET_NAME"]

    def test_build_pmtiles_creates_correct_shapes_index(self):
        # Prepare shapes.txt
        with tempfile.TemporaryDirectory() as temp_dir:
            self.builder.set_workdir(temp_dir)
            shapes_path = os.path.join(temp_dir, "shapes.txt")
            with open(shapes_path, "w", encoding="utf-8") as f:
                f.write("shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n")
                # Also test the reordering of shapes lines. In the test file we put sequence number 10 before 8
                # It also tests the reordering works fine if there are gaps in the sequence numbers
                f.write("s1,45.1,-73.1,10\n")
                f.write("s1,45.0,-73.0,8\n")
                # f.write("s1,45.1,-73.1,2\n")
                f.write("s2,46.0,-74.0,1\n")

            index = self.builder._create_shapes_index()
        self.assertEqual(
            index.coordinates_columns,
            ["shape_pt_lon", "shape_pt_lat", "shape_pt_sequence"],
        )
        self.assertIn("s1", index.coordinates_arrays)
        self.assertIn("s2", index.coordinates_arrays)
        self.assertEqual(len(index.coordinates_arrays["s1"]), 3)
        self.assertEqual(len(index.coordinates_arrays["s1"][0]), 2)
        self.assertEqual(len(index.coordinates_arrays["s2"][0]), 1)
        # Assert that sequence numbers for s1 are sorted
        self.assertListEqual(list(index.coordinates_arrays["s1"][2]), [8, 10])
        # Assert that lon and lat for s1 are reordered to match sequence
        self.assertListEqual(list(index.coordinates_arrays["s1"][0]), [-73.0, -73.1])
        self.assertListEqual(list(index.coordinates_arrays["s1"][1]), [45.0, 45.1])
        self.assertEqual(len(index.coordinates_arrays["s2"][0]), 1)

    def test_create_routes_geojson(self):
        # Prepare minimal GTFS files
        with tempfile.TemporaryDirectory() as temp_dir:
            self.builder.set_workdir(temp_dir)
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
            self.builder.create_routes_geojson()

            # Assert output file exists and is valid GeoJSON
            output_path = self.builder.get_path("routes-output.geojson")
            self.assertTrue(os.path.exists(output_path))
            with open(output_path, "r", encoding="utf-8") as f:
                data = f.read()
        self.assertIn("FeatureCollection", data)

    def test_create_routes_json(self):
        # Prepare minimal routes.txt
        with tempfile.TemporaryDirectory() as temp_dir:
            self.builder.set_workdir(temp_dir)
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
                    self.builder.build_pmtiles()
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
            self.builder.set_workdir(temp_dir)
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
            self.builder.create_routes_geojson()

            # Assert output file exists and contains the expected coordinates
            output_path = self.builder.get_path("routes-output.geojson")
            self.assertTrue(os.path.exists(output_path))
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.assertEqual(data["type"], "FeatureCollection")
                self.assertEqual(len(data["features"]), 1)
                coords = data["features"][0]["geometry"]["coordinates"]
                self.assertEqual([[-73.0, 45.0], [-73.1, 45.1]], coords)

    def test_load_agencies(self):
        builder = PmtilesBuilder("feed123", "feed123_dataset456")
        builder.csv_cache = MagicMock()

        # Case 1: Normal agencies
        builder.csv_cache.get_file.return_value = [
            {"agency_id": "a1", "agency_name": "Agency One"},
            {"agency_id": "a2", "agency_name": "Agency Two"},
        ]
        with patch("os.path.exists", return_value=True):
            agencies = builder._load_agencies()
            self.assertEqual(agencies, {"a1": "Agency One", "a2": "Agency Two"})

            # Case 2: Empty agency_id and missing agency_id
            builder.csv_cache.get_file.return_value = [
                {"agency_id": "", "agency_name": "No ID Agency"},
                {"agency_name": "  Trimmed Agency  "},  # No agency_id
            ]
            agencies = builder._load_agencies()
            self.assertEqual(agencies, {"": "Trimmed Agency"})  # Last one overwrites

            # Case 3: agency_name with leading/trailing spaces
            builder.csv_cache.get_file.return_value = [
                {"agency_id": "a3", "agency_name": "  Spaced Name  "},
            ]
            agencies = builder._load_agencies()
            self.assertEqual(agencies, {"a3": "Spaced Name"})


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

    @patch("main.PmtilesBuilder")
    def test_build_pmtiles_handler_missing_bucket_env(self, mock_builder):
        os.environ.pop("DATASETS_BUCKET_NAME", None)
        payload = {
            "feed_stable_id": self.feed_stable_id,
            "dataset_stable_id": self.dataset_stable_id,
        }
        request = MagicMock()
        request.get_json.return_value = payload

        with suppress_logging():
            result = build_pmtiles_handler(request)
        self.assertIn("error", result)
        self.assertIn(
            "DATASETS_BUCKET_NAME environment variable is not defined.", result["error"]
        )

    @patch("main.PmtilesBuilder")
    def test_build_pmtiles_handler_missing_ids(self, mock_builder):
        payload = {}
        request = MagicMock()
        request.get_json.return_value = payload

        with suppress_logging():
            result = build_pmtiles_handler(request)
        self.assertIn("error", result)
        self.assertIn(
            "Both feed_stable_id and dataset_stable_id must be defined.",
            result["error"],
        )

    @patch("main.PmtilesBuilder")
    def test_build_pmtiles_handler_feed_not_prefix(self, mock_builder):
        payload = {
            "feed_stable_id": "notprefix",
            "dataset_stable_id": self.dataset_stable_id,
        }
        request = MagicMock()
        request.get_json.return_value = payload
        with suppress_logging():
            result = build_pmtiles_handler(request)
        self.assertIn("error", result)
        self.assertIn("is not a prefix of dataset_stable_id", result["error"])

    @patch("main.PmtilesBuilder")
    def test_build_pmtiles_handler_failure(self, mock_builder):
        # Set up environment and request
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["WORKDIR_ROOT"] = temp_dir
            payload = {
                "feed_stable_id": self.feed_stable_id,
                "dataset_stable_id": self.dataset_stable_id,
            }
            request = MagicMock()
            request.get_json.return_value = payload

            # Simulate FAILURE status
            instance = mock_builder.return_value
            instance.build_pmtiles.return_value = (
                instance.OperationStatus.FAILURE,
                "fail msg",
            )
            result = build_pmtiles_handler(request)
            self.assertIn("Successfully", result["message"])
            self.assertEqual(os.listdir(temp_dir), [], "Expected empty workdir root")


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

    def test_two_routes_with_each_two_trips_with_varied_shapes(self):
        import json

        with tempfile.TemporaryDirectory() as temp_dir:
            builder = PmtilesBuilder("feed1", "feed1_dataset1", workdir=temp_dir)
            # Write routes.txt
            with open(builder.get_path("routes.txt"), "w", encoding="utf-8") as f:
                f.write(
                    "route_id,route_long_name,route_color,route_text_color,route_type\n"
                )
                f.write("route1,Route 1,FF0000,FFFFFF,3\n")
                f.write("route2,Route 2,00FF00,000000,3\n")
            # Write trips.txt
            with open(builder.get_path("trips.txt"), "w", encoding="utf-8") as f:
                # 2 routes with each 2 trips, with trip1 and trip2 having their own shapes,
                # and trip3 and trip4 sharing the same shape
                f.write("route_id,service_id,trip_id,shape_id\n")
                f.write("route1,svc1,trip1,shape1\n")
                f.write("route1,svc1,trip2,shape2\n")
                f.write("route2,svc2,trip3,shape3\n")
                f.write("route2,svc2,trip4,shape3\n")
            # Write shapes.txt
            with open(builder.get_path("shapes.txt"), "w", encoding="utf-8") as f:
                f.write("shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n")
                f.write("shape1,1.0,11.0,1\n")
                f.write("shape1,1.1,11.1,2\n")
                f.write("shape2,2.0,12.0,1\n")
                f.write("shape2,2.1,12.1,2\n")
                f.write("shape3,3.0,13.0,1\n")
                f.write("shape3,3.1,13.1,2\n")

            # Create routes-output.geojson
            builder.create_routes_geojson()
            geojson_path = builder.get_path("routes-output.geojson")
            self.assertTrue(os.path.exists(geojson_path))

            with open(geojson_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.assertEqual(data["type"], "FeatureCollection")
                # Since there is essentially 3 shapes, there should be 3 features
                self.assertEqual(len(data["features"]), 3)
                expected_coords = {
                    "shape1": [[11.0, 1.0], [11.1, 1.1]],
                    "shape2": [[12.0, 2.0], [12.1, 2.1]],
                    "shape3": [[13.0, 3.0], [13.1, 3.1]],
                }
                expected_trip_shapes = {
                    "trip1": "shape1",
                    "trip2": "shape2",
                    "trip3": "shape3",
                    "trip4": "shape3",
                }
                trip_counts = {k: 0 for k in expected_trip_shapes}
                for feat in data["features"]:
                    trip_ids = feat["properties"].get("trip_ids")
                    shape_id = feat["properties"].get("shape_id")
                    for trip_id in trip_ids:
                        self.assertIn(trip_id, expected_trip_shapes)
                        self.assertEqual(shape_id, expected_trip_shapes[trip_id])
                        actual = feat["geometry"]["coordinates"]
                        expected = expected_coords[shape_id]
                        rounded_actual = [
                            [round(x, 2) for x in pair] for pair in actual
                        ]
                        self.assertEqual(rounded_actual, expected)
                        trip_counts[trip_id] += 1
                for count in trip_counts.values():
                    self.assertEqual(count, 1)

    def test_two_routes_with_each_two_trips_fallback_to_stops(self):
        import json

        with tempfile.TemporaryDirectory() as temp_dir:
            builder = PmtilesBuilder("feed1", "feed1_dataset1", workdir=temp_dir)
            # Write routes.txt
            with open(builder.get_path("routes.txt"), "w", encoding="utf-8") as f:
                f.write(
                    "route_id,route_long_name,route_color,route_text_color,route_type\n"
                )
                f.write("route1,Route 1,FF0000,FFFFFF,3\n")
                f.write("route2,Route 2,00FF00,000000,3\n")
            # Write trips.txt
            with open(builder.get_path("trips.txt"), "w", encoding="utf-8") as f:
                f.write("route_id,service_id,trip_id,shape_id\n")
                f.write("route1,svc1,trip1,\n")
                f.write("route1,svc1,trip2,\n")
                f.write("route2,svc2,trip3,\n")
                f.write("route2,svc2,trip4,\n")
            # Write stops.txt
            with open(builder.get_path("stops.txt"), "w", encoding="utf-8") as f:
                f.write("stop_id,stop_lat,stop_lon\n")
                f.write("stop1-1,1.1,11.1\n")
                f.write("stop1-2,1.2,11.2\n")
                f.write("stop2-1,2.1,12.1\n")
                f.write("stop2-2,2.2,12.2\n")
                f.write("stop3-1,3.1,13.1\n")
                f.write("stop3-2,3.2,13.2\n")
                f.write("stop4-1,4.1,14.1\n")
                f.write("stop4-2,4.2,14.2\n")
            # Write stop_times.txt
            with open(builder.get_path("stop_times.txt"), "w", encoding="utf-8") as f:
                f.write("trip_id,arrival_time,departure_time,stop_id,stop_sequence\n")
                f.write("trip1,08:00:00,08:00:00,stop1-1,1\n")
                f.write("trip1,08:10:00,08:10:00,stop1-2,2\n")
                f.write("trip2,09:00:00,09:00:00,stop2-1,1\n")
                f.write("trip2,09:10:00,09:10:00,stop2-2,2\n")
                f.write("trip3,10:00:00,10:00:00,stop3-1,1\n")
                f.write("trip3,10:10:00,10:10:00,stop3-2,2\n")
                f.write("trip4,11:00:00,11:00:00,stop4-1,1\n")
                f.write("trip4,11:10:00,11:10:00,stop4-2,2\n")
            # No shapes.txt

            # Create routes-output.geojson
            builder.create_routes_geojson()
            geojson_path = builder.get_path("routes-output.geojson")
            self.assertTrue(os.path.exists(geojson_path))

            with open(geojson_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.assertEqual(data["type"], "FeatureCollection")
                self.assertEqual(len(data["features"]), 4)
                expected_coords = {
                    "trip1": [[11.1, 1.1], [11.2, 1.2]],
                    "trip2": [[12.1, 2.1], [12.2, 2.2]],
                    "trip3": [[13.1, 3.1], [13.2, 3.2]],
                    "trip4": [[14.1, 4.1], [14.2, 4.2]],
                }
                for feat in data["features"]:
                    trip_ids = feat["properties"].get("trip_ids")
                    for trip_id in trip_ids:
                        self.assertIn(trip_id, expected_coords)
                        actual = feat["geometry"]["coordinates"]
                        expected = expected_coords[trip_id]
                        # Round both actual and expected coordinates to 2 decimal places
                        rounded_actual = [
                            [round(x, 2) for x in pair] for pair in actual
                        ]
                        self.assertEqual(rounded_actual, expected)


if __name__ == "__main__":
    unittest.main()
