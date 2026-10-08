import unittest
from unittest.mock import MagicMock, patch

import pytest

from main import DatasetProcessor
from shared.helpers.utils import FeedDownloadError, FeedRequestDiagnostics


def _processor(feed_id="feed-1"):
    return DatasetProcessor(
        producer_url="https://example.com/gtfs.zip",
        feed_id=feed_id,
        feed_stable_id="mdb-1",
        execution_id=None,
        latest_hash=None,
        bucket_name=None,
        authentication_type=0,
        api_key_parameter_name=None,
        public_hosted_datasets_url=None,
    )


def _diagnostics():
    return FeedRequestDiagnostics(
        request_url="https://example.com/gtfs.zip",
        resolved_url="https://example.com/gtfs.zip",
        request_headers={"User-Agent": "agent"},
        response_headers={"Server": "cloudflare"},
        status_code=403,
        latency_ms=1840,
        redirect_urls=[],
        external_ip="34.1.2.3",
        content_type="text/html",
        is_zip=False,
        error_type="ValueError",
        error_message="Invalid HTTP response code: [403]",
    )


class TestDownloadFailureRecording(unittest.TestCase):
    def test_failure_records_one_row_and_reraises(self):
        processor = _processor()
        diagnostics = _diagnostics()

        with patch(
            "main.download_and_get_hash",
            side_effect=FeedDownloadError("boom", diagnostics),
        ):
            with patch.object(processor, "record_download_failure") as mock_record:
                with pytest.raises(FeedDownloadError):
                    processor.download_content("/tmp/does-not-matter", "feed-1")

        mock_record.assert_called_once()
        args = mock_record.call_args[0]
        self.assertEqual(args[0], "feed-1")
        self.assertIs(args[1], diagnostics)

    def test_success_records_nothing(self):
        processor = _processor()

        with patch("main.download_and_get_hash", return_value="abc123"):
            with patch("main.zipfile.is_zipfile", return_value=True):
                with patch.object(processor, "record_download_failure") as mock_record:
                    file_hash, is_zip = processor.download_content(
                        "/tmp/does-not-matter", "feed-1"
                    )

        self.assertEqual(file_hash, "abc123")
        self.assertTrue(is_zip)
        mock_record.assert_not_called()

    def test_no_feed_id_skips_recording(self):
        """The local verifier runs without a feed id, so there is no row to attach."""
        processor = _processor(feed_id=None)

        with patch(
            "main.download_and_get_hash",
            side_effect=FeedDownloadError("boom", _diagnostics()),
        ):
            with patch.object(processor, "record_download_failure") as mock_record:
                with pytest.raises(FeedDownloadError):
                    processor.download_content("/tmp/does-not-matter", None)

        mock_record.assert_not_called()

    def test_storage_failure_does_not_mask_download_error(self):
        processor = _processor()

        session = MagicMock()
        session.commit.side_effect = Exception("db down")

        with patch(
            "main.download_and_get_hash",
            side_effect=FeedDownloadError("boom", _diagnostics()),
        ):
            with patch("main.build_availability_check", return_value=MagicMock()):
                with pytest.raises(FeedDownloadError):
                    processor.download_content("/tmp/does-not-matter", "feed-1")

    def test_recorded_row_is_tagged_as_dataset_download(self):
        processor = _processor()
        diagnostics = _diagnostics()
        session = MagicMock()

        with patch("main.build_availability_check") as mock_build:
            processor.record_download_failure("feed-1", diagnostics, db_session=session)

        mock_build.assert_called_once_with(
            diagnostics, feed_id="feed-1", source="dataset_download"
        )
        session.add.assert_called_once()
        session.commit.assert_called_once()
