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
import json
from datetime import datetime

import pandas as pd
import os

from dotenv import load_dotenv
import functions_framework

# from dataset_service.main import BatchExecutionService, BatchExecution
from helpers.database import start_db_session, close_db_session

# from feeds_gen.apis.feeds_api_base import BaseFeedsApi
from feeds.impl.feeds_api_impl import FeedsApiImpl
from collections import OrderedDict


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


load_dotenv()


class DataCollector:
    def __init__(self):
        self.data = OrderedDict()
        self.rows = []
        self.headers = []

    def add_data(self, key, value):
        if key not in self.headers:
            self.headers.append(key)
        self.data[key] = value

    def finalize_row(self):
        self.rows.append(self.data.copy())
        self.data = OrderedDict()

    def write_csv(self, csv_file_path):
        df = pd.DataFrame(self.rows, columns=self.headers)
        df.to_csv(csv_file_path, index=False)


project_id = os.getenv("PROJECT_ID")


@functions_framework.http
def create_csv():
    """
    HTTP Function entry point queries the datasets and publishes them to a Pub/Sub topic to be processed.
    This function requires the following environment variables to be set:
        PUBSUB_TOPIC_NAME: name of the Pub/Sub topic to publish to
        FEEDS_DATABASE_URL: database URL
        PROJECT_ID: GCP project ID
    :param request: HTTP request object
    :return: HTTP response object
    """
    try:
        db_url = os.getenv("FEEDS_DATABASE_URL")
        session = start_db_session(db_url)

        gtfs_feeds = FeedsApiImpl().get_gtfs_feeds(
            limit=10,
            offset=0,
            provider=None,
            producer_url=None,
            country_code=None,
            subdivision_name=None,
            municipality=None,
            dataset_latitudes=None,
            dataset_longitudes=None,
            bounding_filter_method=None,
            never_return_wip=True,
        )

        gtfs_dict = [obj.to_dict() for obj in gtfs_feeds]

        # Convert the list of dictionaries to a JSON string
        json_string = json.dumps(gtfs_dict, indent=4, cls=CustomJSONEncoder)

        gtfs_rt_feeds = FeedsApiImpl().get_gtfs_rt_feeds(
            limit=10,
            offset=0,
            provider=None,
            producer_url=None,
            entity_types=None,
            country_code=None,
            subdivision_name=None,
            municipality=None,
            never_return_wip=True,
        )

        # Print the JSON string
        print(json_string)

    except Exception as error:
        print(f"Error retrieving feeds: {error}")
        raise Exception(f"Error retrieving feeds: {error}")
    finally:
        close_db_session(session)

    print(f"Retrieved {len(gtfs_feeds)} feeds.")

    data_collector = DataCollector()

    # Step 2: Add data to the DataFrame
    for feed in gtfs_feeds:
        print(f"Processing feed {feed.id}")
        data = get_feed_data(feed)

        for key, value in data.items():
            data_collector.add_data(key, value)
        data_collector.finalize_row()

    for feed in gtfs_rt_feeds:
        print(f"Processing rt feed {feed.id}")
        data = get_gtfs_rt_feed_data(feed)
        for key, value in data.items():
            data_collector.add_data(key, value)
        data_collector.finalize_row()

    csv_file_path = "/Users/jcpitre/Google Drive/My Drive/temp/output.csv"
    data_collector.write_csv(csv_file_path)

    return f"Printed {len(gtfs_feeds)} feeds to csv."


