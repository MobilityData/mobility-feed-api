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
import csv
import logging
import os
import re
from typing import Dict, Iterator

from dotenv import load_dotenv
import functions_framework

from packaging.version import Version
from google.cloud import storage
from geoalchemy2.shape import to_shape

from shared.helpers.logger import Logger
from shared.database_gen.sqlacodegen_models import Gtfsfeed, Gtfsrealtimefeed
from shared.common.db_utils import get_all_gtfs_rt_feeds_query, get_all_gtfs_feeds_query

from shared.helpers.database import Database

load_dotenv()
csv_default_file_path = "./output.csv"

# This needs to be updated if we add fields to either `get_feed_csv_data` or
# `get_gtfs_rt_feed_csv_data`, otherwise the extra field(s) will be excluded from
# the generated CSV file.
headers = [
    "id",
    "data_type",
    "entity_type",
    "location.country_code",
    "location.subdivision_name",
    "location.municipality",
    "provider",
    "name",
    "note",
    "feed_contact_email",
    "static_reference",
    "urls.direct_download",
    "urls.authentication_type",
    "urls.authentication_info",
    "urls.api_key_parameter_name",
    "urls.latest",
    "urls.license",
    "location.bounding_box.minimum_latitude",
    "location.bounding_box.maximum_latitude",
    "location.bounding_box.minimum_longitude",
    "location.bounding_box.maximum_longitude",
    "location.bounding_box.extracted_on",
    "status",
    "features",
    "redirect.id",
    "redirect.comment",
]


@functions_framework.http
def export_and_upload_csv(request=None):
    """
    HTTP Function entry point Reads the DB and outputs a csv file with feeds data.
    This function requires the following environment variables to be set:
        FEEDS_DATABASE_URL: database URL
    :param request: HTTP request object
    :return: HTTP response object
    """
    Logger.init_logger()
    logging.info("Export started")

    csv_file_path = csv_default_file_path
    export_csv(csv_file_path)
    upload_file_to_storage(csv_file_path, "sources_v2.csv")

    logging.info("Export successful")
    return "Export successful"


def export_csv(csv_file_path: str):
    """
    Write feed data to a local CSV file.
    """
    with open(csv_file_path, "w") as out:
        writer = csv.DictWriter(out, fieldnames=headers)
        writer.writeheader()

        count = 0
        for feed in fetch_feeds():
            writer.writerow(feed)
            count += 1

    logging.info(f"Exported {count} feeds to CSV file {csv_file_path}.")


def fetch_feeds() -> Iterator[Dict]:
    """
    Fetch and return feed data from the DB.
    :return: Data to write to the output CSV file.
    """
    db = Database(database_url=os.getenv("FEEDS_DATABASE_URL"))
    logging.info(f"Using database {db.database_url}")
    try:
        with db.start_db_session(echo=True) as session:
            feed_count = 0
            # We should _not_ use `.all()` on the query to avoid loading all
            # the feeds upfront.
            for feed in get_all_gtfs_feeds_query(session):
                yield get_feed_csv_data(feed)
                feed_count += 1

            logging.info(f"Processed {feed_count} GTFS feeds.")

            rt_feed_count = 0
            # We should _not_ use `.all()` on the query to avoid loading all
            # the feeds upfront.
            for feed in get_all_gtfs_rt_feeds_query(session):
                yield get_gtfs_rt_feed_csv_data(feed)
                rt_feed_count += 1

            logging.info(f"Processed {rt_feed_count} GTFS realtime feeds.")
    except Exception as error:
        logging.error(f"Error retrieving feeds: {error}")
        raise Exception(f"Error retrieving feeds: {error}")


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
        latest_report = max(
            latest_dataset.validation_reports,
            key=lambda r: Version(extract_numeric_version(r.validator_version)),
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

    latest_url = latest_dataset.hosted_url if latest_dataset else None
    if latest_url:
        # The url for the latest dataset contains the dataset id which includes the date.
        # e.g. https://dev-files.mobilitydatabase.org/mdb-1/mdb-1-202408202229/mdb-1-202408202229.zip
        # For the latest url we just want something using latest.zip, e.g:
        # https://dev-files.mobilitydatabase.org/mdb-1/latest.zip
        # So use the dataset url, but replace what is after the feed stable id by latest.zip
        position = latest_url.find(feed.stable_id)
        if position != -1:
            # Construct the new URL
            latest_url = latest_url[: position + len(feed.stable_id) + 1] + "latest.zip"

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
        "urls.latest": latest_url,
        "urls.license": feed.license_url,
        "location.bounding_box.minimum_latitude": minimum_latitude,
        "location.bounding_box.maximum_latitude": maximum_latitude,
        "location.bounding_box.minimum_longitude": minimum_longitude,
        "location.bounding_box.maximum_longitude": maximum_longitude,
        # We use the report validated_at date as the extracted_on date
        "location.bounding_box.extracted_on": validated_at,
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


def upload_file_to_storage(source_file_path, target_path):
    """
    Uploads a file to the GCP bucket
    """
    bucket_name = os.getenv("DATASETS_BUCKET_NAME")
    logging.info(f"Uploading file to bucket {bucket_name} at path {target_path}")
    bucket = storage.Client().get_bucket(bucket_name)
    blob = bucket.blob(target_path)
    with open(source_file_path, "rb") as file:
        blob.upload_from_file(file)
    blob.make_public()
    return blob


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export DB feed contents to csv.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--outpath",
        default=csv_default_file_path,
        help="Path to the output csv file.",
    )
    os.environ[
        "FEEDS_DATABASE_URL"
    ] = "postgresql://postgres:postgres@localhost:54320/MobilityDatabaseTest"
    args = parser.parse_args()
    export_csv(args.outpath)
