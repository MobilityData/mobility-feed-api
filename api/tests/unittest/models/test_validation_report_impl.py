import unittest
from datetime import datetime

from shared.database_gen.sqlacodegen_models import Validationreport, Notice, Feature
from shared.db_models.validation_report_impl import ValidationReportImpl


class TestValidationReportImpl(unittest.TestCase):
    def test_from_orm(self):
        validation_report_orm = Validationreport(
            validated_at=datetime(2021, 1, 1, 1, 1, 1),
            validator_version="1.0.0",
            json_report="http://json_report",
            html_report="http://html_report",
            total_error=33,
            total_warning=22,
            total_info=11,
            unique_error_count=2,
            unique_warning_count=1,
            unique_info_count=1,
            notices=[
                Notice(severity="INFO", total_notices=10),
                Notice(severity="INFO", total_notices=1),
                Notice(severity="WARNING", total_notices=20),
                Notice(severity="WARNING", total_notices=2),
                Notice(severity="ERROR", total_notices=30, notice_code="foreign_key_violation"),
                Notice(severity="ERROR", total_notices=3, notice_code="empty_column_name"),
                Notice(severity="INVALID", total_notices=3),
            ],
            features=[Feature(name="feature1"), Feature(name="feature2")],
        )

        result = ValidationReportImpl.from_orm(validation_report_orm)

        self.assertEqual(
            result,
            ValidationReportImpl(
                validated_at=datetime(2021, 1, 1, 1, 1, 1),
                features=["feature1", "feature2"],
                validator_version="1.0.0",
                total_error=33,
                total_warning=22,
                total_info=11,
                unique_error_count=2,
                unique_warning_count=1,
                unique_info_count=1,
                url_json="http://json_report",
                url_html="http://html_report",
            ),
        )

        assert ValidationReportImpl.from_orm(None) is None
