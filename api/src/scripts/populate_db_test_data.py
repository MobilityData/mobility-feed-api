import argparse
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from geoalchemy2 import WKTElement
from sqlalchemy import text

from database.database import Database
from database_gen.sqlacodegen_models import Gtfsdataset, Validationreport, Gtfsfeed, Notice, Feature, t_feedsearch

from utils.logger import Logger


def set_up_configs():
    """
    Set up function
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--filepath", help="Absolute path for the JSON file containing the test data", required=True)
    args = parser.parse_args()
    current_path = Path(__file__).resolve()
    dotenv_path = os.path.join(current_path.parents[3], "config", ".env")
    load_dotenv(dotenv_path=dotenv_path)
    return args.filepath


class DatabasePopulateTestDataHelper:
    """
    Helper class to populate
    the database with test data
    """

    def __init__(self, filepaths):
        self.logger = Logger(self.__class__.__module__).get_logger()
        self.db = Database()

        self.filepaths = filepaths

    def populate_test_datasets(self, filepath):
        """
        Populate the database with the test datasets
        """
        # Load the JSON file
        with open(filepath) as f:
            data = json.load(f)

        # GTFS Datasets
        dataset_dict = {}
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
        for featureName in data["features"]:
            feature = Feature(name=featureName)
            self.db.session.add(feature)

        # Features in Validation Reports
        for report_features in data["validation_report_features"]:
            validation_report_dict[report_features["validation_report_id"]].features.append(
                self.db.session.query(Feature).filter(Feature.name == report_features["feature_name"]).first()
            )

        self.db.session.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {t_feedsearch.name}"))

        self.db.session.commit()

    def populate(self):
        """
        Populate the database with the test data
        """
        self.logger.info("Populating the database with test data")

        if not self.filepaths:
            self.logger.error("No file paths provided")
            return
        if not isinstance(self.filepaths, list):
            self.filepaths = [self.filepaths]

        for filepath in self.filepaths:
            self.populate_test_datasets(filepath)

        self.logger.info("Database populated with test data")


if __name__ == "__main__":
    db_helper = DatabasePopulateTestDataHelper(set_up_configs())
    db_helper.populate()
