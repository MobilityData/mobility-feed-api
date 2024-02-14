from utils.date_utils import valid_iso_date


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


def test_valid_iso_date_valid_format():
    """Test valid_iso_date function with invalids ISO 8601 date formats."""
    assert not valid_iso_date("2021-01-01")
    assert not valid_iso_date("June 2021")
