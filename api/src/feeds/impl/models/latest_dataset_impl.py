from functools import reduce

from packaging.version import Version

from database_gen.sqlacodegen_models import Gtfsdataset
from feeds.impl.models.bounding_box_impl import BoundingBoxImpl
from feeds.impl.models.validation_report_impl import ValidationReportImpl
from feeds_gen.models.latest_dataset import LatestDataset
from feeds_gen.models.latest_dataset_validation_report import LatestDatasetValidationReport


class LatestDatasetImpl(LatestDataset):
    """Implementation of the `LatestDataset` model.
    This class converts a SQLAlchemy row DB object to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_orm` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True
        orm_mode = True

    @classmethod
    def from_orm(cls, dataset: Gtfsdataset | None) -> LatestDataset | None:
        """Create a model instance from a SQLAlchemy a Latest Dataset row object."""
        if not dataset:
            return None
        validation_report: LatestDatasetValidationReport | None = None
        if dataset.validation_reports:
            latest_report = reduce(
                lambda a, b: a if Version(a.validator_version) > Version(b.validator_version) else b,
                dataset.validation_reports,
            )
            total_error, total_info, total_warning = ValidationReportImpl.compute_totals(latest_report)
            validation_report = LatestDatasetValidationReport(
                total_error=total_error,
                total_warning=total_warning,
                total_info=total_info,
            )
        return cls(
            id=dataset.stable_id,
            hosted_url=dataset.hosted_url,
            bounding_box=BoundingBoxImpl.from_orm(dataset.bounding_box),
            downloaded_at=dataset.downloaded_at,
            hash=dataset.hash,
            validation_report=validation_report,
        )
