"""Continuous coverage policy values and the arithmetic that applies them.

The maximum coverage window and the list of files the calculation reads are the published
definition of continuous coverage, so - like the rest of the seal policy in
`shared.common.seal_criteria` - they live in code rather than in DB config: changing either
changes which feeds qualify, and that should go through code review, tests and a deploy.

This module is under `shared/` so that the read API and the nightly `fresh_continuous`
evaluator (`functions-python/tasks_executor`, which symlinks `api/src/shared/*`) can agree on
what "successive datasets overlap" means. The API computes these values on the fly from the
datasets it already stores; nothing here is persisted.

See #1761 for the seal algorithm and MobilityData/product-tasks#215 for the endpoint.
"""

import datetime
from datetime import timedelta
from typing import Final, Optional, Tuple

# The longest service window the seal accepts. A dataset declaring service further out than
# this is not evidence of continuous coverage - it is more likely a placeholder calendar.
MAX_COVERAGE_WINDOW: Final[timedelta] = timedelta(days=730)

# The file supplying the producer's declared window.
FEED_INFO_FILE: Final[str] = "feed_info.txt"

# The files the validated service window is derived from. A dataset carrying neither published
# no calendar data at all, which `fresh_continuous` reads as a verdict rather than as a gap
# in what we know.
CALENDAR_FILES: Final[Tuple[str, ...]] = ("calendar.txt", "calendar_dates.txt")

# The files the calculation reads, in the order they are reported. `feed_info.txt` supplies the
# declared window; the two calendar files are what the validator derives the service window
# from. Order is fixed so a client can render one row of chips per dataset without sorting.
COVERAGE_FILES: Final[Tuple[str, ...]] = (FEED_INFO_FILE, *CALENDAR_FILES)

# Which input a coverage window was taken from. Values match the `coverage_window_source` enum
# in the API spec.
SOURCE_SERVICE_DATES: Final[str] = "service_dates"
SOURCE_FEED_INFO: Final[str] = "feed_info"


def as_date(value: Optional[datetime.date | datetime.datetime]) -> Optional[datetime.date]:
    """Reduce a stored value to a plain date.

    The validated service dates are stored as timestamps and the `feed_info.txt` dates as dates,
    but both describe whole service days. Comparing them as timestamps would make a window that
    starts at midnight look like it starts before one stored as a date, so both are narrowed here
    before any arithmetic.
    """
    if value is None:
        return None
    return value.date() if isinstance(value, datetime.datetime) else value


def window_days(start: Optional[datetime.date], end: Optional[datetime.date]) -> Optional[int]:
    """Length of a closed date window, counting both bounds.

    A window that starts and ends on the same day covers one day, not zero - the bounds are
    service dates, not instants. Returns None for an incomplete window and for an inverted one:
    a producer whose end date precedes its start date has no window to measure, and reporting a
    negative length would read as a real measurement.
    """
    if start is None or end is None or end < start:
        return None
    return (end - start).days + 1


def within_max_coverage_window(start: Optional[datetime.date], end: Optional[datetime.date]) -> Optional[bool]:
    """Whether a window stays inside `MAX_COVERAGE_WINDOW`.

    Returns None when there is no window to measure, which a client must not read as passing.
    """
    days = window_days(start, end)
    if days is None:
        return None
    return end - start <= MAX_COVERAGE_WINDOW


def overlap_and_gap(
    older_end: Optional[datetime.date], newer_start: Optional[datetime.date]
) -> Tuple[Optional[int], Optional[int]]:
    """How a dataset's window meets the window of the dataset downloaded just before it.

    Returns `(overlap_days, gap_days)`, of which at most one is ever set:

    * The windows overlap - the newer one starts on or before the older one ends - so the shared
      days are returned as `overlap_days`, counting both bounds. An older window ending Sep 30
      and a newer one starting Sep 16 share 15 days.
    * The windows meet exactly, the newer starting the day after the older ends. That is
      continuous with nothing to spare, reported as `overlap_days` of 0 rather than as a gap.
    * Service is uncovered in between, returned as `gap_days` - the count of uncovered days, so
      one missing day reads as 1.

    Both are None when either bound is missing: an absent window is not a gap.
    """
    if older_end is None or newer_start is None:
        return None, None
    # Days from the end of the older window to the start of the newer one. <= 0 means they
    # overlap, exactly 1 means they meet, more than 1 leaves days uncovered.
    delta = (newer_start - older_end).days
    if delta <= 1:
        return 1 - delta, None
    return None, delta - 1
