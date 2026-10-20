import base64
import json
import os
import unittest
from unittest.mock import patch

from cloudevents.http import CloudEvent

from main import DRY_RUN_SOURCE, DatasetProcessor, process_dataset
from shared.helpers.utils import (
    FeedDownloadError,
    FeedDownloadResult,
    FeedRequestDiagnostics,
)


def _processor():
    return DatasetProcessor(
        producer_url="https://example.com/gtfs.zip",
        feed_id="feed-1",
        feed_stable_id="mdb-1",
        execution_id="download-dry-run-1",
        latest_hash=None,
        bucket_name=None,
        authentication_type=0,
        api_key_parameter_name=None,
        public_hosted_datasets_url=None,
    )


def _diagnostics(**overrides):
    values = dict(
        request_url="https://example.com/gtfs.zip",
        status_code=200,
        content_type="application/zip",
        is_zip=True,
    )
    values.update(overrides)
    return FeedRequestDiagnostics(**values)


def _event(payload):
    data = base64.b64encode(json.dumps(payload).encode()).decode()
    return CloudEvent(
        {"type": "event.type", "source": "event.source"},
        {"message": {"data": data}},
    )


class TestDryRunDownload(unittest.TestCase):
    def test_success_is_recorded_with_egress_ip_and_temp_file_removed(self):
        processor = _processor()
        diagnostics = _diagnostics()
        written = {}

        def fake_download(url, file_path, **kwargs):
            # The real job writes to disk; so does the dry run.
            with open(file_path, "wb") as f:
                f.write(b"PK\x03\x04")
            written["path"] = file_path
            written["headers"] = kwargs["headers"]
            return FeedDownloadResult(
                file_hash="abc", is_zip=True, diagnostics=diagnostics
            )

        with patch.dict(os.environ, {"WORKING_DIR": "/tmp"}), patch(
            "main.download_feed", side_effect=fake_download
        ), patch("main.get_external_ip", return_value="34.1.2.3"), patch.object(
            processor, "record_download_failure"
        ) as record:
            success = processor.dry_run_download(
                "feed-1", headers={"User-Agent": "curl/8.0"}
            )

        self.assertTrue(success)
        self.assertEqual(written["headers"], {"User-Agent": "curl/8.0"})
        self.assertFalse(os.path.exists(written["path"]))
        self.assertEqual(diagnostics.external_ip, "34.1.2.3")
        record.assert_called_once_with("feed-1", diagnostics, source=DRY_RUN_SOURCE)

    def test_failure_is_recorded_not_raised(self):
        processor = _processor()
        diagnostics = _diagnostics(status_code=403, error_type="ValueError")

        with patch(
            "main.download_feed",
            side_effect=FeedDownloadError("boom", diagnostics),
        ), patch.object(processor, "record_download_failure") as record:
            success = processor.dry_run_download("feed-1")

        self.assertFalse(success)
        record.assert_called_once_with("feed-1", diagnostics, source=DRY_RUN_SOURCE)


class TestProcessDatasetDryRun(unittest.TestCase):
    payload = {
        "execution_id": "download-dry-run-1",
        "producer_url": "https://example.com/gtfs.zip",
        "feed_stable_id": "mdb-1",
        "feed_id": "feed-1",
        "dataset_id": None,
        "dataset_hash": None,
        "authentication_type": 0,
        "authentication_info_url": None,
        "api_key_parameter_name": None,
        "dry_run": True,
        "headers": {"User-Agent": "curl/8.0"},
    }

    def test_dry_run_only_downloads(self):
        """No trace, no upload, no dataset: only the download and its diagnostics."""
        with patch.object(
            DatasetProcessor, "dry_run_download", return_value=True
        ) as dry_run, patch("main.DatasetTraceService") as trace_service, patch.object(
            DatasetProcessor, "process_from_producer_url"
        ) as process, patch(
            "main.record_trace"
        ) as record_trace:
            result = process_dataset(_event(self.payload))

        self.assertEqual(result, "Dry run completed.")
        dry_run.assert_called_once_with("feed-1", headers={"User-Agent": "curl/8.0"})
        trace_service.assert_not_called()
        process.assert_not_called()
        record_trace.assert_not_called()

    def test_dry_run_error_is_returned(self):
        with patch.object(
            DatasetProcessor, "dry_run_download", side_effect=RuntimeError("db down")
        ):
            result = process_dataset(_event(self.payload))

        self.assertIn("Dry run failed", result)
