from datetime import datetime, timezone

from utils.date_utils import parse_iso_datetime, valid_iso_date


def test_valid_iso_date_valid_format():
    """Test valid_iso_date function with valids ISO 8601 date formats."""
    # Validators are not required to check for None or empty strings
    assert valid_iso_date("")
    assert valid_iso_date("   ")
    assert valid_iso_date(None)

    assert valid_iso_date("2021-01-01T00:00:00")
    assert valid_iso_date("2021-01-01T00:00:00Z")
    assert valid_iso_date("2021-01-01T00:00:00+00:00")
    assert valid_iso_date("2021-01-01T00:00:00-00:00")
    assert valid_iso_date("2021-01-01T00:00:00+01:00")
    assert valid_iso_date("2021-01-01T00:00:00-01:00")
    assert valid_iso_date("2021-01-01T00:00:00.000Z")
    assert valid_iso_date("2021-01-01T00:00:00.000+00:00")
    assert valid_iso_date("2021-01-01T00:00:00.000-00:00")
    assert valid_iso_date("2021-01-01T00:00:00.000+01:00")
    assert valid_iso_date("2021-01-01T00:00:00.000-01:00")
    assert valid_iso_date("2021-01-01T00:00:00.000000Z")
    assert valid_iso_date("2021-01-01T00:00:00.000000+00:00")
    assert valid_iso_date("2021-01-01T00:00:00.000000-00:00")
    assert valid_iso_date("2021-01-01T00:00:00.000000+01:00")
    assert valid_iso_date("2021-01-01T00:00:00.000000-01:00")
    assert valid_iso_date("2021-01-01T00:00:00.000000000Z")
    assert valid_iso_date("2021-01-01T00:00:00.000000000+00:00")
    assert valid_iso_date("2021-01-01T00:00:00.000000000-00:00")


def test_invalid_iso_date_valid_format():
    """Test valid_iso_date function with invalids ISO 8601 date formats."""
    assert not valid_iso_date("2021-01-01")
    assert not valid_iso_date("June 2021")


def test_parse_iso_datetime_none_and_empty():
    assert parse_iso_datetime(None) is None
    assert parse_iso_datetime("") is None


def test_parse_iso_datetime_naive_defaults_to_utc():
    assert parse_iso_datetime("2024-01-01T00:00:00") == datetime(2024, 1, 1, tzinfo=timezone.utc)


def test_parse_iso_datetime_aware_is_preserved():
    assert parse_iso_datetime("2024-01-01T00:00:00Z") == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert parse_iso_datetime("2024-01-01T00:00:00+01:00") == datetime(2023, 12, 31, 23, 0, tzinfo=timezone.utc)


def test_parse_iso_datetime_naive_and_aware_are_comparable():
    """The exact scenario `valid_iso_date` allows through and `fromisoformat` alone can't compare:
    one input with an offset and one without."""
    naive = parse_iso_datetime("2024-01-01T00:00:00")
    aware = parse_iso_datetime("2024-06-01T00:00:00Z")
    assert naive < aware
