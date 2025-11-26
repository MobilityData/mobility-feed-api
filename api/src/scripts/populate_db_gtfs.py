import os
from datetime import datetime
from typing import TYPE_CHECKING

import pycountry
import pytz
from sqlalchemy import func

from scripts.load_dataset_on_create import publish_all
from scripts.populate_db import DatabasePopulateHelper, set_up_configs
from shared.database.database import generate_unique_id
from shared.database_gen.sqlacodegen_models import (
    Entitytype,
    Externalid,
    Gtfsrealtimefeed,
    Location,
    Redirectingid,
    Gtfsfeed,
)
from utils.data_utils import set_up_defaults

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class GTFSDatabasePopulateHelper(DatabasePopulateHelper):
    """
    GTFS - Helper class to populate the database
    """

    def __init__(self, filepaths):
        """
        Specify a list of files to load the csv data from.
        Can also be a single string with a file name.
        """
        super().__init__(filepaths)
        # Keep track of the feeds that have been added to the database
        self.added_gtfs_feeds = []

    def filter_data(self):
        self.df = self.df[(self.df.data_type == "gtfs") | (self.df.data_type == "gtfs-rt")]
        self.df = set_up_defaults(self.df)
        # Keep track of the feeds that have been added to the database
        self.added_gtfs_feeds = []

    def get_data_type(self, row):
        """
        Get the data type from the row
        """
        data_type = self.get_safe_value(row, "data_type", "").lower()
        if data_type not in ["gtfs", "gtfs-rt", "gtfs_rt"]:
            self.logger.warning(f"Unsupported data type: {data_type}")
            return None
        return data_type.replace("-", "_")

    def get_stable_id(self, row):
        """
        Get the stable id from the row
        """
        return f'mdb-{self.get_safe_value(row, "mdb_source_id", "")}'

    def get_country(self, country_code):
        country = None
        if country_code:
            country = pycountry.countries.get(alpha_2=country_code)
            country = country.name if country else None
        return country

    def populate_location(self, session, feed, row, stable_id):
        """
        Populate the location for the feed
        """
        if feed.locations:
            self.logger.warning(f"Location already exists for feed {stable_id}")
            return

        country_code = self.get_safe_value(row, "location.country_code", "")
        subdivision_name = self.get_safe_value(row, "location.subdivision_name", "")
        municipality = self.get_safe_value(row, "location.municipality", "")
        country = self.get_country(country_code)
        location_id = self.get_location_id(country_code, subdivision_name, municipality)
        if not location_id:
            self.logger.warning(f"Location ID is empty for feed {stable_id}")
            feed.locations.clear()
        else:
            location = session.get(Location, location_id)
            location = (
                location
                if location
                else Location(
                    id=location_id,
                    # Country code should be short.
                    # If too long it might be an error
                    # (like it could be the country name instead of code).
                    country_code=country_code if country_code and len(country_code) <= 3 else None,
                    subdivision_name=subdivision_name,
                    municipality=municipality,
                    country=country,
                )
            )
            feed.locations = [location]

    def process_entity_types(self, session: "Session", feed: Gtfsrealtimefeed, row, stable_id):
        """
        Process the entity types for the feed
        """
        entity_types = self.get_safe_value(row, "entity_type", "").replace("|", "-").split("-")
        if len(entity_types) > 0:
            for entity_type_name in entity_types:
                entity_type = session.query(Entitytype).filter(Entitytype.name == entity_type_name).first()

                if not entity_type:
                    entity_type = Entitytype(name=entity_type_name)
                if all(entity_type.name != entity.name for entity in feed.entitytypes):
                    feed.entitytypes.append(entity_type)
                    session.flush()
        else:
            self.logger.warning(f"Entity types array is empty for feed {stable_id}")
            feed.entitytypes.clear()

    # def process_feed_references(self, session: "Session"):
    #     """
    #     Process the feed references
    #     """
    #     self.logger.info("Processing feed references")
    #     for index, row in self.df.iterrows():
    #         stable_id = self.get_stable_id(row)
    #         data_type = self.get_data_type(row)
    #         if data_type != "gtfs_rt":
    #             continue
    #         gtfs_rt_feed = self.query_feed_by_stable_id(session, stable_id, "gtfs_rt")
    #         static_reference = self.get_safe_value(row, "static_reference", "")
    #         if static_reference:
    #             try:
    #                 gtfs_stable_id = f"mdb-{int(float(static_reference))}"
    #             except ValueError:
    #                 gtfs_stable_id = static_reference
    #             gtfs_feed = self.query_feed_by_stable_id(session, gtfs_stable_id, "gtfs")
    #             if not gtfs_feed:
    #                 self.logger.warning(f"Could not find static reference feed {gtfs_stable_id} for feed {stable_id}")
    #                 continue
    #             already_referenced_ids = {ref.id for ref in gtfs_feed.gtfs_rt_feeds}
    #             if gtfs_feed and gtfs_rt_feed.id not in already_referenced_ids:
    #                 gtfs_feed.gtfs_rt_feeds.append(gtfs_rt_feed)
    #                 # Flush to avoid FK violation
    #                 session.flush()

    def process_feed_references(self, session: "Session"):
        """
        Process the feed references for GTFS-RT feeds.

        1. Uses 'static_reference' column if present.
        2. Falls back to matching static feeds by provider name.
        """
        self.logger.info("Processing feed references")

        for index, row in self.df.iterrows():
            stable_id = self.get_stable_id(row)
            data_type = self.get_data_type(row)

            # Only process GTFS-RT feeds
            if data_type != "gtfs_rt":
                continue

            gtfs_rt_feed = self.query_feed_by_stable_id(session, stable_id, "gtfs_rt")
            if not gtfs_rt_feed:
                self.logger.warning(f"Could not find GTFS-RT feed {stable_id}")
                continue

            # Try static_reference column first
            static_reference = self.get_safe_value(row, "static_reference", "").strip()
            gtfs_feed = None

            if static_reference:
                # Normalize stable_id
                try:
                    gtfs_stable_id = f"mdb-{int(float(static_reference))}"
                except ValueError:
                    gtfs_stable_id = static_reference

                gtfs_feed = self.query_feed_by_stable_id(session, gtfs_stable_id, "gtfs")
                if not gtfs_feed:
                    self.logger.warning(f"Could not find static reference feed {gtfs_stable_id} for feed {stable_id}")

            # Fallback: match by provider if no static_reference or not found
            if not gtfs_feed:
                provider_value = (self.get_safe_value(row, "provider", "") or "").strip().lower()
                if provider_value:
                    gtfs_feed = (
                        session.query(Gtfsfeed)
                        .filter(
                            Gtfsfeed.data_type == "gtfs",
                            func.lower(func.trim(Gtfsfeed.provider)) == provider_value,
                            Gtfsfeed.stable_id != stable_id,
                        )
                        .first()
                    )
                    if not gtfs_feed:
                        self.logger.warning(
                            f"No static GTFS feed found for provider '{provider_value}' for feed {stable_id}"
                        )

            # Link the feeds if we have a valid static GTFS feed
            if gtfs_feed:
                already_referenced_ids = {ref.id for ref in gtfs_feed.gtfs_rt_feeds}
                if gtfs_rt_feed.id not in already_referenced_ids:
                    gtfs_feed.gtfs_rt_feeds.append(gtfs_rt_feed)
                    session.flush()  # Avoid FK violations
                    self.logger.info(f"Linked GTFS-RT feed {stable_id} to static feed {gtfs_feed.stable_id}")

    def process_redirects(self, session: "Session"):
        """
        Process the redirects
        """
        self.logger.info("Processing redirects")
        for index, row in self.df.iterrows():
            stable_id = self.get_stable_id(row)
            raw_redirects = row.get("redirect.id", None)
            redirects_ids = str(raw_redirects).split("|") if raw_redirects is not None else []
            if len(redirects_ids) == 0:
                continue
            feed = self.query_feed_by_stable_id(session, stable_id, None)
            raw_comments = row.get("redirect.comment", None)
            comments = raw_comments.split("|") if raw_comments is not None else []
            if len(redirects_ids) != len(comments) and len(comments) > 0:
                self.logger.warning(f"Number of redirect ids and redirect comments differ for feed {stable_id}")
            for redirect_id in redirects_ids:
                redirect_id = redirect_id.strip() if redirect_id else ""
                if len(redirect_id) == 0:
                    # since there is a 1:1 correspondence between redirect ids and comments, skip also the comment
                    comments = comments[1:]
                    continue
                if comments:
                    comment = comments.pop(0)
                else:
                    comment = ""
                try:
                    target_stable_id = f"mdb-{int(float(redirect_id))}"
                except ValueError:
                    target_stable_id = redirect_id
                target_feed = self.query_feed_by_stable_id(session, target_stable_id, None)
                if not target_feed:
                    self.logger.warning(f"Could not find redirect target feed {target_stable_id} for feed {stable_id}")
                    continue

                if feed.id == target_feed.id:
                    self.logger.error(f"Feed has redirect pointing to itself {stable_id}")
                else:
                    if all(redirect.target_id != target_feed.id for redirect in feed.redirectingids):
                        feed.redirectingids.append(
                            Redirectingid(source_id=feed.id, target_id=target_feed.id, redirect_comment=comment)
                        )
                        # Flush to avoid FK violation
                        session.flush()

    def populate_db(self, session: "Session", fetch_url: bool = True):
        """
        Populate the database with the sources.csv data
        """
        self.logger.info("Populating the database with sources.csv data")
        for index, row in self.df.iterrows():
            self.logger.debug(f"Populating Database with Feed [stable_id = {row['mdb_source_id']}]")
            # Create or update the GTFS feed
            data_type = self.get_data_type(row)
            stable_id = self.get_stable_id(row)
            is_official_from_csv = self.get_safe_boolean_value(row, "is_official", None)
            feed = self.query_feed_by_stable_id(session, stable_id, data_type)
            if feed:
                self.logger.debug(f"Updating {feed.__class__.__name__}: {stable_id}")
                # Always set the deprecated status if found in the csv
                csv_status = self.get_safe_value(row, "status", "active")
                if csv_status.lower() == "deprecated":
                    feed.status = "deprecated"
            else:
                feed = self.get_model(data_type)(
                    id=generate_unique_id(),
                    data_type=data_type,
                    stable_id=stable_id,
                    # Current timestamp with UTC timezone
                    created_at=datetime.now(pytz.utc),
                    operational_status="published",
                )
                feed.status = self.get_safe_value(row, "status", "active")
                self.logger.info(f"Creating {feed.__class__.__name__}: {stable_id}")
                session.add(feed)
                if data_type == "gtfs":
                    self.added_gtfs_feeds.append(feed)
                feed.externalids = [
                    Externalid(
                        feed_id=feed.id,
                        associated_id=str(int(float(row["mdb_source_id"]))),
                        source="mdb",
                    )
                ]
            # If the is_official field from the CSV is empty, the value here will be None and we don't touch the DB
            if is_official_from_csv is not None:
                if feed.official != is_official_from_csv:
                    feed.official = is_official_from_csv
                    feed.official_updated_at = datetime.now(pytz.utc)

            # Populate common fields from Feed
            feed.feed_name = self.get_safe_value(row, "name", "")
            feed.note = self.get_safe_value(row, "note", "")
            producer_url = self.get_safe_value(row, "urls.direct_download", "")
            if "transitfeeds" not in producer_url:  # Avoid setting transitfeeds as producer_url
                feed.producer_url = producer_url
            feed.authentication_type = str(int(float(self.get_safe_value(row, "urls.authentication_type", "0"))))
            feed.authentication_info_url = self.get_safe_value(row, "urls.authentication_info", "")
            feed.api_key_parameter_name = self.get_safe_value(row, "urls.api_key_parameter_name", "")
            feed.license_url = self.get_safe_value(row, "urls.license", "")
            feed.feed_contact_email = self.get_safe_value(row, "feed_contact_email", "")
            feed.provider = self.get_safe_value(row, "provider", "")

            self.populate_location(session, feed, row, stable_id)
            if data_type == "gtfs_rt":
                self.process_entity_types(session, feed, row, stable_id)

            session.add(feed)
            session.flush()
        # This need to be done after all feeds are added to the session to avoid FK violation
        self.process_feed_references(session)
        self.process_redirects(session)
        self.post_process_locations(session)

    def trigger_downstream_tasks(self):
        """
        Trigger downstream tasks after populating the database
        """
        self.logger.info("Triggering downstream tasks")
        self.logger.info(
            f"New feeds added to the database: "
            f"{','.join([feed.stable_id for feed in self.added_gtfs_feeds] if self.added_gtfs_feeds else [])}"
        )

        env = os.getenv("ENV")
        self.logger.info(f"ENV = {env}")
        if os.getenv("ENV", "local") != "local":
            # Publishes the new feeds to the Pub/Sub topic to download the datasets
            publish_all(self.added_gtfs_feeds)

    def post_process_locations(self, session: "Session"):
        """
        Set the country for any location entry that does not have one.
        """
        query = session.query(Location).filter(Location.country.is_(None))
        result = query.all()
        set_country_count = 0
        for location in result:
            country = self.get_country(location.country_code)
            if country:
                location.country = country  # Set the country field to the desired value
                set_country_count += 1
        session.commit()
        self.logger.info(f"Had to set the country for {set_country_count} locations")


if __name__ == "__main__":
    db_helper = GTFSDatabasePopulateHelper(set_up_configs())
    db_helper.initialize()
