from typing import Optional, Sequence

from feeds_gen.models.gtfs_feed_validation_notice import GtfsFeedValidationNotice
from feeds_gen.models.gtfs_feed_validation_report import GtfsFeedValidationReport
from shared.database_gen.sqlacodegen_models import Notice, Validationreport

# Errors first, so a client rendering the head of the list shows what breaks the feed.
SEVERITY_ORDER = {"ERROR": 0, "WARNING": 1, "INFO": 2}


class GtfsFeedValidationReportImpl(GtfsFeedValidationReport):
    """Implementation of the `GtfsFeedValidationReport` model."""

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @staticmethod
    def _notices(notices: Sequence[Notice]) -> list[GtfsFeedValidationNotice]:
        ordered = sorted(notices, key=lambda n: (SEVERITY_ORDER.get(n.severity, len(SEVERITY_ORDER)), -n.total_notices))
        return [
            GtfsFeedValidationNotice(code=notice.notice_code, severity=notice.severity, total=notice.total_notices)
            for notice in ordered
        ]

    @classmethod
    def from_orm(
        cls,
        dataset_stable_id: str,
        report: Optional[Validationreport],
        notices: Sequence[Notice] = (),
        is_latest: bool = False,
    ) -> GtfsFeedValidationReport:
        """One dataset's entry.

        `notices` is passed in rather than read off `report.notices` because the caller loads them
        for the whole page at once, already filtered by severity.
        """
        return cls(
            dataset_id=dataset_stable_id,
            is_latest=is_latest,
            validated_at=report.validated_at if report else None,
            validator_version=report.validator_version if report else None,
            total_error=report.total_error if report else None,
            total_warning=report.total_warning if report else None,
            total_info=report.total_info if report else None,
            unique_error_count=report.unique_error_count if report else None,
            unique_warning_count=report.unique_warning_count if report else None,
            unique_info_count=report.unique_info_count if report else None,
            url_json=report.json_report if report else None,
            url_html=report.html_report if report else None,
            notices=cls._notices(notices),
        )
