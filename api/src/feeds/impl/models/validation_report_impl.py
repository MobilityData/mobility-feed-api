from shared.database_gen.sqlacodegen_models import Validationreport
from feeds_gen.models.validation_report import ValidationReport
from utils.logger import get_logger

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"


class ValidationReportImpl(ValidationReport):
    """Implementation of the `ValidationReport` model.
    This class converts a SQLAlchemy row DB object to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_orm` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def _get_logger(cls):
        return get_logger(ValidationReportImpl.__class__.__module__)

    @classmethod
    def from_orm(cls, validation_report: Validationreport | None) -> ValidationReport | None:
        """Create a model instance from a SQLAlchemy a Validation Report row object."""
        if not validation_report:
            return None

        return cls(
            validated_at=validation_report.validated_at,
            features=[feature.name for feature in validation_report.features],
            validator_version=validation_report.validator_version,
            total_error=validation_report.total_error,
            total_warning=validation_report.total_warning,
            total_info=validation_report.total_info,
            unique_error_count=validation_report.unique_error_count,
            unique_warning_count=validation_report.unique_warning_count,
            unique_info_count=validation_report.unique_info_count,
            url_json=validation_report.json_report,
            url_html=validation_report.html_report,
            # TODO this field is not in the database
            # url_system_errors=validation_report.system_errors,
        )
