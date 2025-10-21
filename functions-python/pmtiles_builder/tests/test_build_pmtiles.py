# Tests for additional behaviors of PmtilesBuilder not covered in the other test module.
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import flask

from main import PmtilesBuilder, build_pmtiles_handler


class TestBuildPmtilesHandler(unittest.TestCase):
    def test_missing_parameters(self):
        with flask.Flask(__name__).test_request_context(json={}):
            req = flask.request
            result = build_pmtiles_handler(req)
        self.assertIn("status", result)
        self.assertEqual(result["status"], "error")
        self.assertIn("feed_stable_id", result["error"])

    def test_dataset_not_prefixed_by_feed(self):
        payload = {"feed_stable_id": "feedA", "dataset_stable_id": "other_dataset"}
        with flask.Flask(__name__).test_request_context(json=payload):
            req = flask.request
            result = build_pmtiles_handler(req)
        self.assertIn("status", result)
        self.assertEqual(result["status"], "error")

    def test_missing_bucket_env(self):
        # Ensure the DATASETS_BUCKET_NAME is not set
        if "DATASETS_BUCKET_NAME" in os.environ:
            del os.environ["DATASETS_BUCKET_NAME"]
        payload = {"feed_stable_id": "feed", "dataset_stable_id": "feed_dataset"}
        with flask.Flask(__name__).test_request_context(json=payload):
            req = flask.request
            result = build_pmtiles_handler(req)
        self.assertEqual(result.get("status"), "error")
        self.assertIn("DATASETS_BUCKET_NAME", result.get("error", ""))

    @patch("main.get_logger", return_value=MagicMock())
    @patch("main.EphemeralOrDebugWorkdir")
    @patch("main.PmtilesBuilder")
    def test_build_pmtiles_handler_success(
        self, mock_builder_cls, mock_workdir_cls, _mock_logger
    ):
        # Arrange
        os.environ["DATASETS_BUCKET_NAME"] = "test-bucket"
        payload = {"feed_stable_id": "feedX", "dataset_stable_id": "feedX_datasetY"}

        # Ensure the patched class exposes the real OperationStatus enum so
        # comparisons inside main.build_pmtiles_handler remain valid.
        mock_builder_cls.OperationStatus = PmtilesBuilder.OperationStatus

        # Workdir context manager mock
        cm = MagicMock()
        cm.__enter__.return_value = "/tmp/fake_workdir"
        cm.__exit__.return_value = False
        mock_workdir_cls.return_value = cm

        # Builder mock
        builder_inst = MagicMock()
        builder_inst.build_pmtiles.return_value = (
            PmtilesBuilder.OperationStatus.SUCCESS,
            "ok",
        )
        mock_builder_cls.return_value = builder_inst

        with flask.Flask(__name__).test_request_context(json=payload):
            req = flask.request
            result = build_pmtiles_handler(req)

        # Assert
        self.assertIn("message", result)
        self.assertEqual(result["message"], "Successfully built pmtiles.")
        mock_builder_cls.assert_called_once_with(
            feed_stable_id=payload["feed_stable_id"],
            dataset_stable_id=payload["dataset_stable_id"],
            workdir="/tmp/fake_workdir",
        )
        builder_inst.build_pmtiles.assert_called_once()

    @patch("main.get_logger", return_value=MagicMock())
    @patch("main.EphemeralOrDebugWorkdir")
    @patch("main.PmtilesBuilder")
    def test_build_pmtiles_handler_builder_returns_failure(
        self, mock_builder_cls, mock_workdir_cls, _mock_logger
    ):
        os.environ["DATASETS_BUCKET_NAME"] = "test-bucket"
        payload = {"feed_stable_id": "feedX", "dataset_stable_id": "feedX_datasetY"}

        # Ensure equality checks against OperationStatus work even though the class is patched
        mock_builder_cls.OperationStatus = PmtilesBuilder.OperationStatus

        cm = MagicMock()
        cm.__enter__.return_value = "/tmp/fake_workdir"
        cm.__exit__.return_value = False
        mock_workdir_cls.return_value = cm

        builder_inst = MagicMock()
        builder_inst.build_pmtiles.return_value = (
            PmtilesBuilder.OperationStatus.FAILURE,
            "no data",
        )
        mock_builder_cls.return_value = builder_inst

        with flask.Flask(__name__).test_request_context(json=payload):
            req = flask.request
            result = build_pmtiles_handler(req)

        self.assertIn("warning", result)
        self.assertEqual(result["warning"], "no data")

    @patch("main.get_logger", return_value=MagicMock())
    @patch("main.EphemeralOrDebugWorkdir")
    @patch("main.PmtilesBuilder")
    def test_build_pmtiles_handler_exception_path(
        self, mock_builder_cls, mock_workdir_cls, _mock_logger
    ):
        os.environ["DATASETS_BUCKET_NAME"] = "test-bucket"
        payload = {"feed_stable_id": "feedX", "dataset_stable_id": "feedX_datasetY"}

        # Make sure main.PmtilesBuilder.OperationStatus is set so build_pmtiles_handler behaves normally
        mock_builder_cls.OperationStatus = PmtilesBuilder.OperationStatus

        # make the workdir context manager raise on enter to simulate unexpected failure
        cm = MagicMock()
        cm.__enter__.side_effect = Exception("boom")
        cm.__exit__.return_value = False
        mock_workdir_cls.return_value = cm

        with flask.Flask(__name__).test_request_context(json=payload):
            req = flask.request
            result = build_pmtiles_handler(req)

        self.assertIn("error", result)
        self.assertIn("Failed to build PMTiles", result["error"])


