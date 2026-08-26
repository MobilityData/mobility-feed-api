import unittest
from datetime import date, datetime, timedelta, timezone

from shared.common.continuous_coverage import (
    COVERAGE_FILES,
    MAX_COVERAGE_WINDOW,
    SOURCE_FEED_INFO,
    SOURCE_SERVICE_DATES,
)
from shared.database_gen.sqlacodegen_models import Feedinfo, Gtfsdataset, Gtfsfile
from shared.db_models.gtfs_feed_continuous_coverage_impl import GtfsFeedContinuousCoverageImpl


def make_dataset(
    stable_id="mdb-1-202606280029",
    service_start=datetime(2026, 9, 16, tzinfo=timezone.utc),
    service_end=datetime(2027, 7, 28, tzinfo=timezone.utc),
    feed_info=None,
    files=COVERAGE_FILES,
    downloaded_at=datetime(2026, 6, 28, tzinfo=timezone.utc),
):
    """A dataset whose validated service window is Sep 16 2026 - Jul 28 2027."""
    return Gtfsdataset(
        id=stable_id,
        stable_id=stable_id,
        downloaded_at=downloaded_at,
        service_date_range_start=service_start,
        service_date_range_end=service_end,
        feed_info=feed_info,
        gtfsfiles=[
            Gtfsfile(id=f"{stable_id}-{name}", gtfs_dataset_id=stable_id, file_name=name, file_size_bytes=1)
            for name in files
        ],
    )


def make_feed_info(start=date(2026, 9, 16), end=date(2027, 7, 28)):
    return Feedinfo(file_hash="hash", feed_start_date=start, feed_end_date=end)


class TestGtfsFeedContinuousCoverageImpl(unittest.TestCase):
    """Test the `GtfsFeedContinuousCoverageImpl` model."""

    def test_no_dataset_returns_none(self):
        assert GtfsFeedContinuousCoverageImpl.from_orm(None) is None

    def test_service_dates_are_preferred(self):
        """The validator's service dates are the calculation's input when present."""
        result = GtfsFeedContinuousCoverageImpl.from_orm(make_dataset(feed_info=make_feed_info()))

        assert result.coverage_window_source == SOURCE_SERVICE_DATES
        assert result.coverage_window.start == date(2026, 9, 16)
        assert result.coverage_window.end == date(2027, 7, 28)
        assert result.coverage_window.days == 316

    def test_feed_info_is_the_fallback(self):
        """A dataset the validator produced no service dates for falls back on `feed_info.txt`."""
        dataset = make_dataset(service_start=None, service_end=None, feed_info=make_feed_info())
        result = GtfsFeedContinuousCoverageImpl.from_orm(dataset)

        assert result.coverage_window_source == SOURCE_FEED_INFO
        assert result.coverage_window.start == date(2026, 9, 16)
        assert result.service_window is None

    def test_no_window_at_all(self):
        """With neither input there is no window, and no verdict on the two-year limit."""
        result = GtfsFeedContinuousCoverageImpl.from_orm(make_dataset(service_start=None, service_end=None))

        assert result.coverage_window is None
        assert result.coverage_window_source is None
        assert result.within_max_coverage_window is None

    def test_windows_are_reported_separately(self):
        """Both inputs are served even when they agree, so a client can show the two bars."""
        dataset = make_dataset(feed_info=make_feed_info())
        result = GtfsFeedContinuousCoverageImpl.from_orm(dataset)

        assert result.service_window.start == date(2026, 9, 16)
        assert result.feed_info_window.start == date(2026, 9, 16)
        assert result.feed_info_matches is True

    def test_feed_info_mismatch(self):
        """A `feed_info.txt` disagreeing with the calendars is reported, not resolved silently."""
        dataset = make_dataset(feed_info=make_feed_info(start=date(2026, 10, 1)))
        result = GtfsFeedContinuousCoverageImpl.from_orm(dataset)

        assert result.feed_info_matches is False

    def test_missing_feed_info_is_not_a_mismatch(self):
        """A dataset with no `feed_info.txt` has not contradicted its calendars."""
        result = GtfsFeedContinuousCoverageImpl.from_orm(make_dataset())

        assert result.feed_info_window is None
        assert result.feed_info_matches is None

    def test_beyond_the_two_year_limit(self):
        """A dataset declaring service more than two years out fails the limit."""
        start = datetime(2026, 9, 16, tzinfo=timezone.utc)
        dataset = make_dataset(service_start=start, service_end=start + MAX_COVERAGE_WINDOW + timedelta(days=1))
        result = GtfsFeedContinuousCoverageImpl.from_orm(dataset)

        assert result.within_max_coverage_window is False

    def test_exactly_at_the_two_year_limit(self):
        """The limit is inclusive, so a window exactly two years long still passes."""
        start = datetime(2026, 9, 16, tzinfo=timezone.utc)
        dataset = make_dataset(service_start=start, service_end=start + MAX_COVERAGE_WINDOW)
        result = GtfsFeedContinuousCoverageImpl.from_orm(dataset)

        assert result.within_max_coverage_window is True

    def test_overlap_with_previous_dataset(self):
        """The mock's case: an older window ending Sep 30 and a newer one starting Sep 16."""
        previous = make_dataset(
            stable_id="mdb-1-202604290029",
            service_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            service_end=datetime(2026, 9, 30, tzinfo=timezone.utc),
        )
        result = GtfsFeedContinuousCoverageImpl.from_orm(make_dataset(), previous_dataset=previous)

        assert result.previous_dataset_id == "mdb-1-202604290029"
        assert result.overlap_days == 15
        assert result.gap_days is None

    def test_gap_from_previous_dataset(self):
        """Service uncovered between two datasets is what the criterion is meant to catch."""
        previous = make_dataset(
            stable_id="mdb-1-202604290029",
            service_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            service_end=datetime(2026, 9, 1, tzinfo=timezone.utc),
        )
        result = GtfsFeedContinuousCoverageImpl.from_orm(make_dataset(), previous_dataset=previous)

        assert result.overlap_days is None
        assert result.gap_days == 14

    def test_previous_dataset_window_uses_the_same_fallback(self):
        """The older dataset's window is resolved the same way, not read off service dates only."""
        previous = make_dataset(
            stable_id="mdb-1-202604290029",
            service_start=None,
            service_end=None,
            feed_info=make_feed_info(start=date(2026, 5, 1), end=date(2026, 9, 30)),
        )
        result = GtfsFeedContinuousCoverageImpl.from_orm(make_dataset(), previous_dataset=previous)

        assert result.overlap_days == 15

    def test_no_previous_dataset(self):
        """The oldest dataset of a feed has nothing to overlap with."""
        result = GtfsFeedContinuousCoverageImpl.from_orm(make_dataset())

        assert result.previous_dataset_id is None
        assert result.overlap_days is None
        assert result.gap_days is None

    def test_files_always_reported_in_full(self):
        """All three files get an entry so a client can render a fixed row."""
        result = GtfsFeedContinuousCoverageImpl.from_orm(make_dataset(files=("calendar.txt", "stops.txt")))

        assert [file.name for file in result.files] == list(COVERAGE_FILES)
        assert [file.present for file in result.files] == [False, True, False]

    def test_is_latest_is_passed_through(self):
        """Whether a dataset is the feed's latest is the caller's knowledge, not the row's."""
        assert GtfsFeedContinuousCoverageImpl.from_orm(make_dataset(), is_latest=True).is_latest is True
        assert GtfsFeedContinuousCoverageImpl.from_orm(make_dataset()).is_latest is False
