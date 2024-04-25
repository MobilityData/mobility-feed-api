import unittest
from datetime import datetime

from database_gen.sqlacodegen_models import Validationreport, Notice, Feature
from feeds.impl.models.validation_report_impl import ValidationReportImpl
from feeds_gen.models.validation_report import ValidationReport


class TestValidationReportImpl(unittest.TestCase):
    def test_from_orm(self):
        validation_report_orm = Validationreport(
            validated_at=datetime(2021, 1, 1, 1, 1, 1),
            validator_version="1.0.0",
            json_report="http://json_report",
            html_report="http://html_report",
            notices=[
                Notice(severity="INFO", total_notices=10),
                Notice(severity="INFO", total_notices=1),
                Notice(severity="WARNING", total_notices=20),
                Notice(severity="WARNING", total_notices=2),
                Notice(severity="ERROR", total_notices=30),
                Notice(severity="ERROR", total_notices=3),
                Notice(severity="INVALID", total_notices=3),
            ],
            features=[Feature(name="feature1"), Feature(name="feature2")],
        )

        result = ValidationReportImpl.from_orm(validation_report_orm)

        self.assertEqual(
            result,
            ValidationReport(
                validated_at=datetime(2021, 1, 1, 1, 1, 1),
                features=["feature1", "feature2"],
                validator_version="1.0.0",
                total_error=33,
                total_warning=22,
                total_info=11,
                url_json="http://json_report",
                url_html="http://html_report",
            ),
        )

        assert ValidationReportImpl.from_orm(None) is None