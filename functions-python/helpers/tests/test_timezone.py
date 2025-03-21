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
        feed_service_window_start = "2025-03-04"
        feed_service_window_end = "2025-03-10"
        timezone = "Asia/Tokyo"

        result = get_service_date_range_with_timezone_utc(
            feed_service_window_start, feed_service_window_end, timezone
        )

        expected_start = datetime(
            2025, 3, 3, 15, 0, tzinfo=ZoneInfo("UTC")
        )  # Asia/Tokyo is UTC-9
        expected_end = datetime(2025, 3, 10, 14, 59, tzinfo=ZoneInfo("UTC"))
        self.assertEqual(result, [expected_start, expected_end])

    def test_valid_dates_with_utc(self):
        feed_service_window_start = "2025-03-01"
        feed_service_window_end = "2025-03-10"
        timezone = "UTC"

        result = get_service_date_range_with_timezone_utc(
            feed_service_window_start, feed_service_window_end, timezone
        )

        expected_start = datetime(2025, 3, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
        expected_end = datetime(2025, 3, 10, 23, 59, tzinfo=ZoneInfo("UTC"))
        self.assertEqual(result, [expected_start, expected_end])

    def test_missing_feed_service_window_start(self):
        feed_service_window_start = None
        feed_service_window_end = "2025-03-10"
        timezone = "UTC"

        result = get_service_date_range_with_timezone_utc(
            feed_service_window_start, feed_service_window_end, timezone
        )

        self.assertIsNone(result)

    def test_missing_feed_service_window_end(self):
        feed_service_window_start = "2025-03-01"
        feed_service_window_end = None
        timezone = "UTC"

        result = get_service_date_range_with_timezone_utc(
            feed_service_window_start, feed_service_window_end, timezone
        )

        self.assertIsNone(result)

    def test_invalid_date_format_start(self):
        feed_service_window_start = "03-01-2025"  # Invalid format (MM-DD-YYYY)
        feed_service_window_end = "2025-03-10"
        timezone = "UTC"

        result = get_service_date_range_with_timezone_utc(
            feed_service_window_start, feed_service_window_end, timezone
        )

        self.assertIsNone(result)

    def test_invalid_date_format_end(self):
        feed_service_window_start = "2025-03-01"
        feed_service_window_end = "03-10-2025"  # Invalid format (MM-DD-YYYY)
        timezone = "UTC"

        result = get_service_date_range_with_timezone_utc(
            feed_service_window_start, feed_service_window_end, timezone
        )

        self.assertIsNone(result)

    def test_default_timezone_utc(self):
        feed_service_window_start = "2025-03-01"
        feed_service_window_end = "2025-03-10"
        timezone = None  # None should default to UTC

        result = get_service_date_range_with_timezone_utc(
            feed_service_window_start, feed_service_window_end, timezone
        )

        expected_start = datetime(2025, 3, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
        expected_end = datetime(2025, 3, 10, 23, 59, tzinfo=ZoneInfo("UTC"))
        self.assertEqual(result, [expected_start, expected_end])

    def test_invalid_service_date_range(self):
        feed_service_window_start = None
        feed_service_window_end = None
        timezone = "UTC"

        result = get_service_date_range_with_timezone_utc(
            feed_service_window_start, feed_service_window_end, timezone
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
