import unittest
from datetime import date, datetime, timezone

from shared.common.continuous_coverage import COVERAGE_FILES
from shared.database_gen.sqlacodegen_models import Feedinfo, Gtfsdataset, Gtfsfile
from shared.db_models.gtfs_feed_continuous_coverage_boundary_impl import GtfsFeedContinuousCoverageBoundaryImpl


def make_dataset(stable_id, service, declared=None):
    """One dataset, its windows given as `(start, end)` date pairs."""
    return Gtfsdataset(
        id=stable_id,
        stable_id=stable_id,
        downloaded_at=datetime(2026, 6, 28, tzinfo=timezone.utc),
        service_date_range_start=service[0],
        service_date_range_end=service[1],
        feed_info=(
            Feedinfo(file_hash=stable_id, feed_start_date=declared[0], feed_end_date=declared[1]) if declared else None
        ),
        gtfsfiles=[
            Gtfsfile(id=f"{stable_id}-{name}", gtfs_dataset_id=stable_id, file_name=name, file_size_bytes=1)
            for name in COVERAGE_FILES
        ],
    )


def make_pair():
    older = make_dataset("ds-older", (date(2026, 1, 1), date(2026, 6, 30)))
    newer = make_dataset("ds-newer", (date(2026, 6, 16), date(2026, 12, 31)))
    return older, newer


class TestGtfsFeedContinuousCoverageBoundaryImpl(unittest.TestCase):
    """Test the `GtfsFeedContinuousCoverageBoundaryImpl` model."""

    def test_no_dataset_returns_none(self):
        assert GtfsFeedContinuousCoverageBoundaryImpl.from_orm(None) is None

    def test_both_datasets_are_served_whole(self):
        """The older dataset is a full entry, not just an id on the newer one."""
        older, newer = make_pair()
        result = GtfsFeedContinuousCoverageBoundaryImpl.from_orm(newer, previous_dataset=older, is_latest=True)

        assert result.newer.dataset_id == "ds-newer"
        assert result.newer.is_latest is True
        assert result.newer.overlap_days == 15
        assert result.older.dataset_id == "ds-older"
        assert result.older.coverage_window.start == date(2026, 1, 1)
        assert result.older.coverage_window.end == date(2026, 6, 30)
        assert [file.name for file in result.older.files] == list(COVERAGE_FILES)

    def test_the_older_dataset_has_no_boundary_of_its_own(self):
        """Its predecessor is not loaded, so it is served without an overlap."""
        older, newer = make_pair()
        result = GtfsFeedContinuousCoverageBoundaryImpl.from_orm(newer, previous_dataset=older)

        assert result.older.previous_dataset_id is None
        assert result.older.overlap_days is None
        assert result.older.is_latest is False

    def test_a_feeds_first_dataset_has_no_older_side(self):
        _, newer = make_pair()
        result = GtfsFeedContinuousCoverageBoundaryImpl.from_orm(newer, is_latest=True)

        assert result.older is None
        assert result.newer.dataset_id == "ds-newer"
