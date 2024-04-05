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

import json
import os
import uuid
from datetime import datetime
import requests

import functions_framework
from database_gen.sqlacodegen_models import Validationreport, Feature, Notice, Gtfsdataset
from helpers.database import start_db_session, close_db_session

FILES_ENDPOINT = os.getenv("FILES_ENDPOINT")


def read_json_report(json_report_url):
    response = requests.get(json_report_url)
    return response.json()


def get_feature(feature_name, session):
    feature = session.query(Feature).filter(Feature.name == feature_name).first()
    if not feature:
        feature = Feature(name=feature_name)
    return feature


def get_dataset(dataset_stable_id, session):
    return session.query(Gtfsdataset).filter(Gtfsdataset.stable_id == dataset_stable_id).one_or_none()


def create_validation_report_entities(feed_stable_id, dataset_stable_id):
    # TODO: Add header and make function better
    entities = []

    json_report_url = f"{FILES_ENDPOINT}/{feed_stable_id}/{dataset_stable_id}/report.json"
    json_report = read_json_report(json_report_url)
    validated_at = json_report["summary"]["validatedAt"]
    version = json_report["summary"]["validatorVersion"]

    report_id = f"{dataset_stable_id}_{version}"
    html_report_url = f"{FILES_ENDPOINT}/{feed_stable_id}/{dataset_stable_id}/report.html"

    print(f"Creating validation report entities for {report_id}.")
    print(f"JSON report URL: {json_report_url}")
    print(f"HTML report URL: {html_report_url}")

    # Validation Report Entity
    validation_report_entity = Validationreport(
        id=report_id,
        validator_version=version,
        validated_at=validated_at,
        html_report=html_report_url,
        json_report=json_report_url,
    )
    entities.append(validation_report_entity)

    # Feature Entities
    session = None
    try:
        session = start_db_session(os.getenv("FEEDS_DATABASE_URL"))
        dataset = get_dataset(dataset_stable_id, session)
        for feature_name in json_report["summary"]["gtfsFeatures"]:
            feature = get_feature(feature_name, session)
            feature.validations.append(validation_report_entity)
            entities.append(feature)
        for notice in json_report["notices"]:
            notice_code = notice["code"]
            notice = Notice(
                dataset_id=dataset.id,
                validation_report_id=report_id,
                notice_code=notice_code,
                severity=notice["severity"],
                total_notices=notice["totalNotices"],
            )
            entities.append(notice)
        for entity in entities:
            session.add(entity)
        session.commit()
        return entities
    except Exception as error:
        print(f"Error creating validation report entities: {error}")
        raise error
    finally:
        close_db_session(session)


@functions_framework.http
def process_validation_report(request):
    """
    HTTP Function entry point queries the datasets and publishes them to a Pub/Sub topic to be processed.
    This function requires the following environment variables to be set:
        FEEDS_DATABASE_URL: database URL
        PROJECT_ID: GCP project ID
        FILES_ENDPOINT: endpoint to download files from
    :param request: HTTP request object
    # TODO specify the format of the request body
    :return: HTTP response object
    """
    request_json = request.get_json(silent=True)
    print(request_json)
    dataset_id = request_json["dataset_id"]
    feed_id = request_json["feed_id"]
    create_validation_report_entities(feed_id, dataset_id)
    return f"Publish completed. Published {len([])} feeds to test."
