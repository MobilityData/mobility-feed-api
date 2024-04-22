from database_gen.sqlacodegen_models import Validationreport
from feeds_gen.models.validation_report import ValidationReport
from utils.logger import Logger

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"


class ValidationReportImpl(ValidationReport):
    """Implementation of the `ValidationReport` model.
    This class converts a SQLAlchemy row DB object to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_orm` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True
        orm_mode = True

    @staticmethod
    def compute_totals(validation_report) -> tuple[int, int, int]:
        """Compute the total number of errors, info, and warnings from a validation report."""
        total_info, total_warning, total_error = 0, 0, 0
        for notice in validation_report.notices:
            match notice.severity:
                case "INFO":
                    total_info += notice.total_notices
                case "WARNING":
                    total_warning += notice.total_notices
                case "ERROR":
                    total_error += notice.total_notices
                case _:
                    ValidationReportImpl._get_logger().warning(f"Unknown severity: {notice.severity}")
        return total_error, total_info, total_warning

    @classmethod
    def _get_logger(cls):
        return Logger(ValidationReportImpl.__class__.__module__).get_logger()

    @classmethod
    def from_orm(cls, validation_report: Validationreport | None) -> ValidationReport | None:
        """Create a model instance from a SQLAlchemy a Validation Report row object."""
        if not validation_report:
            return None
        total_error, total_info, total_warning = cls.compute_totals(validation_report)
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
