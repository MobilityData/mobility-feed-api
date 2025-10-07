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
from typing import Dict, Iterator, Optional
from natsort import natsorted
from dotenv import load_dotenv
from sqlalchemy.orm import Session
import functions_framework

from packaging.version import Version
from google.cloud import storage
from geoalchemy2.shape import to_shape

from shared.database.database import with_db_session
from shared.helpers.logger import init_logger
from shared.database_gen.sqlacodegen_models import Gtfsfeed, Gtfsrealtimefeed, Feed
from shared.common.db_utils import (
    get_all_gtfs_rt_feeds,
    get_all_gtfs_feeds,
    get_geopolygons,
)

from shared.database_gen.sqlacodegen_models import Geopolygon

load_dotenv()
csv_default_file_path = "./output.csv"
init_logger()
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
    "is_official",
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


class BoundingBox:
    """
    Class used to keep the GTFS feed bounding box in a lookup table so it can be used in associated real-time feeds.
    """

    def __init__(
        self,
        minimum_latitude=None,
        maximum_latitude=None,
        minimum_longitude=None,
        maximum_longitude=None,
        extracted_on=None,
    ):
        self.minimum_latitude = minimum_latitude
        self.maximum_latitude = maximum_latitude
        self.minimum_longitude = minimum_longitude
        self.maximum_longitude = maximum_longitude
        self.extracted_on = extracted_on

    def fill_data(self, data):
        data["location.bounding_box.minimum_latitude"] = self.minimum_latitude
        data["location.bounding_box.maximum_latitude"] = self.maximum_latitude
        data["location.bounding_box.minimum_longitude"] = self.minimum_longitude
        data["location.bounding_box.maximum_longitude"] = self.maximum_longitude
        data["location.bounding_box.extracted_on"] = self.extracted_on


bounding_box_lookup = {}


@functions_framework.http
def export_and_upload_csv(_):
    """
    HTTP Function entry point Reads the DB and outputs a csv file with feeds data.
    This function requires the following environment variables to be set:
        FEEDS_DATABASE_URL: database URL
    :return: HTTP response object
    """
    logging.info("Export started")

    csv_file_path = csv_default_file_path
    export_csv(csv_file_path)
    upload_file_to_storage(csv_file_path, "feeds_v2.csv")

    logging.info("Export successful")
    return "Export successful"


def export_csv(csv_file_path: str):
    """
    Write feed data to a local CSV file.
    """
    with open(csv_file_path, "w") as out:
        writer = csv.DictWriter(out, fieldnames=headers)
        writer.writeheader()

        feeds = list(fetch_feeds())
        sorted_feeds = natsorted(feeds, key=lambda x: x["id"])
        for feed in sorted_feeds:
            writer.writerow(feed)

    logging.info(f"Exported {len(feeds)} feeds to CSV file {csv_file_path}.")


def process_feeds(
    query_fun: callable, processing_fun: callable, db_session: Session
) -> Iterator[Dict]:
    """
    Process feeds from the database and yield the results.
    :param query_fun: Function to query feeds from the database.
    :param processing_fun: Function to process each feed.
    :param db_session: Database session.
    :return: Yields processed feed data.
    """
    stable_ids = set()
    for w_extracted_locations_only in (True, False):
        feeds = list(
            query_fun(
                db_session,
                published_only=True,
                w_extracted_locations_only=w_extracted_locations_only,
            )
        )
        geopolygons_map = (
            get_geopolygons(db_session, feeds) if w_extracted_locations_only else None
        )
        for feed in feeds:
            if feed.stable_id in stable_ids:
                continue
            stable_ids.add(feed.stable_id)
            yield processing_fun(feed, geopolygons_map)
        logging.info(
            f"Found {len(feeds)} feeds " + "with location data."
            if w_extracted_locations_only
            else "no location data."
        )


@with_db_session
def fetch_feeds(db_session: Session) -> Iterator[Dict]:
    """
    Fetch and return feed data from the DB.
    :return: Data to write to the output CSV file.
    """
    try:
        logging.info("Processing GTFS feeds...")
        yield from process_feeds(get_all_gtfs_feeds, get_gtfs_feed_csv_data, db_session)

        logging.info("Processing GTFS RT feeds...")
        yield from process_feeds(
            get_all_gtfs_rt_feeds, get_gtfs_rt_feed_csv_data, db_session
        )

    except Exception as error:
        logging.error(f"Error retrieving feeds: {error}")
        raise Exception(f"Error retrieving feeds: {error}")


def extract_numeric_version(version):
    match = re.match(r"(\d+\.\d+\.\d+)", version)
    return match.group(1) if match else version


def get_gtfs_feed_csv_data(
    feed: Gtfsfeed, geopolygon_map: Optional[Dict[str, Geopolygon]]
) -> Dict:
    """
    This function takes a Gtfsfeed object and returns a dictionary with the data to be written to the CSV file.
    :param feed: Gtfsfeed object containing feed data.
    :return: Dictionary with feed data formatted for CSV output.
    """
    joined_features = ""
    bounding_box = None

    # First extract the common feed data
    data = get_feed_csv_data(feed, geopolygon_map)

    # Then supplement with the GTFS specific data
    latest_dataset = next(
        (
            dataset
            for dataset in (feed.gtfsdatasets or [])
            if dataset and dataset.latest
        ),
        None,
    )
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
    if feed.bounding_box:
        shape = to_shape(feed.bounding_box)
        if shape and shape.bounds:
            bounding_box = BoundingBox(
                minimum_latitude=shape.bounds[1],
                maximum_latitude=shape.bounds[3],
                minimum_longitude=shape.bounds[0],
                maximum_longitude=shape.bounds[2],
                extracted_on=feed.bounding_box_dataset.downloaded_at,
            )

    # Keep the bounding box for that GTFS feed so it can be used in associated real-time feeds, if any
    if bounding_box:
        bounding_box.fill_data(data)
        bounding_box_lookup[feed.id] = bounding_box

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
    data["urls.latest"] = latest_url
    data["features"] = joined_features

    return data


