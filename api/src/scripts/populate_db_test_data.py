import json
from uuid import uuid4

from geoalchemy2 import WKTElement
from google.cloud.sql.connector.instance import logger
from sqlalchemy import text

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Gtfsdataset,
    Validationreport,
    Gtfsfeed,
    Notice,
    Feature,
    License,
    t_feedsearch,
    Location,
    Officialstatushistory,
    Gbfsversion,
    Gbfsendpoint,
    Gbfsfeed,
    Rule,
    Feed,
)
from scripts.populate_db import set_up_configs, DatabasePopulateHelper
from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


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
        self.logger = get_logger(self.__class__.__module__)

        if not isinstance(filepaths, list):
            self.filepaths = [filepaths]
        else:
            self.filepaths = filepaths

    @with_db_session
    def populate_test_datasets(self, filepath, db_session: "Session"):
        """
        Populate the database with the test datasets
        """
        # Load the JSON file
        with open(filepath) as f:
            data = json.load(f)

        # Licenses (populate license table first so feeds can reference them)
        if "licenses" in data:
            for lic in data["licenses"]:
                # skip if id missing
                lic_id = lic.get("id")
                if not lic_id:
                    continue
                existing = db_session.get(License, lic_id)
                if existing:
                    # optionally update existing fields if needed
                    continue
                license_obj = License(
                    id=lic_id,
                    type=lic.get("type", "standard"),
                    is_spdx=lic.get("is_spdx", False),
                    name=lic.get("name"),
                    url=lic.get("url"),
                    description=lic.get("description"),
                    content_txt=lic.get("content_txt"),
                    content_html=lic.get("content_html"),
                    created_at=lic.get("created_at"),
                    updated_at=lic.get("updated_at"),
                )
                db_session.add(license_obj)
            db_session.commit()

        # Link licenses to feeds if specified
        if "feed_licenses" in data:
            for lf in data["feed_licenses"]:
                license_id = lf.get("license_id")
                feed_stable_id = lf.get("feed_stable_id")
                if not license_id or not feed_stable_id:
                    continue
                license_obj = db_session.get(License, license_id)
                if not license_obj:
                    self.logger.error(
                        f"No license found with id: {license_id}; skipping license_feed for feed " f"{feed_stable_id}"
                    )
                    continue
                feed_obj = db_session.query(Feed).filter(Feed.stable_id == feed_stable_id).one_or_none()
                if not feed_obj:
                    self.logger.error(
                        f"No feed found with stable_id: {feed_stable_id}; skipping license_feed for"
                        f" license {license_id}"
                    )
                    continue
                feed_obj.license = license_obj
            db_session.commit()

        # Rules (optional section to seed rule metadata used by license_rules)
        if "rules" in data:
            for rule in data["rules"]:
                rule_name = rule.get("name")
                if not rule_name:
                    continue
                existing_rule = db_session.get(Rule, rule_name)
                if existing_rule:
                    continue
                db_session.add(
                    Rule(
                        name=rule_name,
                        label=rule.get("label") or rule_name,
                        type=rule.get("type") or "permission",
                        description=rule.get("description"),
                    )
                )
            db_session.commit()

        # GTFS Feeds
        if "feeds" in data:
            self.populate_test_feeds(data["feeds"], db_session)

        # GTFS Datasets
        dataset_dict = {}
        if "datasets" in data:
            for dataset in data["datasets"]:
                # query the db using feed_id to get the feed object
                gtfsfeed = db_session.query(Gtfsfeed).filter(Gtfsfeed.stable_id == dataset["feed_stable_id"]).all()
                if not gtfsfeed:
                    self.logger.error(f"No feed found with stable_id: {dataset['feed_stable_id']}")
                    continue

                gtfs_dataset = Gtfsdataset(
                    id=dataset["id"],
                    feed_id=gtfsfeed[0].id,
                    stable_id=dataset["id"],
                    hosted_url=dataset["hosted_url"],
                    hash=dataset["hash"],
                    downloaded_at=dataset["downloaded_at"],
                    bounding_box=(
                        None if dataset.get("bounding_box") is None else WKTElement(dataset["bounding_box"], srid=4326)
                    ),
                    validation_reports=[],
                )
                if dataset["latest"]:
                    gtfsfeed[0].latest_dataset = gtfs_dataset

                dataset_dict[dataset["id"]] = gtfs_dataset
                db_session.add(gtfs_dataset)
        db_session.commit()

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
                db_session.add(validation_report)

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
                db_session.add(notice)
        # Features
        if "features" in data:
            for featureName in data["features"]:
                feature = Feature(name=featureName)
                db_session.add(feature)

        db_session.commit()

        # Features in Validation Reports
        if "validation_report_features" in data:
            for report_features in data["validation_report_features"]:
                validation_report_dict[report_features["validation_report_id"]].features.append(
                    db_session.query(Feature).filter(Feature.name == report_features["feature_name"]).first()
                )

        # License rules: populate association table by creating missing Rule rows and attaching them to License
        if "license_rules" in data:
            for lr in data["license_rules"]:
                license_id = lr.get("license_id")
                rule_id = lr.get("rule_id")
                if not license_id or not rule_id:
                    continue
                license_obj = db_session.get(License, license_id)
                if not license_obj:
                    self.logger.error(f"No license found with id: {license_id}; skipping license_rule {rule_id}")
                    continue
                rule_obj = db_session.get(Rule, rule_id)
                if not rule_obj:
                    # Create a minimal Rule entry; label and type set conservatively
                    rule_obj = Rule(name=rule_id, label=rule_id, type="permission", description=None)
                    db_session.add(rule_obj)
                    # flush so the relationship can reference it immediately
                    db_session.flush()
                # Attach if not already associated
                if rule_obj not in license_obj.rules:
                    license_obj.rules.append(rule_obj)
            db_session.commit()

        # GBFS version
        if "gbfs_versions" in data:
            for version in data["gbfs_versions"]:
                gbfs_feed = db_session.query(Gbfsfeed).filter(Gbfsfeed.stable_id == version["feed_id"]).one_or_none()
                if not gbfs_feed:
                    self.logger.error(f"No feed found with stable_id: {version['feed_id']}")
                    continue
                gbfs_version = Gbfsversion(id=version["id"], version=version["version"], url=version["url"])
                if version.get("endpoints"):
                    for endpoint in version["endpoints"]:
                        gbfs_endpoint = Gbfsendpoint(
                            id=endpoint["id"],
                            url=endpoint["url"],
                            language=endpoint.get("language"),
                            name=endpoint["name"],
                        )
                        gbfs_version.gbfsendpoints.append(gbfs_endpoint)
                gbfs_feed.gbfsversions.append(gbfs_version)

        db_session.commit()
        db_session.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {t_feedsearch.name}"))

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

    def populate_test_feeds(self, feeds_data, db_session: "Session"):
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
                license_url=feed_data["source_info"]["license_url"],
                feed_contact_email=feed_data["feed_contact_email"],
                producer_url=feed_data["source_info"]["producer_url"],
                # license_id may be missing or an empty string; coerce empty -> None to avoid FK violation
                license_id=(feed_data["source_info"].get("license_id") or None),
                # allow empty notes to stay as empty string; coerce if you prefer None
                license_notes=(feed_data["source_info"].get("license_notes") or None),
                operational_status="published",
            )
            locations = []
            for location_data in feed_data["locations"]:
                location_id = DatabasePopulateHelper.get_location_id(
                    location_data["country_code"],
                    location_data["subdivision_name"],
                    location_data["municipality"],
                )
                location = db_session.get(Location, location_id)
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
            db_session.add(feed)
            db_session.commit()
            logger.info(f"Added feed {feed.stable_id}")


if __name__ == "__main__":
    db_helper = DatabasePopulateTestDataHelper(set_up_configs())
    db_helper.populate()
