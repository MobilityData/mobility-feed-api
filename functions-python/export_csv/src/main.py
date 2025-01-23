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
import argparse
import os
import re

import pandas as pd

from dotenv import load_dotenv
import functions_framework

from packaging.version import Version
from functools import reduce

from geoalchemy2.shape import to_shape

from shared.database_gen.sqlacodegen_models import Gtfsfeed, Gtfsrealtimefeed
from collections import OrderedDict
from shared.common.db_utils import get_all_gtfs_rt_feeds_query, get_all_gtfs_feeds_query

from shared.helpers.database import Database

load_dotenv()
csv_default_file_path = "./output.csv"
csv_file_path = csv_default_file_path


class DataCollector:
    """
    A class used to collect and organize data into rows and headers for CSV output.
    One particularity of this class is that it uses an OrderedDict to store the data, so that the order of the columns
    is preserved when writing to CSV.
    """

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

    def write_csv_to_file(self, csv_file_path):
        df = pd.DataFrame(self.rows, columns=self.headers)
        df.to_csv(csv_file_path, index=False)

    def get_dataframe(self) -> pd:
        return pd.DataFrame(self.rows, columns=self.headers)


@functions_framework.http
def export_csv(request=None):
    """
    HTTP Function entry point Reads the DB and outputs a csv file with feeds data.
    This function requires the following environment variables to be set:
        FEEDS_DATABASE_URL: database URL
    :param request: HTTP request object
    :return: HTTP response object
    """
    data_collector = collect_data()
    data_collector.write_csv_to_file(csv_file_path)
    return f"Export of database feeds to CSV file {csv_file_path}."


def collect_data() -> DataCollector:
    """
    Collect data from the DB and write the output to a DataCollector.
    :return: A filled DataCollector
    """
    db = Database(database_url=os.getenv("FEEDS_DATABASE_URL"))
    try:
        with db.start_db_session() as session:
            gtfs_feeds_query = get_all_gtfs_feeds_query(
                include_wip=False,
                db_session=session,
            )

            gtfs_feeds = gtfs_feeds_query.all()

            print(f"Retrieved {len(gtfs_feeds)} GTFS feeds.")

            gtfs_rt_feeds_query = get_all_gtfs_rt_feeds_query(
                include_wip=False,
                db_session=session,
            )

            gtfs_rt_feeds = gtfs_rt_feeds_query.all()

            print(f"Retrieved {len(gtfs_rt_feeds)} GTFS realtime feeds.")

            data_collector = DataCollector()

            for feed in gtfs_feeds:
                # print(f"Processing feed {feed.stable_id}")
                data = get_feed_csv_data(feed)

                for key, value in data.items():
                    data_collector.add_data(key, value)
                data_collector.finalize_row()
            print(f"Procewssed {len(gtfs_feeds)} GTFS feeds.")

            for feed in gtfs_rt_feeds:
                # print(f"Processing rt feed {feed.stable_id}")
                data = get_gtfs_rt_feed_csv_data(feed)
                for key, value in data.items():
                    data_collector.add_data(key, value)
                data_collector.finalize_row()
            print(f"Processed {len(gtfs_rt_feeds)} GTFS realtime feeds.")

    except Exception as error:
        print(f"Error retrieving feeds: {error}")
        raise Exception(f"Error retrieving feeds: {error}")
    data_collector.write_csv_to_file(csv_file_path)
    return data_collector


def extract_numeric_version(version):
    match = re.match(r"(\d+\.\d+\.\d+)", version)
    return match.group(1) if match else version


