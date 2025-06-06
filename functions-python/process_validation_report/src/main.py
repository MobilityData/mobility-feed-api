#
#   MobilityData 2024
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import os
import logging
from datetime import datetime
import requests
from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.helpers.timezone import (
    extract_timezone_from_json_validation_report,
    get_service_date_range_with_timezone_utc,
)
import functions_framework
from shared.database_gen.sqlacodegen_models import (
    Validationreport,
    Feature,
    Notice,
    Gtfsdataset,
)
from shared.helpers.logger import init_logger
from shared.helpers.transform import get_nested_value
from shared.helpers.feed_status import update_feed_statuses_query

init_logger()

FILES_ENDPOINT = os.getenv("FILES_ENDPOINT")


def read_json_report(json_report_url):
    """
    Fetches and returns the JSON content from a given URL.

    :param json_report_url: URL to the JSON report
    :return: Dict representation of the JSON report
    """
    response = requests.get(json_report_url)
    return response.json(), response.status_code


def get_feature(feature_name, session):
    """
    Retrieves a Feature object by its name from the database.
    If the feature does not exist, it creates a new one.

    :param feature_name: Name of the feature
    :param session: Database session instance
    :return: Feature instance
    """
    feature = session.query(Feature).filter(Feature.name == feature_name).first()
    if not feature:
        feature = Feature(name=feature_name)
    return feature


def get_dataset(dataset_stable_id, session):
    """
    Retrieves a GTFSDataset object by its stable ID from the database.

    :param dataset_stable_id: Stable ID of the dataset
    :param session: Database session instance
    :return: GTFSDataset instance or None if not found
    """
    return (
        session.query(Gtfsdataset)
        .filter(Gtfsdataset.stable_id == dataset_stable_id)
        .one_or_none()
    )


def validate_json_report(json_report_url):
    """
    Validates the JSON report by fetching and reading it.
    :param json_report_url: The URL of the JSON report
    :return: Tuple containing the JSON report or an error message and the status code
    """
    try:
        json_report, code = read_json_report(json_report_url)
        if code != 200:
            logging.error("Error reading JSON report: %s", code)
            return f"Error reading JSON report at url {json_report_url}.", code
        return json_report, 200
    except Exception as error:  # JSONDecodeError or RequestException
        logging.error("Error reading JSON report: %s", str(error))
        return f"Error reading JSON report at url {json_report_url}: {error}", 500


def parse_json_report(json_report):
    """
    Parses the JSON report and extracts the validatedAt and validatorVersion fields.
    :param json_report: The JSON report
    :return: A tuple containing the validatedAt datetime and the validatorVersion
    """
    try:
        dt = json_report["summary"]["validatedAt"]
        validated_at = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        version = None
        if "validatorVersion" in json_report["summary"]:
            version = json_report["summary"]["validatorVersion"]
        logging.info(
            "Validation report validated_at: %s with version: %s.",
            validated_at,
            version,
        )
        return validated_at, version
    except Exception as error:
        logging.error("Error parsing JSON report: %s", error)
        raise Exception(f"Error parsing JSON report: {error}")


def generate_report_entities(
    version, validated_at, json_report, dataset_stable_id, session, feed_stable_id
):
    """
    Creates validation report entities based on the JSON report.
    :param version: The version of the validator
    :param validated_at: The datetime the report was validated
    :param json_report: The JSON report object
    :param dataset_stable_id: Stable ID of the dataset
    :param session: The database session
    :param feed_stable_id: Stable ID of the feed
    :return: List of entities created
    """
    entities = []
    report_id = f"{dataset_stable_id}_{version}"
    logging.info("Creating validation report entities for: %s.", report_id)

    html_report_url = (
        f"{FILES_ENDPOINT}/{feed_stable_id}/{dataset_stable_id}/report_{version}.html"
    )
    json_report_url = (
        f"{FILES_ENDPOINT}/{feed_stable_id}/{dataset_stable_id}/report_{version}.json"
    )
    # Check if report already exists
    # If exists, the function should graceful finish avoiding retry mechanism to trigger again
    if get_validation_report(report_id, session):
        logging.warning("Validation report %s already exists. Terminating.", report_id)
        return []

    validation_report_entity = Validationreport(
        id=report_id,
        validator_version=version,
        validated_at=validated_at,
        html_report=html_report_url,
        json_report=json_report_url,
    )
    entities.append(validation_report_entity)

    dataset = get_dataset(dataset_stable_id, session)
    if not dataset:
        raise Exception(f"Dataset {dataset_stable_id} not found.")
    dataset.validation_reports.append(validation_report_entity)

    extracted_timezone = extract_timezone_from_json_validation_report(json_report)
    if extracted_timezone is not None:
        dataset.agency_timezone = extracted_timezone

    populate_service_date(dataset, json_report, extracted_timezone)

    for feature_name in get_nested_value(json_report, ["summary", "gtfsFeatures"], []):
        feature = get_feature(feature_name, session)
        feature.validations.append(validation_report_entity)
        entities.append(feature)

    for notice in json_report["notices"]:
        notice_entity = Notice(
            dataset_id=dataset.id,
            validation_report_id=report_id,
            notice_code=notice["code"],
            severity=notice["severity"],
            total_notices=notice["totalNotices"],
        )
        dataset.notices.append(notice_entity)
        entities.append(notice_entity)

    # Process notices and compute counters
    populate_counters(dataset.notices, validation_report_entity)
    return entities


