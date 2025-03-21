import unittest
from timezone import (
    extract_timezone_from_json_validation_report,
    get_service_date_range_with_timezone_utc,
)

from datetime import datetime
from zoneinfo import ZoneInfo


class TestExtractTimezoneFromJsonValidationReport(unittest.TestCase):
    def test_valid_timezone(self):
        json_data = {"summary": {"agencies": [{"timezone": "America/New_York"}]}}
        result = extract_timezone_from_json_validation_report(json_data)
        self.assertEqual(result, "America/New_York")

    def test_invalid_timezone(self):
        json_data = {"summary": {"agencies": [{"timezone": "Invalid/Timezone"}]}}
        result = extract_timezone_from_json_validation_report(json_data)
        self.assertIsNone(result)

    def test_missing_timezone_key(self):
        json_data = {"summary": {"agencies": [{"name": "Test Agency"}]}}
        result = extract_timezone_from_json_validation_report(json_data)
        self.assertIsNone(result)

    def test_empty_agencies_list(self):
        json_data = {"summary": {"agencies": []}}
        result = extract_timezone_from_json_validation_report(json_data)
        self.assertIsNone(result)

    def test_missing_agencies_key(self):
        json_data = {"summary": {}}
        result = extract_timezone_from_json_validation_report(json_data)
        self.assertIsNone(result)

    def test_missing_summary_key(self):
        json_data = {}
        result = extract_timezone_from_json_validation_report(json_data)
        self.assertIsNone(result)

    def test_timezone_case_insensitivity(self):
        json_data = {"summary": {"agencies": [{"timezone": "america/new_york"}]}}
        result = extract_timezone_from_json_validation_report(json_data)
        self.assertEqual(result, "America/New_York")  # `zoneinfo` requires exact casing

    def test_multiple_agencies(self):
        json_data = {
            "summary": {
                "agencies": [
                    {"timezone": "Europe/Paris"},
                    {"timezone": "America/Los_Angeles"},
                ]
            }
        }
        result = extract_timezone_from_json_validation_report(json_data)
        self.assertEqual(result, "Europe/Paris")  # Picks the first valid one


class TestGetServiceDateRangeWithTimezoneUTC(unittest.TestCase):

    def test_valid_dates_with_timezone(self):
        json_report = {
            "summary": {
                "feedInfo": {
                    "feedServiceWindowStart": "2025-03-04",
                    "feedServiceWindowEnd": "2025-03-10",
                },
                "agencies": [{"timezone": "Asia/Tokyo"}],
            }
        }
        result = get_service_date_range_with_timezone_utc(json_report)
        expected_start = datetime(
            2025, 3, 3, 15, 0, tzinfo=ZoneInfo("UTC")
        )  # Asia/Tokyo is UTC-9
        expected_end = datetime(
            2025, 3, 10, 14, 59, tzinfo=ZoneInfo("UTC")
        )  # Asia/Tokyo is UTC-9
        self.assertEqual(result, [expected_start, expected_end])

    def test_valid_dates_with_utc(self):
        json_report = {
            "summary": {
                "feedInfo": {
                    "feedServiceWindowStart": "2025-03-01",
                    "feedServiceWindowEnd": "2025-03-10",
                }
            }
        }
        result = get_service_date_range_with_timezone_utc(json_report)
        expected_start = datetime(2025, 3, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
        expected_end = datetime(2025, 3, 10, 23, 59, tzinfo=ZoneInfo("UTC"))
        self.assertEqual(result, [expected_start, expected_end])

    def test_missing_feed_service_window_start(self):
        json_report = {"summary": {"feedInfo": {"feedServiceWindowEnd": "2025-03-10"}}}
        result = get_service_date_range_with_timezone_utc(json_report)
        self.assertIsNone(result)

    def test_missing_feed_service_window_end(self):
        json_report = {
            "summary": {"feedInfo": {"feedServiceWindowStart": "2025-03-01"}}
        }
        result = get_service_date_range_with_timezone_utc(json_report)
        self.assertIsNone(result)

    def test_invalid_date_format(self):
        json_report = {
            "summary": {
                "feedInfo": {
                    "feedServiceWindowStart": "03-01-2025",  # Wrong format (MM-DD-YYYY)
                    "feedServiceWindowEnd": "2025-03-10",
                }
            }
        }
        result = get_service_date_range_with_timezone_utc(json_report)
        self.assertIsNone(result)

    def test_missing_summary_feedinfo(self):
        json_report = {"summary": {}}
        result = get_service_date_range_with_timezone_utc(json_report)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