class TestDownloadAndUploadHelpers(unittest.TestCase):
    def setUp(self):
        # Ensure env var for bucket is set for the builder to use
        os.environ["DATASETS_BUCKET_NAME"] = "test-bucket"
        # Patch the module-level get_logger used by main so PmtilesBuilder won't emit real logs during ctor
        self.get_logger_patcher = patch("main.get_logger", return_value=MagicMock())
        self.mock_get_logger = self.get_logger_patcher.start()
        self.builder = PmtilesBuilder("feedX", "feedX_datasetY")
        # Also ensure the instance logger is a mock (defensive)
        self.builder.logger = MagicMock()

    def tearDown(self):
        if "DATASETS_BUCKET_NAME" in os.environ:
            del os.environ["DATASETS_BUCKET_NAME"]
        # stop the get_logger patcher if started
        if hasattr(self, "get_logger_patcher"):
            self.get_logger_patcher.stop()

    @patch("main.storage.Client")
    def test_download_and_process_blob_missing_raises(self, mock_storage):
        # Processor that requires download
        processor = MagicMock()
        processor.filename = "missing.txt"
        processor.no_download = False
        processor.no_delete = True
        processor.process = MagicMock()

        # Mock bucket/blob to indicate missing blob
        mock_client = mock_storage.return_value
        bucket = mock_client.get_bucket.return_value
        blob = MagicMock()
        blob.exists.return_value = False
        bucket.blob.return_value = blob

        # Suppress global logging output during the invocation so the test output is clean
        import logging

        logging.disable(logging.CRITICAL)
        try:
            # Method should not raise anymore; it should just return without calling process()
            self.builder.download_and_process(processor)
        finally:
            logging.disable(logging.NOTSET)
        processor.process.assert_not_called()

    @patch("main.storage.Client")
    def test_download_and_process_no_download_calls_process_only(self, mock_storage):
        processor = MagicMock()
        processor.filename = "local.txt"
        processor.no_download = True
        processor.no_delete = True
        processor.process = MagicMock()

        # storage.Client should not be required/called
        self.builder.download_and_process(processor)
        processor.process.assert_called_once()
        mock_storage.assert_not_called()

    @patch("main.storage.Client")
    def test_upload_files_to_gcs_success(self, mock_storage):
        # Create a temp file to upload
        with tempfile.TemporaryDirectory() as td:
            fname = "upload.me"
            path = os.path.join(td, fname)
            with open(path, "w", encoding="utf-8") as f:
                f.write("hello")

            # Patch get_path to point to our temp file for the given filename
            self.builder.get_path = (
                lambda fn: path if fn == fname else os.path.join(td, fn)
            )

            mock_client = mock_storage.return_value
            bucket = mock_client.get_bucket.return_value
            # list_blobs returns empty (nothing to delete)
            bucket.list_blobs.return_value = []

            blob = MagicMock()
            # Ensure blob upload and make_public succeed
            bucket.blob.return_value = blob

            # Call upload (builder.upload_to_gcs True by default unless env overrides)
            self.builder.upload_to_gcs = True
            self.builder.bucket_name = "test-bucket"

            self.builder.upload_files_to_gcs([fname])

            # The bucket.blob must be called with the destination path
            self.assertTrue(bucket.blob.called)
            blob.upload_from_filename.assert_called_once_with(path)

    @patch("main.storage.Client")
    def test_check_required_files_presence_bucket_missing(self, mock_storage):
        # Simulate storage client raising on get_bucket
        mock_storage.return_value.get_bucket.side_effect = Exception("no bucket")
        status, msg = self.builder.check_required_files_presence("some/prefix")
        self.assertEqual(status, self.builder.OperationStatus.FAILURE)
        self.assertIn("does not exist", msg)

    @patch("main.storage.Client")
    def test_check_required_files_presence_blobs_empty(self, mock_storage):
        # Simulate bucket exists but directory prefix has no blobs
        mock_client = mock_storage.return_value
        bucket = mock_client.get_bucket.return_value
        bucket.list_blobs.return_value = []

        status, msg = self.builder.check_required_files_presence("some/prefix")
        self.assertEqual(status, self.builder.OperationStatus.FAILURE)
        self.assertIn("does not exist or is empty", msg)

    @patch("main.storage.Client")
    def test_check_required_files_presence_missing_required_file(self, mock_storage):
        # Simulate bucket with blobs but a required file is missing
        mock_client = mock_storage.return_value
        bucket = mock_client.get_bucket.return_value
        bucket.list_blobs.return_value = [MagicMock()]
        # bucket.blob(...).exists() should return False for required file
        blob_mock = MagicMock()
        blob_mock.exists.return_value = False
        bucket.blob.return_value = blob_mock

        status, msg = self.builder.check_required_files_presence("some/prefix")
        self.assertEqual(status, self.builder.OperationStatus.FAILURE)
        self.assertIn("Required file", msg)

    @patch("main.storage.Client")
    def test_check_required_files_presence_success(self, mock_storage):
        # Simulate bucket with all required files present
        mock_client = mock_storage.return_value
        bucket = mock_client.get_bucket.return_value
        bucket.list_blobs.return_value = [MagicMock()]
        blob_mock = MagicMock()
        blob_mock.exists.return_value = True
        bucket.blob.return_value = blob_mock

        status, msg = self.builder.check_required_files_presence("some/prefix")
        self.assertEqual(status, self.builder.OperationStatus.SUCCESS)
        self.assertIn("All required files are present", msg)

    @patch("main.TripsProcessor")
    @patch("main.StopTimesProcessor")
    @patch("main.RoutesProcessorForColors")
    @patch("main.StopsProcessor")
    @patch("main.ShapesProcessor")
    @patch("main.AgenciesProcessor")
    @patch("main.RoutesProcessor")
    def test_process_all_invokes_download_for_each_processor(
        self,
        mock_routes_proc,
        mock_agencies,
        mock_shapes,
        mock_stops,
        mock_routes_colors,
        mock_stop_times,
        mock_trips,
    ):
        # Arrange: return simple mock instances with filenames so download_and_process can be called
        mock_trips.return_value = MagicMock(filename="trips.txt")
        mock_stop_times.return_value = MagicMock(filename="stop_times.txt")
        mock_routes_colors.return_value = MagicMock(filename="routes_colors.txt")
        mock_stops.return_value = MagicMock(filename="stops.txt")
        mock_shapes.return_value = MagicMock(filename="shapes.txt")
        mock_agencies.return_value = MagicMock(filename="agency.txt")
        mock_routes_proc.return_value = MagicMock(filename="routes.txt")

        # Act: patch the builder's download_and_process to count invocations
        with patch.object(
            self.builder, "download_and_process", autospec=True
        ) as mock_download:
            self.builder.process_all()

        # Assert: should have been called once per processor constructed in process_all
        self.assertEqual(mock_download.call_count, 7)

    @patch("main.subprocess.run")
    def test_run_tippecanoe_success(self, mock_run):
        # Simulate tippecanoe succeeding (returncode 0)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "tippecanoe OK"
        mock_run.return_value = mock_result

        with tempfile.TemporaryDirectory() as td:
            # create dummy input file so get_path points to an existing file
            in_fname = "routes-output.geojson"
            out_fname = "routes.pmtiles"
            open(os.path.join(td, in_fname), "w").close()

            # Patch builder.get_path to use our temp dir
            self.builder.get_path = lambda fn: os.path.join(td, fn)

            # Should not raise
            self.builder.run_tippecanoe(in_fname, out_fname)

        mock_run.assert_called_once()
        called_args = mock_run.call_args[0][0]
        # ensure '-o' and output path are in the command
        self.assertIn("-o", called_args)

    @patch("main.subprocess.run")
    def test_run_tippecanoe_failure(self, mock_run):
        # Simulate tippecanoe failing (non-zero returncode)
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "fatal error"
        mock_run.return_value = mock_result

        with tempfile.TemporaryDirectory() as td:
            in_fname = "routes-output.geojson"
            out_fname = "routes.pmtiles"
            open(os.path.join(td, in_fname), "w").close()
            self.builder.get_path = lambda fn: os.path.join(td, fn)

            with self.assertRaises(Exception) as cm:
                self.builder.run_tippecanoe(in_fname, out_fname)

        self.assertIn("Tippecanoe failed", str(cm.exception))

    def test_update_database_no_dataset(self):
        # db_session.query().filter().one_or_none() returns None -> nothing to do
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.one_or_none.return_value = None

        # Call the decorated method with explicit db_session to bypass session creation
        self.builder.dataset_stable_id = "missing_dataset"
        self.builder.update_database(db_session=mock_db)

        # commit should not be called because no dataset
        mock_db.commit.assert_not_called()

    def test_update_database_success(self):
        # Prepare mocks: dataset found and gtfsfeed exists
        dataset_mock = MagicMock()
        dataset_mock.feed_id = "feed_123"
        dataset_mock.stable_id = "dataset_ok"

        gtfsfeed_mock = MagicMock()

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.one_or_none.return_value = (
            dataset_mock
        )
        mock_db.get.return_value = gtfsfeed_mock

        self.builder.dataset_stable_id = "dataset_ok"
        self.builder.update_database(db_session=mock_db)

        # ensure visualization_dataset was set and commit called
        self.assertIs(getattr(gtfsfeed_mock, "visualization_dataset"), dataset_mock)
        mock_db.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