def get_feed_csv_data(feed: Gtfsfeed):
    """
    This function takes a GtfsFeed and returns a dictionary with the data to be written to the CSV file.
    """
    latest_dataset = next(
        (
            dataset
            for dataset in (feed.gtfsdatasets or [])
            if dataset and dataset.latest
        ),
        None,
    )

    joined_features = ""
    validated_at = None
    minimum_latitude = maximum_latitude = minimum_longitude = maximum_longitude = None

    if latest_dataset and latest_dataset.validation_reports:
        # Keep the report from the more recent validator version
        latest_report = reduce(
            lambda a, b: a
            if Version(extract_numeric_version(a.validator_version))
            > Version(extract_numeric_version(b.validator_version))
            else b,
            latest_dataset.validation_reports,
        )

        if latest_report:
            if latest_report.features:
                features = latest_report.features
                joined_features = (
                    "|".join(
                        sorted(feature.name for feature in features if feature.name)
                    )
                    if features
                    else ""
                )
            if latest_report.validated_at:
                validated_at = latest_report.validated_at
        if latest_dataset.bounding_box:
            shape = to_shape(latest_dataset.bounding_box)
            if shape and shape.bounds:
                minimum_latitude = shape.bounds[1]
                maximum_latitude = shape.bounds[3]
                minimum_longitude = shape.bounds[0]
                maximum_longitude = shape.bounds[2]

    data = {
        "id": feed.stable_id,
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
        "urls.direct_download": feed.producer_url,
        "urls.authentication_type": feed.authentication_type,
        "urls.authentication_info": feed.authentication_info_url,
        "urls.api_key_parameter_name": feed.api_key_parameter_name,
        "urls.latest": latest_dataset.hosted_url if latest_dataset else None,
        "urls.license": feed.license_url,
        "location.bounding_box.minimum_latitude": minimum_latitude,
        "location.bounding_box.maximum_latitude": maximum_latitude,
        "location.bounding_box.minimum_longitude": minimum_longitude,
        "location.bounding_box.maximum_longitude": maximum_longitude,
        "location.bounding_box.extracted_on": validated_at,
        # We use the report validated_at date as the extracted_on date
        "status": feed.status,
        "features": joined_features,
    }

    redirect_ids = ""
    redirect_comments = ""
    # Add concatenated redirect IDs
    if feed.redirectingids:
        for redirect in feed.redirectingids:
            if redirect and redirect.target and redirect.target.stable_id:
                stripped_id = redirect.target.stable_id.strip()
                if stripped_id:
                    redirect_ids = (
                        redirect_ids + "|" + stripped_id
                        if redirect_ids
                        else stripped_id
                    )
                    redirect_comments = (
                        redirect_comments + "|" + redirect.redirect_comment
                        if redirect_comments
                        else redirect.redirect_comment
                    )
        if redirect_ids == "":
            redirect_comments = ""
        else:
            # If there is no comment but we do have redirects, use an empty string instead of a
            # potentially a bunch of vertical bars.
            redirect_comments = (
                "" if redirect_comments.strip("|") == "" else redirect_comments
            )

    data["redirect.id"] = redirect_ids
    data["redirect.comment"] = redirect_comments

    return data


def get_gtfs_rt_feed_csv_data(feed: Gtfsrealtimefeed):
    """
    This function takes a GtfsRTFeed and returns a dictionary with the data to be written to the CSV file.
    """
    entity_types = ""
    if feed.entitytypes:
        valid_entity_types = [
            entity_type.name.strip()
            for entity_type in feed.entitytypes
            if entity_type and entity_type.name
        ]
        valid_entity_types = sorted(valid_entity_types)
        entity_types = "|".join(valid_entity_types)

    static_references = ""
    if feed.gtfs_feeds:
        valid_feed_references = [
            feed_reference.stable_id.strip()
            for feed_reference in feed.gtfs_feeds
            if feed_reference and feed_reference.stable_id
        ]
        static_references = "|".join(valid_feed_references)

    data = {
        "id": feed.stable_id,
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
        "urls.direct_download": feed.producer_url,
        "urls.authentication_type": feed.authentication_type,
        "urls.authentication_info": feed.authentication_info_url,
        "urls.api_key_parameter_name": feed.api_key_parameter_name,
        "urls.latest": None,
        "urls.license": feed.license_url,
        "location.bounding_box.minimum_latitude": None,
        "location.bounding_box.maximum_latitude": None,
        "location.bounding_box.minimum_longitude": None,
        "location.bounding_box.maximum_longitude": None,
        "location.bounding_box.extracted_on": None,
        "features": None,
        "redirect.id": None,
        "redirect.comment": None,
    }

    return data


def main():
    global csv_file_path
    parser = argparse.ArgumentParser(description="Export DB feed contents to csv.")
    parser.add_argument(
        "--outpath", help="Path to the output csv file. Default is ./output.csv"
    )
    args = parser.parse_args()
    csv_file_path = args.outpath if args.outpath else csv_default_file_path
    export_csv()


if __name__ == "__main__":
    main()