def get_feed_data(
    feed,
):  # id, latest, limit, offset, downloaded_after, downloaded_before
    feeds_api = FeedsApiImpl()
    latest_dataset = feeds_api.get_gtfs_feed_datasets(
        gtfs_feed_id=feed.id,
        latest=True,
        limit=None,
        offset=None,
        downloaded_after=None,
        downloaded_before=None,
    )

    # Get the features from the latest dataset
    joined_features = ""
    validated_at = None
    if latest_dataset and latest_dataset[0]:
        validation_report = latest_dataset[0].validation_report
        if validation_report:
            if validation_report.features:
                features = validation_report.features
                joined_features = "|".join(features) if features else ""
            if validation_report.validated_at:
                validated_at = validation_report.validated_at

    data = {
        "mdb_source_id": feed.id,
        "data_type": feed.data_type,
        "entity_type": None,
        "location.country_code": ""
        if not feed.locations or not feed.locations[0]
        else feed.locations[0].country_code,
        "location.subdivision_name": ""
        if not feed.locations or not feed.locations[0]
        else feed.locations[0].subdivision_name,
        "location.municipality": ""
        if not feed.locations or not feed.locations[0]
        else feed.locations[0].municipality,
        "provider": feed.provider,
        "name": feed.feed_name,
        "note": feed.note,
        "feed_contact_email": feed.feed_contact_email,
        "static_reference": None,
        "urls.direct_download": feed.source_info.producer_url,
        "urls.authentication_type": feed.source_info.authentication_type,
        "urls.authentication_info": feed.source_info.authentication_info_url,
        "urls.api_key_parameter_name": feed.source_info.api_key_parameter_name,
        "urls.latest": feed.latest_dataset.hosted_url if feed.latest_dataset else None,
        "urls.license": feed.source_info.license_url,
        "location.bounding_box.minimum_latitude": (
            feed.latest_dataset.bounding_box.minimum_latitude
            if feed.latest_dataset and feed.latest_dataset.bounding_box
            else None
        ),
        "location.bounding_box.maximum_latitude": (
            feed.latest_dataset.bounding_box.maximum_latitude
            if feed.latest_dataset and feed.latest_dataset.bounding_box
            else None
        ),
        "location.bounding_box.minimum_longitude": (
            feed.latest_dataset.bounding_box.minimum_longitude
            if feed.latest_dataset and feed.latest_dataset.bounding_box
            else None
        ),
        "location.bounding_box.maximum_longitude": (
            feed.latest_dataset.bounding_box.maximum_longitude
            if feed.latest_dataset and feed.latest_dataset.bounding_box
            else None
        ),
        "location.bounding_box.extracted_on": validated_at,
        # We use the report validated_at date as the extracted_on date
        "status": feed.status,
        "features": joined_features,
    }

    redirect_ids = ""
    redirect_comments = ""
    # Add concatenated redirect IDs
    if feed.redirects:
        valid_redirects = [redirect.target_id.strip() for redirect in feed.redirects]
        redirect_ids = "|".join(valid_redirects)
        valid_comments = [redirect.comment.strip() for redirect in feed.redirects]
        redirect_comments = "|".join(valid_comments) if any(valid_comments) else ""

    data["redirect.id"] = redirect_ids
    data["redirect.comment"] = redirect_comments

    return data


def get_gtfs_rt_feed_data(
    feed,
):  # id, latest, limit, offset, downloaded_after, downloaded_before
    entity_types = ""
    if feed.entity_types:
        valid_entity_types = [
            entity_type.strip() for entity_type in feed.entity_types if entity_type
        ]
        entity_types = "|".join(valid_entity_types)

    static_references = ""
    if feed.feed_references:
        valid_feed_references = [
            reference.strip() for reference in feed.feed_references if reference
        ]
        static_references = "|".join(valid_feed_references)

    data = {
        "mdb_source_id": feed.id,
        "data_type": feed.data_type,
        "entity_type": entity_types,
        "location.country_code": ""
        if not feed.locations or not feed.locations[0]
        else feed.locations[0].country_code,
        "location.subdivision_name": ""
        if not feed.locations or not feed.locations[0]
        else feed.locations[0].subdivision_name,
        "location.municipality": ""
        if not feed.locations or not feed.locations[0]
        else feed.locations[0].municipality,
        "provider": feed.provider,
        "name": feed.feed_name,
        "note": feed.note,
        "feed_contact_email": feed.feed_contact_email,
        "static_reference": static_references,
        "urls.direct_download": feed.source_info.producer_url,
        "urls.authentication_type": feed.source_info.authentication_type,
        "urls.authentication_info": feed.source_info.authentication_info_url,
        "urls.api_key_parameter_name": feed.source_info.api_key_parameter_name,
        "urls.latest": None,
        "urls.license": feed.source_info.license_url,
        "location.bounding_box.minimum_latitude": None,
        "location.bounding_box.maximum_latitude": None,
        "location.bounding_box.minimum_longitude": None,
        "location.bounding_box.maximum_longitude": None,
        "location.bounding_box.extracted_on": None,
        "features": None,
    }

    redirect_ids = ""
    redirect_comments = ""
    # Add concatenated redirect IDs
    if feed.redirects:
        valid_redirects = [redirect.target_id.strip() for redirect in feed.redirects]
        redirect_ids = "|".join(valid_redirects)
        valid_comments = [redirect.comment.strip() for redirect in feed.redirects]
        redirect_comments = "|".join(valid_comments) if any(valid_comments) else ""

    data["redirect.id"] = redirect_ids
    data["redirect.comment"] = redirect_comments

    return data


def main():
    # parser = argparse.ArgumentParser(description="Retrieve and print non-deprecated feeds.")
    # args = parser.parse_args()
    create_csv()


if __name__ == "__main__":
    main()
