from functools import reduce
from typing import List

from shared.database_gen.sqlacodegen_models import Gtfsdataset, Validationreport
from shared.db_models.bounding_box_impl import BoundingBoxImpl
from shared.db_models.validation_report_impl import ValidationReportImpl
from feeds_gen.models.gtfs_dataset import GtfsDataset
from shared.db_models.model_utils import compare_java_versions


class GtfsDatasetImpl(GtfsDataset):
    """Implementation of the `GtfsDataset` model.
    This class converts a SQLAlchemy row DB object to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_orm` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm_latest_validation_report(
        cls, validation_reports: List["Validationreport"] | None
    ) -> ValidationReportImpl | None:
        """Create a model instance from a SQLAlchemy the latest Validation Report list.
        The latest validation report has the highest `validator_version`.
        The `validator_version` is in form of semantic version.
        """
        if validation_reports:
            latest_report = reduce(
                lambda a, b: a if compare_java_versions(a.validator_version, b.validator_version) == 1 else b,
                validation_reports,
            )
            return ValidationReportImpl.from_orm(latest_report)
        return None

    @classmethod
    def from_orm(cls, gtfs_dataset: Gtfsdataset | None) -> GtfsDataset | None:
        """Create a model instance from a SQLAlchemy a GTFS row object."""
        if not gtfs_dataset:
            return None
        return cls(
            id=gtfs_dataset.stable_id,
            feed_id=gtfs_dataset.feed.stable_id,
            hosted_url=gtfs_dataset.hosted_url,
            note=gtfs_dataset.note,
            downloaded_at=gtfs_dataset.downloaded_at,
            hash=gtfs_dataset.hash,
            bounding_box=BoundingBoxImpl.from_orm(gtfs_dataset.bounding_box),
            validation_report=cls.from_orm_latest_validation_report(gtfs_dataset.validation_reports),
            service_date_range_start=gtfs_dataset.service_date_range_start,
            service_date_range_end=gtfs_dataset.service_date_range_end,
            agency_timezone=gtfs_dataset.agency_timezone,
            unzipped_folder_size_mb=round(gtfs_dataset.unzipped_size_bytes / 1024**2, 2)
            if gtfs_dataset.unzipped_size_bytes
            else None,
            zipped_folder_size_mb=round(gtfs_dataset.zipped_size_bytes / 1024**2, 2)
            if gtfs_dataset.zipped_size_bytes
            else None,
        )
