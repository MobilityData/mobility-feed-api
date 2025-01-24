from packaging.version import Version

import numpy as np

from database_gen.sqlacodegen_models import Validationreport


def set_up_defaults(df):
    """
    Updates the dataframe to match types defined in the database
    @param df: Dataframe to update
    """
    df.status = df.status.fillna("active")
    df["urls.authentication_type"] = df["urls.authentication_type"].fillna(0)
    df["features"] = df["features"].fillna("")
    df["entity_type"] = df["entity_type"].fillna("")
    df["location.country_code"] = df["location.country_code"].fillna("")
    df["location.subdivision_name"] = df["location.subdivision_name"].fillna("")
    df["location.municipality"] = df["location.municipality"].fillna("")
    df = df.replace(np.nan, None)
    df = df.replace("gtfs-rt", "gtfs_rt")
    df["location.country_code"] = df["location.country_code"].replace("unknown", "")
    df["location.subdivision_name"] = df["location.subdivision_name"].replace("unknown", "")
    df["location.municipality"] = df["location.municipality"].replace("unknown", "")
    return df


def parse_validation_report_version(validation_report: Validationreport) -> Version:
    """
    Parse the version from the validation report
    @param validation_report: ORM Validationreport
    @return: Version
    """
    cleaned_version = validation_report.validator_version.split("-SNAPSHOT")[0]
    return Version(cleaned_version)


def get_latest_validation_report(
    validation_report_a: Validationreport, validation_report_b: Validationreport
) -> Validationreport:
    """
    Compare two validation reports by their version
    @param validation_report_a: ORM Validationreport
    @param validation_report_b: ORM Validationreport
    @return: validation report with the highest version
    """
    version_a = parse_validation_report_version(validation_report_a)
    version_b = parse_validation_report_version(validation_report_b)
    return validation_report_a if version_a > version_b else validation_report_b
