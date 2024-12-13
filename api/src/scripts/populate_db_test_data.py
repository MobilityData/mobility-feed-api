import json
from uuid import uuid4

from geoalchemy2 import WKTElement
from google.cloud.sql.connector.instance import logger
from sqlalchemy import text

from database.database import Database
from database_gen.sqlacodegen_models import (
    Gtfsdataset,
    Validationreport,
    Gtfsfeed,
    Notice,
    Feature,
    t_feedsearch,
    Location,
    Officialstatushistory,
)
from scripts.populate_db import set_up_configs, DatabasePopulateHelper
from utils.logger import Logger


class DatabasePopulateTestDataHelper:
    """
    Helper class to populate
    the database with test data
    """

    def __init__(self, filepaths):
        """
        Specify a list of files to load the json data from.
        Can also be a single string with a file name.
        """
        self.logger = Logger(self.__class__.__module__).get_logger()
        self.db = Database()

        if not isinstance(filepaths, list):
            self.filepaths = [filepaths]
        else:
            self.filepaths = filepaths

    def populate_test_datasets(self, filepath):
        """
        Populate the database with the test datasets
        """
        # Load the JSON file
        with open(filepath) as f:
            data = json.load(f)

        # GTFS Feeds
        if "feeds" in data:
            self.populate_test_feeds(data["feeds"])

        # GTFS Datasets
        dataset_dict = {}
        if "datasets" in data:
            for dataset in data["datasets"]:
                # query the db using feed_id to get the feed object
                gtfsfeed = self.db.session.query(Gtfsfeed).filter(Gtfsfeed.stable_id == dataset["feed_stable_id"]).all()
                if not gtfsfeed:
                    self.logger.error(f"No feed found with stable_id: {dataset['feed_stable_id']}")
                    continue

                gtfs_dataset = Gtfsdataset(
                    id=dataset["id"],
                    feed_id=gtfsfeed[0].id,
                    stable_id=dataset["id"],
                    latest=dataset["latest"],
                    hosted_url=dataset["hosted_url"],
                    hash=dataset["hash"],
                    downloaded_at=dataset["downloaded_at"],
                    bounding_box=None
                    if dataset.get("bounding_box") is None
                    else WKTElement(dataset["bounding_box"], srid=4326),
                    validation_reports=[],
                )
                dataset_dict[dataset["id"]] = gtfs_dataset
                self.db.session.add(gtfs_dataset)

        # Validation reports
        if "validation_reports" in data:
            validation_report_dict = {}
            for report in data["validation_reports"]:
                validation_report = Validationreport(
                    id=report["id"],
                    validator_version=report["validator_version"],
                    validated_at=report["validated_at"],
                    html_report=report["html_report"],
                    json_report=report["json_report"],
                    features=[],
                )
                dataset_dict[report["dataset_id"]].validation_reports.append(validation_report)
                validation_report_dict[report["id"]] = validation_report
                self.db.session.add(validation_report)

        # Notices
        if "notices" in data:
            for report_notice in data["notices"]:
                notice = Notice(
                    dataset_id=report_notice["dataset_id"],
                    validation_report_id=report_notice["validation_report_id"],
                    severity=report_notice["severity"],
                    notice_code=report_notice["notice_code"],
                    total_notices=report_notice["total_notices"],
                )
                self.db.session.add(notice)
        # Features
        if "features" in data:
            for featureName in data["features"]:
                feature = Feature(name=featureName)
                self.db.session.add(feature)

        # Features in Validation Reports
        if "validation_report_features" in data:
            for report_features in data["validation_report_features"]:
                validation_report_dict[report_features["validation_report_id"]].features.append(
                    self.db.session.query(Feature).filter(Feature.name == report_features["feature_name"]).first()
                )

        self.db.session.commit()
        self.db.session.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {t_feedsearch.name}"))

    def populate(self):
        """
        Populate the database with the test data
        """
        self.logger.info("Populating the database with test data")

        if not self.filepaths:
            self.logger.error("No file paths provided")
            return

        for filepath in self.filepaths:
            self.populate_test_datasets(filepath)

        self.logger.info("Database populated with test data")

    def populate_test_feeds(self, feeds_data):
        for feed_data in feeds_data:
            feed = Gtfsfeed(
                id=str(uuid4()),
                stable_id=feed_data["id"],
                data_type=feed_data["data_type"],
                status=feed_data["status"],
                created_at=feed_data["created_at"],
                provider=feed_data["provider"],
                feed_name=feed_data["feed_name"],
                note=feed_data["note"],
                authentication_info_url=None,
                api_key_parameter_name=None,
                license_url=None,
                feed_contact_email=feed_data["feed_contact_email"],
                producer_url=feed_data["source_info"]["producer_url"],
            )
            locations = []
            for location_data in feed_data["locations"]:
                location_id = DatabasePopulateHelper.get_location_id(
                    location_data["country_code"],
                    location_data["subdivision_name"],
                    location_data["municipality"],
                )
                location = self.db.session.get(Location, location_id)
                location = (
                    location
                    if location
                    else Location(
                        id=location_id,
                        country_code=location_data["country_code"],
                        subdivision_name=location_data["subdivision_name"],
                        municipality=location_data["municipality"],
                        country=location_data["country"],
                    )
                )
                locations.append(location)
            feed.locations = locations
            if "official" in feed_data:
                official_status_history = Officialstatushistory(
                    feed_id=feed.id,
                    is_official=feed_data["official"],
                    reviewer_email="dev@test.com",
                    timestamp=feed_data["created_at"],
                )
                feed.officialstatushistories.append(official_status_history)
            self.db.session.add(feed)
            logger.info(f"Added feed {feed.stable_id}")


if __name__ == "__main__":
    db_helper = DatabasePopulateTestDataHelper(set_up_configs())
    db_helper.populate()
