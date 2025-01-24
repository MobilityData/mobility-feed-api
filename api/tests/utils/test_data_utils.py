from database_gen.sqlacodegen_models import Validationreport
from utils.data_utils import parse_validation_report_version, get_latest_validation_report
from packaging.version import Version


def test_parse_validation_report_version():
    validation_report = Validationreport(validator_version="1.0.0-SNAPSHOT")
    assert parse_validation_report_version(validation_report) == Version("1.0.0")

    validation_report = Validationreport(validator_version="1.0.0")
    assert parse_validation_report_version(validation_report) == Version("1.0.0")


def test_get_latest_validation_report():
    validation_report_a = Validationreport(validator_version="1.0.0-SNAPSHOT")
    validation_report_b = Validationreport(validator_version="1.0.1-SNAPSHOT")
    assert get_latest_validation_report(validation_report_a, validation_report_b) == validation_report_b

    validation_report_a = Validationreport(validator_version="1.0.0-SNAPSHOT")
    validation_report_b = Validationreport(validator_version="1.0.1")
    assert get_latest_validation_report(validation_report_a, validation_report_b) == validation_report_b
