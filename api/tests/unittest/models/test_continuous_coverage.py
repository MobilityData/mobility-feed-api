import unittest
from datetime import date, datetime, timedelta, timezone

from shared.common.continuous_coverage import (
    MAX_COVERAGE_WINDOW,
    as_date,
    overlap_and_gap,
    window_days,
    within_max_coverage_window,
)


class TestAsDate(unittest.TestCase):
    """Test `as_date`, which reconciles the two ways a service bound is stored."""

    def test_datetime_is_narrowed(self):
        """Service dates are stored as timestamps but describe whole days."""
        assert as_date(datetime(2026, 9, 16, 13, 45, tzinfo=timezone.utc)) == date(2026, 9, 16)

    def test_date_passes_through(self):
        """`feed_info.txt` dates are already dates."""
        assert as_date(date(2026, 9, 16)) == date(2026, 9, 16)

    def test_none(self):
        assert as_date(None) is None


class TestWindowDays(unittest.TestCase):
    """Test `window_days`, the inclusive length of a service window."""

    def test_counts_both_bounds(self):
        """Sep 16 through Sep 30 is 15 service days, not 14."""
        assert window_days(date(2026, 9, 16), date(2026, 9, 30)) == 15

    def test_single_day_window(self):
        """A window covering one day covers one day, not zero."""
        assert window_days(date(2026, 9, 16), date(2026, 9, 16)) == 1

    def test_incomplete_window(self):
        assert window_days(None, date(2026, 9, 30)) is None
        assert window_days(date(2026, 9, 16), None) is None

    def test_inverted_window(self):
        """An end date before its start is no measurement, not a negative one."""
        assert window_days(date(2026, 9, 30), date(2026, 9, 16)) is None


class TestWithinMaxCoverageWindow(unittest.TestCase):
    """Test the two-year limit."""

    def test_inside_the_limit(self):
        start = date(2026, 9, 16)
        assert within_max_coverage_window(start, start + MAX_COVERAGE_WINDOW - timedelta(days=1)) is True

    def test_exactly_at_the_limit(self):
        """The limit is inclusive: a window exactly two years long still qualifies."""
        start = date(2026, 9, 16)
        assert within_max_coverage_window(start, start + MAX_COVERAGE_WINDOW) is True

    def test_beyond_the_limit(self):
        start = date(2026, 9, 16)
        assert within_max_coverage_window(start, start + MAX_COVERAGE_WINDOW + timedelta(days=1)) is False

    def test_no_window_is_not_a_pass(self):
        """A missing window must not read as satisfying the limit."""
        assert within_max_coverage_window(None, date(2027, 7, 28)) is None


class TestOverlapAndGap(unittest.TestCase):
    """Test how successive datasets are judged to meet, overlap or leave a gap."""

    def test_overlapping_windows(self):
        """An older window ending Sep 30 and a newer one starting Sep 16 share 15 days."""
        assert overlap_and_gap(date(2026, 9, 30), date(2026, 9, 16)) == (15, None)

    def test_windows_meeting_exactly(self):
        """The newer window starting the day after the older ends is continuous with nothing spare.

        That is reported as zero overlap rather than as a gap: no service day is uncovered.
        """
        assert overlap_and_gap(date(2026, 9, 30), date(2026, 10, 1)) == (0, None)

    def test_same_day_boundary(self):
        """Both windows covering Sep 30 share exactly that one day."""
        assert overlap_and_gap(date(2026, 9, 30), date(2026, 9, 30)) == (1, None)

    def test_one_uncovered_day(self):
        """A single missing service day reads as a gap of 1, not 2."""
        assert overlap_and_gap(date(2026, 9, 30), date(2026, 10, 2)) == (None, 1)

    def test_larger_gap(self):
        assert overlap_and_gap(date(2026, 9, 30), date(2026, 10, 15)) == (None, 14)

    def test_missing_bound_is_not_a_gap(self):
        """An absent window says nothing about continuity, so neither value is reported."""
        assert overlap_and_gap(None, date(2026, 9, 16)) == (None, None)
        assert overlap_and_gap(date(2026, 9, 30), None) == (None, None)

    def test_accepts_timestamps_via_as_date(self):
        """Mixed storage types compare correctly once narrowed."""
        older_end = as_date(datetime(2026, 9, 30, 23, 59, tzinfo=timezone.utc))
        newer_start = as_date(date(2026, 9, 16))
        assert overlap_and_gap(older_end, newer_start) == (15, None)