def populate_counters(notices, validation_report_entity):
    """
    Populates the validation report entity with counters based on the notices.
    :param notices: Notices
    :param validation_report_entity: validation report entity
    """
    counters = process_validation_report_notices(notices)

    # Update the validation report entity with computed counters
    validation_report_entity.total_info = counters["total_info"]
    validation_report_entity.total_warning = counters["total_warning"]
    validation_report_entity.total_error = counters["total_error"]
    validation_report_entity.unique_info_count = counters["unique_info_count"]
    validation_report_entity.unique_warning_count = counters["unique_warning_count"]
    validation_report_entity.unique_error_count = counters["unique_error_count"]


def populate_service_date(dataset, json_report, timezone=None):
    """
    Populates the service date range of the dataset based on the JSON report.
    The service date range is extracted from the feedServiceWindowStart and feedServiceWindowEnd fields,
     if both are present and not empty.
    """
    feed_service_window_start = get_nested_value(
        json_report, ["summary", "feedInfo", "feedServiceWindowStart"]
    )
    feed_service_window_end = get_nested_value(
        json_report, ["summary", "feedInfo", "feedServiceWindowEnd"]
    )
    if (
        result := get_service_date_range_with_timezone_utc(
            feed_service_window_start, feed_service_window_end, timezone
        )
    ) is not None:
        utc_service_start_date, utc_service_end_date = result
        dataset.service_date_range_start = utc_service_start_date
        dataset.service_date_range_end = utc_service_end_date


@with_db_session
def create_validation_report_entities(
    feed_stable_id, dataset_stable_id, version, db_session
):
    """
    Creates and stores entities based on a validation report.
    This includes the validation report itself, related feature entities,
    and any notices found within the report.

    :param feed_stable_id: Stable ID of the feed
    :param dataset_stable_id: Stable ID of the dataset
    :param version: Version of the validator
    :return: Tuple List of all entities created (Validationreport, Feature, Notice) and status code
    """
    json_report_url = (
        f"{FILES_ENDPOINT}/{feed_stable_id}/{dataset_stable_id}/report_{version}.json"
    )
    logging.info(f"Accessing JSON report at {json_report_url}.")
    json_report, code = validate_json_report(json_report_url)
    if code != 200:
        return json_report, code

    try:
        validated_at, version_from_json = parse_json_report(json_report)
    except Exception as error:
        return str(error), 500

    try:
        # Generate the database entities required for the report
        # If an error is thrown we should let the retry mechanism to do its work
        entities = generate_report_entities(
            # default to the version parameter
            version_from_json if version_from_json else version,
            validated_at,
            json_report,
            dataset_stable_id,
            db_session,
            feed_stable_id,
        )

        for entity in entities:
            db_session.add(entity)
        # In this case the report entities are already in the DB or cannot be saved for other reasons
        # In any case, this will fail in any retried event
        try:
            logging.info("Committing %s entities to the database.", len(entities))
            db_session.commit()
            logging.info("Entities committed successfully.")
        except Exception as error:
            logging.warning(
                "Could not commit %s entities to the database: %s", entities, error
            )
            return str(error), 200

        update_feed_statuses_query(db_session, [feed_stable_id])
        result = f"Created {len(entities)} entities."
        logging.info(result)
        return result, 200
    except Exception as error:
        logging.error("Error creating validation report entities: : %s", error)
        return f"Error creating validation report entities: {error}", 500
    finally:
        pass


