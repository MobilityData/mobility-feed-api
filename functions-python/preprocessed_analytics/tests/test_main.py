import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
from flask import Request
from preprocessed_analytics.src.main import (
    process_analytics_gtfs,
    process_analytics_gbfs,
    get_compute_date,
    process_analytics,
)
from preprocessed_analytics.src.processors.gtfs_analytics_processor import (
    GTFSAnalyticsProcessor,
)
from preprocessed_analytics.src.processors.gbfs_analytics_processor import (
    GBFSAnalyticsProcessor,
)
from flask import Response


class TestAnalyticsFunctions(unittest.TestCase):
    @patch("preprocessed_analytics.src.main.process_analytics_gtfs")
    @patch("preprocessed_analytics.src.main.process_analytics_gbfs")
    def setUp(self, mock_process_analytics_gtfs, mock_process_analytics_gbfs):
        self.mock_request = MagicMock(spec=Request)
        self.mock_request.get_json.return_value = {"compute_date": "20240822"}

    @patch("preprocessed_analytics.src.main.get_compute_date")
    def test_get_compute_date_valid(self, mock_get_compute_date):
        compute_date = get_compute_date(self.mock_request)
        self.assertEqual(compute_date, datetime(2024, 8, 22))

    def test_get_compute_date_invalid(self):
        # Mock request with invalid compute_date format
        self.mock_request.get_json.return_value = {"compute_date": "invalid_date"}
        compute_date = get_compute_date(self.mock_request)
        self.assertIsInstance(compute_date, datetime)
        self.assertLessEqual(compute_date, datetime.now())

    @patch("preprocessed_analytics.src.main.GTFSAnalyticsProcessor.run")
    @patch("preprocessed_analytics.src.main.process_analytics")
    def test_process_analytics_gtfs_success(self, mock_process_analytics, mock_run):
        mock_run.return_value = None
        mock_process_analytics.return_value = Response(None, status=200)
        response = process_analytics_gtfs(self.mock_request)
        mock_process_analytics.assert_called_once_with(
            self.mock_request, GTFSAnalyticsProcessor
        )
        self.assertEqual(response.status_code, 200)

    @patch("preprocessed_analytics.src.main.GBFSAnalyticsProcessor.run")
    @patch("preprocessed_analytics.src.main.process_analytics")
    def test_process_analytics_gbfs_success(self, mock_process_analytics, mock_run):
        mock_run.return_value = None
        mock_process_analytics.return_value = Response(None, status=200)
        response = process_analytics_gbfs(self.mock_request)
        mock_process_analytics.assert_called_once_with(
            self.mock_request, GBFSAnalyticsProcessor
        )
        self.assertEqual(response.status_code, 200)

    @patch("preprocessed_analytics.src.main.Logger.init_logger")
    @patch("preprocessed_analytics.src.main.GTFSAnalyticsProcessor.run")
    def test_process_analytics_gtfs_error(self, mock_run, _):
        mock_run.side_effect = Exception("Test error")
        response = process_analytics_gtfs(self.mock_request)
        self.assertEqual(response.status_code, 500)

    @patch("preprocessed_analytics.src.main.Logger.init_logger")
    @patch("preprocessed_analytics.src.main.GBFSAnalyticsProcessor.run")
    def test_process_analytics_gbfs_error(self, mock_run, _):
        mock_run.side_effect = Exception("Test error")
        response = process_analytics_gbfs(self.mock_request)
        self.assertEqual(response.status_code, 500)

    @patch("preprocessed_analytics.src.main.Logger.init_logger")
    @patch("preprocessed_analytics.src.main.GTFSAnalyticsProcessor.run")
    @patch("preprocessed_analytics.src.main.GTFSAnalyticsProcessor.__init__")
    def test_process_analytics_success(self, mock_init, mock_run, _):
        mock_run.return_value = None
        mock_init.return_value = None
        response = process_analytics(self.mock_request, GTFSAnalyticsProcessor)
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Successfully processed analytics for date:", response.data.decode()
        )

    @patch("preprocessed_analytics.src.main.Logger.init_logger")
    @patch("preprocessed_analytics.src.main.GTFSAnalyticsProcessor.run")
    def test_process_analytics_failure(self, mock_run, _):
        mock_run.side_effect = Exception("Processing error")
        response = process_analytics(self.mock_request, GTFSAnalyticsProcessor)
        self.assertEqual(response.status_code, 500)
        self.assertIn("Error processing analytics for date", response.data.decode())
