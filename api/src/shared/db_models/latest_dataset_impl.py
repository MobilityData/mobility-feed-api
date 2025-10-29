from functools import reduce

from shared.database_gen.sqlacodegen_models import Gtfsdataset
from shared.db_models.bounding_box_impl import BoundingBoxImpl
from feeds_gen.models.latest_dataset import LatestDataset
from feeds_gen.models.latest_dataset_validation_report import LatestDatasetValidationReport
from shared.db_models.model_utils import compare_java_versions


class LatestDatasetImpl(LatestDataset):
    """Implementation of the `LatestDataset` model.
    This class converts a SQLAlchemy row DB object to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(cls, dataset: Gtfsdataset | None) -> LatestDataset | None:
        """Create a model instance from a SQLAlchemy a Latest Dataset row object."""
        if not dataset:
            return None
        validation_report: LatestDatasetValidationReport | None = None
        if dataset.validation_reports:
            latest_report = reduce(
                lambda a, b: a if compare_java_versions(a.validator_version, b.validator_version) == 1 else b,
                dataset.validation_reports,
            )
            validation_report = LatestDatasetValidationReport(
                total_error=latest_report.total_error,
                total_warning=latest_report.total_warning,
                total_info=latest_report.total_info,
                unique_error_count=latest_report.unique_error_count,
                unique_warning_count=latest_report.unique_warning_count,
                unique_info_count=latest_report.unique_info_count,
                features=sorted([feature.name for feature in latest_report.features]) if latest_report.features else [],
            )

        return cls(
            id=dataset.stable_id,
            hosted_url=dataset.hosted_url,
            bounding_box=BoundingBoxImpl.from_orm(dataset.bounding_box),
            downloaded_at=dataset.downloaded_at,
            service_date_range_start=dataset.service_date_range_start,
            service_date_range_end=dataset.service_date_range_end,
            agency_timezone=dataset.agency_timezone,
            hash=dataset.hash,
            validation_report=validation_report,
            unzipped_folder_size_mb=round(dataset.unzipped_size_bytes / 1024**2, 2)
            if dataset.unzipped_size_bytes
            else None,
            zipped_folder_size_mb=round(dataset.zipped_size_bytes / 1024**2, 2)
            if dataset.zipped_size_bytes
            else None,
        )