def get_validation_report(report_id, session):
    """
    Retrieves a ValidationReport object by its ID from the database.
    :param report_id: The ID of the report
    :param session: The database session
    :return: ValidationReport instance or None if not found
    """
    return (
        session.query(Validationreport).filter(Validationreport.id == report_id).first()
    )


@functions_framework.http
def process_validation_report(request):
    """
    Processes a validation report by creating necessary entities in the database.
    It expects a JSON request body with 'dataset_id' and 'feed_id'.

    :param request: Request object containing 'dataset_id' and 'feed_id'
    :return: HTTP response indicating the result of the operation
    """
    request_json = request.get_json(silent=True)
    logging.info(
        "Processing validation report function called with request: %s", request_json
    )
    if (
        not request_json
        or "dataset_id" not in request_json
        or "feed_id" not in request_json
        or "validator_version" not in request_json
    ):
        return (
            f"Invalid request body: {request_json}. We expect 'dataset_id', 'feed_id' and 'validator_version' to be "
            f"present.",
            400,
        )

    dataset_id = request_json["dataset_id"]
    feed_id = request_json["feed_id"]
    validator_version = request_json["validator_version"]
    logging.info(
        "Processing validation report version: %s for dataset: %s in feed: %s.",
        validator_version,
        dataset_id,
        feed_id,
    )
    return create_validation_report_entities(feed_id, dataset_id, validator_version)


@functions_framework.http
@with_db_session
def compute_validation_report_counters(request, db_session: Session):
    """
    Compute the total number of errors, warnings, and info notices,
    as well as the number of distinct codes for each severity level
    across all validation reports in the database, and write the results to the database.
    """
    batch_size = 100  # Number of reports to process in each batch
    offset = 0
    notice_exists = (
        db_session.query(Notice)
        .filter(Notice.validation_report_id == Validationreport.id)
        .exists()
    )

    while True:
        validation_reports = (
            db_session.query(Validationreport)
            .filter(
                (Validationreport.unique_info_count == 0)
                & (Validationreport.unique_warning_count == 0)
                & (Validationreport.unique_error_count == 0)
                & notice_exists
            )
            .order_by(Validationreport.validated_at.desc())
            .limit(batch_size)
            .offset(offset)
            .all()
        )
        logging.info(
            "Processing %s validation reports from offset: %s.",
            len(validation_reports),
            offset,
        )
        # Break the loop if no more reports are found
        if len(validation_reports) == 0:
            break

        for report in validation_reports:
            populate_counters(report.notices, report)
            logging.info(
                "Updated ValidationReport %s with counters: "
                "INFO=%s, WARNING=%s, ERROR=%s, "
                "Unique INFO Code=%s, Unique WARNING Code=%s, "
                "Unique ERROR Code=%s",
                report.id,
                report.total_info,
                report.total_warning,
                report.total_error,
                report.unique_info_count,
                report.unique_warning_count,
                report.unique_error_count,
            )

        # Commit the changes for the current batch
        db_session.commit()

        # Last page
        if len(validation_reports) < batch_size:
            break

    return {"message": "Validation report counters computed successfully."}, 200


def process_validation_report_notices(notices):
    """
    Processes the notices of a validation report and computes counters for different severities.

    :param report: A Validationreport object containing associated notices.
    :return: A dictionary with computed counters for total and unique counts of INFO, WARNING, and ERROR severities.
    """
    # Initialize counters for the current report
    total_info, total_warning, total_error = 0, 0, 0
    info_codes, warning_codes, error_codes = set(), set(), set()

    # Process associated notices
    for notice in notices:
        match notice.severity:
            case "INFO":
                total_info += notice.total_notices
                info_codes.add(notice.notice_code)
            case "WARNING":
                total_warning += notice.total_notices
                warning_codes.add(notice.notice_code)
            case "ERROR":
                total_error += notice.total_notices
                error_codes.add(notice.notice_code)
            case _:
                logging.warning("Unknown severity: %s", notice.severity)

    return {
        "total_info": total_info,
        "total_warning": total_warning,
        "total_error": total_error,
        "unique_info_count": len(info_codes),
        "unique_warning_count": len(warning_codes),
        "unique_error_count": len(error_codes),
    }