def get_location_data(
    feed: Feed, geopolygon_map: Optional[Dict[str, Geopolygon]]
) -> tuple:
    """Extract location data from a feed with fallbacks for missing values."""
    if not geopolygon_map or not feed.feedosmlocationgroups:
        if not feed.locations:
            return "", "", ""
        sorted_locations = sorted(feed.locations, key=lambda location: location.id)
        return (
            sorted_locations[0].country_code,
            sorted_locations[0].subdivision_name,
            sorted_locations[0].municipality,
        )
    osm_location_group = next(
        (
            group
            for group in sorted(
                feed.feedosmlocationgroups, key=lambda g: g.group.group_name
            )
        )
    )
    group_id = osm_location_group.group_id
    split_group_id = [osm_id.strip() for osm_id in group_id.split(".")]
    if not split_group_id:
        logging.error(f"Invalid group ID: {group_id}")
        return "", "", ""
    country_osm_id = split_group_id[0]
    subdivision_osm_id = split_group_id[1] if len(split_group_id) > 1 else None
    municipality_osm_id = split_group_id[-1] if len(split_group_id) > 2 else None

    country_code = (
        geopolygon_map.get(country_osm_id).iso_3166_1_code
        if country_osm_id in geopolygon_map
        else None
    )
    subdivision_name = (
        geopolygon_map.get(subdivision_osm_id).name
        if subdivision_osm_id in geopolygon_map
        else None
    )
    municipality = (
        geopolygon_map.get(municipality_osm_id).name
        if municipality_osm_id in geopolygon_map
        else None
    )
    return country_code, subdivision_name, municipality


def get_feed_csv_data(
    feed: Feed, geopolygon_map: Optional[Dict[str, Geopolygon]]
) -> Dict:
    """
    This function takes a generic feed and returns a dictionary with the data to be written to the CSV file.
    Any specific data (for GTFS or GTFS_RT has to be added after this call.
    """

    redirect_ids = []
    redirect_comments = []
    # Add concatenated redirect IDs
    sorted_redirects = sorted(feed.redirectingids, key=lambda x: x.target.stable_id)
    if sorted_redirects:
        for redirect in sorted_redirects:
            if redirect and redirect.target and redirect.target.stable_id:
                stripped_id = redirect.target.stable_id.strip()
                if stripped_id:
                    redirect_ids.append(stripped_id)
                    redirect_comment = redirect.redirect_comment or ""
                    redirect_comments.append(redirect_comment)
    redirect_ids = sorted(redirect_ids)
    redirect_ids_str = "|".join(redirect_ids)
    redirect_comments_str = "|".join(redirect_comments)

    # If for some reason there is no redirect_ids, discard the redirect_comments if any
    if redirect_ids_str == "":
        redirect_comments_str = ""
    else:
        # If there is no comment but we do have redirects, use an empty string instead of a
        # potentially a bunch of vertical bars.
        redirect_comments_str = (
            ""
            if (redirect_comments_str or "").strip("|") == ""
            else redirect_comments_str
        )

    # Some of the data is set to None or "" here but will be set to the proper value
    # later depending on the type (GTFS or GTFS_RT)
    country_code, subdivision_name, municipality = get_location_data(
        feed, geopolygon_map
    )
    data = {
        "id": feed.stable_id,
        "data_type": feed.data_type,
        "entity_type": None,
        "location.country_code": country_code,
        "location.subdivision_name": subdivision_name,
        "location.municipality": municipality,
        "provider": feed.provider,
        "is_official": feed.official,
        "name": feed.feed_name,
        "note": feed.note,
        "feed_contact_email": feed.feed_contact_email,
        "static_reference": None,
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
        # We use the report validated_at date as the extracted_on date
        "location.bounding_box.extracted_on": None,
        "status": feed.status,
        "features": None,
        "redirect.id": redirect_ids_str,
        "redirect.comment": redirect_comments_str,
    }
    return data


def get_gtfs_rt_feed_csv_data(
    feed: Gtfsrealtimefeed, geopolygon_map: Optional[Dict[str, Geopolygon]]
) -> Dict:
    """
    This function takes a GtfsRTFeed and returns a dictionary with the data to be written to the CSV file.
    """
    data = get_feed_csv_data(feed, geopolygon_map)

    entity_types = ""
    if feed.entitytypes:
        valid_entity_types = [
            entity_type.name.strip()
            for entity_type in feed.entitytypes
            if entity_type and entity_type.name
        ]
        valid_entity_types = sorted(valid_entity_types)
        entity_types = "|".join(valid_entity_types)
    data["entity_type"] = entity_types

    static_references = ""
    first_feed_reference = None
    if feed.gtfs_feeds:
        valid_feed_references = [
            feed_reference.stable_id.strip()
            for feed_reference in feed.gtfs_feeds
            if feed_reference and feed_reference.stable_id
        ]
        static_references = "|".join(valid_feed_references)
        # If there is more than one GTFS feeds associated with this RT feed (why?)
        # We will arbitrarily use the first one in the list for the bounding box.
        first_feed_reference = feed.gtfs_feeds[0] if feed.gtfs_feeds else None
    data["static_reference"] = static_references

    # For the RT feed, we use the bounding box of the associated GTFS feed, if any.
    # These bounding boxes were collected when processing the GTFS feeds.
    bounding_box = (
        bounding_box_lookup.get(first_feed_reference.id)
        if first_feed_reference
        else None
    )
    if bounding_box:
        bounding_box.fill_data(data)

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
