from typing import Optional

from feeds_gen.models.gtfs_feed_continuous_coverage import GtfsFeedContinuousCoverage
from feeds_gen.models.gtfs_feed_continuous_coverage_file import GtfsFeedContinuousCoverageFile
from shared.common.continuous_coverage import (
    COVERAGE_FILES,
    SOURCE_FEED_INFO,
    SOURCE_SERVICE_DATES,
    as_date,
    overlap_and_gap,
    within_max_coverage_window,
)
from shared.database_gen.sqlacodegen_models import Gtfsdataset as GtfsdatasetOrm
from shared.db_models.service_date_window_impl import ServiceDateWindowImpl


class GtfsFeedContinuousCoverageImpl(GtfsFeedContinuousCoverage):
    """Implementation of the `GtfsFeedContinuousCoverage` model.

    Converts one `gtfsdataset` row - plus the row downloaded just before it - to a Pydantic model,
    deriving the windows and the overlap the nightly job does not store. All the policy deciding
    what counts as continuous lives in `shared.common.continuous_coverage`, so this class only
    applies it.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def _coverage_window(cls, dataset: GtfsdatasetOrm) -> tuple[Optional[ServiceDateWindowImpl], Optional[str]]:
        """The window the calculation uses for a dataset, and which input it came from.

        The validated service dates win: they are what the validator derived from the calendar
        files, so they describe the service the dataset actually encodes. `feed_info.txt` is only a
        producer's declaration and is used as a fallback, which is also why the two are reported
        separately and compared - a mismatch is worth showing rather than resolving silently.
        """
        service_window = ServiceDateWindowImpl.from_dates(
            dataset.service_date_range_start, dataset.service_date_range_end
        )
        if service_window is not None:
            return service_window, SOURCE_SERVICE_DATES

        feed_info = dataset.feed_info
        if feed_info is None:
            return None, None
        feed_info_window = ServiceDateWindowImpl.from_dates(feed_info.feed_start_date, feed_info.feed_end_date)
        return (feed_info_window, SOURCE_FEED_INFO) if feed_info_window is not None else (None, None)

    @classmethod
    def _files(cls, dataset: GtfsdatasetOrm) -> list[GtfsFeedContinuousCoverageFile]:
        """Which of the files the calculation reads were present in the dataset.

        Every file in `COVERAGE_FILES` gets an entry, present or not, so a client can render a
        fixed row of chips without checking which keys came back.
        """
        present = {file.file_name for file in dataset.gtfsfiles}
        return [GtfsFeedContinuousCoverageFile(name=name, present=name in present) for name in COVERAGE_FILES]

    @classmethod
    def from_orm(
        cls,
        dataset: GtfsdatasetOrm | None,
        previous_dataset: GtfsdatasetOrm | None = None,
        is_latest: bool = False,
    ) -> GtfsFeedContinuousCoverage | None:
        """Create a model instance from a SQLAlchemy Gtfsdataset row object.

        `previous_dataset` is the dataset downloaded immediately before this one, which is what the
        overlap is measured against. It is passed in rather than looked up here because it may sit
        outside the requested page - the caller is the only one that knows the unpaged neighbour.
        """
        if not dataset:
            return None

        coverage_window, coverage_window_source = cls._coverage_window(dataset)
        service_window = ServiceDateWindowImpl.from_dates(
            dataset.service_date_range_start, dataset.service_date_range_end
        )
        feed_info = dataset.feed_info
        feed_info_window = (
            ServiceDateWindowImpl.from_dates(feed_info.feed_start_date, feed_info.feed_end_date)
            if feed_info is not None
            else None
        )

        # Only a comparison of two windows that both exist is a verdict. Missing either one leaves
        # this None: a dataset with no `feed_info.txt` has not contradicted its calendars.
        feed_info_matches = (
            (feed_info_window.start == service_window.start and feed_info_window.end == service_window.end)
            if feed_info_window is not None and service_window is not None
            else None
        )

        # The previous dataset's own coverage window is what this one has to meet, so it is resolved
        # the same way rather than read straight off the service date columns.
        previous_window = cls._coverage_window(previous_dataset)[0] if previous_dataset else None
        overlap_days, gap_days = overlap_and_gap(
            previous_window.end if previous_window else None,
            coverage_window.start if coverage_window else None,
        )

        return cls(
            dataset_id=dataset.stable_id,
            is_latest=is_latest,
            downloaded_at=dataset.downloaded_at,
            coverage_window=coverage_window,
            coverage_window_source=coverage_window_source,
            within_max_coverage_window=within_max_coverage_window(
                as_date(coverage_window.start) if coverage_window else None,
                as_date(coverage_window.end) if coverage_window else None,
            ),
            service_window=service_window,
            feed_info_window=feed_info_window,
            feed_info_matches=feed_info_matches,
            previous_dataset_id=previous_dataset.stable_id if previous_dataset else None,
            overlap_days=overlap_days,
            gap_days=gap_days,
            files=cls._files(dataset),
        )
