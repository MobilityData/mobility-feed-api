from database_gen.sqlacodegen_models import Validationreport
from feeds_gen.models.validation_report import ValidationReport as ValidationReportApi

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"


class ValidationReportApiImpl(ValidationReportApi):
    """Implementation of the `ValidationReportApi` model.
    This class converts a SQLAlchemy row DB object to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_orm` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True
        orm_mode = True

    @classmethod
    def from_orm(cls, validation_report: Validationreport) -> ValidationReportApi | None:
        """Create a model instance from a SQLAlchemy a Validation Report row object."""
        if not validation_report:
            return None
        total_info, total_warning, total_error = 0, 0, 0
        for notice in validation_report.notices:
            if notice.severity == "INFO":
                total_info += notice.total_notices
            elif notice.severity == "WARNING":
                total_warning += notice.total_notices
            elif notice.severity == "ERROR":
                total_error += notice.total_notices
        return cls(
            validated_at=validation_report.validated_at,
            features=[feature.name for feature in validation_report.features],
            validator_version=validation_report.validator_version,
            total_error=total_error,
            total_warning=total_warning,
            total_info=total_info,
            url_json=validation_report.json_report,
            url_html=validation_report.html_report,
            # TODO this field is not in the database
            # url_system_errors=validation_report.system_errors,
        )
