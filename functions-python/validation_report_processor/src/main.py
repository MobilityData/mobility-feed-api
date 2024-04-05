#
#   MobilityData 2023
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
from datetime import datetime
import requests
import functions_framework
from database_gen.sqlacodegen_models import (
    Validationreport,
    Feature,
    Notice,
    Gtfsdataset,
)
from helpers.database import start_db_session, close_db_session

FILES_ENDPOINT = os.getenv("FILES_ENDPOINT")


def read_json_report(json_report_url):
    """
    Fetches and returns the JSON content from a given URL.

    :param json_report_url: URL to the JSON report
    :return: Dict representation of the JSON report
    """
    response = requests.get(json_report_url)
    return response.json()


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
    Retrieves a Gtfsdataset object by its stable ID from the database.

    :param dataset_stable_id: Stable ID of the dataset
    :param session: Database session instance
    :return: Gtfsdataset instance or None if not found
    """
    return (
        session.query(Gtfsdataset)
        .filter(Gtfsdataset.stable_id == dataset_stable_id)
        .one_or_none()
    )


def create_validation_report_entities(feed_stable_id, dataset_stable_id):
    """
    Creates and stores entities based on a validation report.
    This includes the validation report itself, related feature entities,
    and any notices found within the report.

    :param feed_stable_id: Stable ID of the feed
    :param dataset_stable_id: Stable ID of the dataset
    :return: Tuple List of all entities created (Validationreport, Feature, Notice) and status code
    """
    entities = []

    json_report_url = (
        f"{FILES_ENDPOINT}/{feed_stable_id}/{dataset_stable_id}/report.json"
    )
    try:
        json_report = read_json_report(json_report_url)
    except Exception as error:
        print(f"Error reading JSON report: {error}")
        return f"Error reading JSON report: {error}", 500

    try:
        dt = json_report["summary"]["validatedAt"]
        validated_at = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        version = json_report["summary"]["validatorVersion"]
    except Exception as error:
        print(f"Error parsing JSON report: {error}")
        return f"Error parsing JSON report: {error}", 500

    report_id = f"{dataset_stable_id}_{version}"
    html_report_url = (
        f"{FILES_ENDPOINT}/{feed_stable_id}/{dataset_stable_id}/report.html"
    )

    print(f"Creating validation report entities for {report_id}.")
    print(f"JSON report URL: {json_report_url}")
    print(f"HTML report URL: {html_report_url}")

    session = None
    try:
        session = start_db_session(os.getenv("FEEDS_DATABASE_URL"))
        # Validation Report Entity
        if get_validation_report(report_id, session):  # Check if report already exists
            return f"Validation report {report_id} already exists.", 409
        validation_report_entity = Validationreport(
            id=report_id,
            validator_version=version,
            validated_at=validated_at,
            html_report=html_report_url,
            json_report=json_report_url,
        )
        entities.append(validation_report_entity)

        dataset = get_dataset(dataset_stable_id, session)
        for feature_name in json_report["summary"]["gtfsFeatures"]:
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
            entities.append(notice_entity)
        for entity in entities:
            session.add(entity)
        session.commit()
        return f"Created {len(entities)} entities.", 200
    except Exception as error:
        print(f"Error creating validation report entities: {error}")
        return f"Error creating validation report entities: {error}", 500
    finally:
        close_db_session(session)


def get_validation_report(report_id, session):
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
    if (
        not request_json
        or "dataset_id" not in request_json
        or "feed_id" not in request_json
    ):
        return "Invalid request", 400

    dataset_id = request_json["dataset_id"]
    feed_id = request_json["feed_id"]
    return create_validation_report_entities(feed_id, dataset_id)
