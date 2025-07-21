from feeds_gen.models.gbfs_version import GbfsValidationReport
from shared.database_gen.sqlacodegen_models import Gbfsvalidationreport as GbfsValidationReportOrm


class GbfsValidationReportImpl(GbfsValidationReport):
    """Implementation of the `GtfsFeed` model.
    This class converts a SQLAlchemy row DB object to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(cls, validation_report: GbfsValidationReportOrm | None) -> GbfsValidationReport | None:
        if not validation_report:
            return None
        return cls(
            validated_at=validation_report.validated_at,
            total_error=validation_report.total_errors_count,
            report_summary_url=validation_report.report_summary_url,
            validator_version=validation_report.validator_version,
        )
