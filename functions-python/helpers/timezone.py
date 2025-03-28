from zoneinfo import available_timezones
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Optional
import logging


def is_valid_timezone(tz_str: str) -> bool | None:
    return tz_str in available_timezones()


def normalize_timezone(timezone: str | None) -> str | None:
    """Converts a lowercase/misformatted timezone to its correct capitalization."""
    if timezone is None:
        return None
    timezones = {tz.lower(): tz for tz in available_timezones()}
    return timezones.get(timezone.lower())  # Returns correct capitalization or None


def extract_timezone_from_json_validation_report(json_data: dict) -> Optional[str]:
    summary = json_data.get("summary", {})
    extracted_timezone = None
    if isinstance(summary.get("agencies"), list) and summary["agencies"]:
        raw_timezone = summary["agencies"][0].get("timezone", None)
        extracted_timezone = normalize_timezone(raw_timezone)
        if extracted_timezone is not None and is_valid_timezone(extracted_timezone):
            logging.info(f"Timezone found in JSON report: {extracted_timezone}.")
            return extracted_timezone
        else:
            logging.info(
                "Timezone not found in JSON report or is invalid. Defaulting to UTC"
            )
        return None
    else:
        logging.info(
            "Timezone not found in JSON report or is invalid. Defaulting to UTC"
        )
    return extracted_timezone


def get_service_date_range_with_timezone_utc(
    feed_service_window_start, feed_service_window_end, timezone
) -> Optional[List[datetime]]:
    """
    Takes the service date range in %Y-%m-%d format and converts it to UTC timezone.
    """
    if timezone is None:
        timezone = "UTC"

    if feed_service_window_start and feed_service_window_end:
        # service date range is found
        formatted_service_start_date = None
        formatted_service_end_date = None
        try:
            formatted_service_start_date = datetime.strptime(
                feed_service_window_start, "%Y-%m-%d"
            )
        except ValueError:
            logging.error(
                f"""
                Key 'summary.feedInfo.feedStartDate' not found or bad value in
                JSON. value: {feed_service_window_start}
                """
            )
            return None

        try:
            formatted_service_end_date = datetime.strptime(
                feed_service_window_end, "%Y-%m-%d"
            )
        except ValueError:
            logging.error(
                f"""
                Key 'summary.feedInfo.feedEndDate' not found or bad value in
                JSON. value: {feed_service_window_end}
                """
            )
            return None

        # this check is due to an issue in the validation report
        # where the start date could be later than the end date
        if formatted_service_start_date > formatted_service_end_date:
            formatted_service_start_date, formatted_service_end_date = (
                formatted_service_end_date,
                formatted_service_start_date,
            )

        local_service_start_date = formatted_service_start_date.replace(
            hour=0, minute=0, tzinfo=ZoneInfo(timezone)
        )
        utc_service_start_date = local_service_start_date.astimezone(ZoneInfo("UTC"))

        local_service_end_date = formatted_service_end_date.replace(
            hour=23, minute=59, tzinfo=ZoneInfo(timezone)
        )
        utc_service_end_date = local_service_end_date.astimezone(ZoneInfo("UTC"))

        return [utc_service_start_date, utc_service_end_date]

    else:
        logging.error("service date range not found")
        return None
