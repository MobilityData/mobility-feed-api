import argparse
import os
from pathlib import Path
from typing import Type

import pandas
from dotenv import load_dotenv
from sqlalchemy import text

from database.database import Database, generate_unique_id, configure_polymorphic_mappers
from database_gen.sqlacodegen_models import (
    Entitytype,
    Externalid,
    Gtfsfeed,
    Gtfsrealtimefeed,
    Location,
    Redirectingid,
    t_feedsearch,
    Feed,
)
from scripts.load_dataset_on_create import publish_all
from utils.data_utils import set_up_defaults
from utils.logger import Logger

import logging

logging.basicConfig()
logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)


def set_up_configs():
    """
    Set up function
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", help="Environment to use", default="local")
    parser.add_argument("--filepath", help="Absolute path for the data file", required=True)
    args = parser.parse_args()
    current_path = Path(__file__).resolve()
    dotenv_path = os.path.join(current_path.parents[3], "config", f".env.{args.env}")
    load_dotenv(dotenv_path=dotenv_path)
    return args.filepath


class DatabasePopulateHelper:
    """
    Helper class to populate the database
    """

    def __init__(self, filepath):
        self.logger = Logger(self.__class__.__name__).get_logger()
        self.logger.setLevel(logging.INFO)
        self.db = Database(echo_sql=False)
        self.df = pandas.read_csv(filepath)  # contains the data to populate the database

        # Filter unsupported data types
        self.df = self.df[(self.df.data_type == "gtfs") | (self.df.data_type == "gtfs-rt")]
        self.df = set_up_defaults(self.df)
        self.added_gtfs_feeds = []  # Keep track of the feeds that have been added to the database

    @staticmethod
    def get_model(data_type: str | None) -> Type[Gtfsrealtimefeed | Gtfsfeed | Feed]:
        """
        Get the model based on the data type
        """
        if data_type is None:
            return Feed
        return Gtfsrealtimefeed if data_type == "gtfs_rt" else Gtfsfeed

    @staticmethod
    def get_safe_value(row, column_name, default_value):
        """
        Get a safe value from the row
        """
        if not row[column_name] or pandas.isna(row[column_name]) or f"{row[column_name]}".strip() == "":
            return default_value if default_value is not None else None
        return f"{row[column_name]}".strip()

    def get_data_type(self, row):
        """
        Get the data type from the row
        """
        data_type = self.get_safe_value(row, "data_type", "").lower()
        if data_type not in ["gtfs", "gtfs-rt", "gtfs_rt"]:
            self.logger.warning(f"Unsupported data type: {data_type}")
            return None
        return data_type.replace("-", "_")

    def query_feed_by_stable_id(self, stable_id: str, data_type: str | None) -> Gtfsrealtimefeed | Gtfsfeed | None:
        """
        Query the feed by stable id
        """
        model = self.get_model(data_type)
        return self.db.session.query(model).filter(model.stable_id == stable_id).first()

    def get_stable_id(self, row):
        """
        Get the stable id from the row
        """
        return f'mdb-{self.get_safe_value(row, "mdb_source_id", "")}'

    def populate_location(self, feed, row, stable_id):
        """
        Populate the location for the feed
        """
        country_code = self.get_safe_value(row, "location.country_code", "")
        subdivision_name = self.get_safe_value(row, "location.subdivision_name", "")
        municipality = self.get_safe_value(row, "location.municipality", "")
        composite_id = f"{country_code}-{subdivision_name}-{municipality}".replace(" ", "_")
        location_id = composite_id if len(composite_id) > 2 else None
        if not location_id:
            self.logger.warning(f"Location ID is empty for feed {stable_id}")
            feed.locations.clear()
        else:
            location = self.db.session.get(Location, location_id)
            location = (
                location
                if location
                else Location(
                    id=location_id,
                    country_code=country_code,
                    subdivision_name=subdivision_name,
                    municipality=municipality,
                )
            )
            feed.locations = [location]

    def process_entity_types(self, feed: Gtfsrealtimefeed, row, stable_id):
        """
        Process the entity types for the feed
        """
        entity_types = self.get_safe_value(row, "entity_type", "").replace("|", "-").split("-")
        if len(entity_types) > 0:
            for entity_type_name in entity_types:
                entity_type = self.db.session.query(Entitytype).filter(Entitytype.name == entity_type_name).first()
                if not entity_type:
                    entity_type = Entitytype(name=entity_type_name)
                if all(entity_type.name != entity.name for entity in feed.entitytypes):
                    feed.entitytypes.append(entity_type)
                    self.db.session.flush()
        else:
            self.logger.warning(f"Entity types array is empty for feed {stable_id}")
            feed.entitytypes.clear()

    def process_feed_references(self):
        """
        Process the feed references
        """
        self.logger.info("Processing feed references")
        for index, row in self.df.iterrows():
            stable_id = self.get_stable_id(row)
            data_type = self.get_data_type(row)
            if data_type != "gtfs_rt":
                continue
            gtfs_rt_feed = self.query_feed_by_stable_id(stable_id, "gtfs_rt")
            static_reference = self.get_safe_value(row, "static_reference", "")
            if static_reference:
                gtfs_stable_id = f"mdb-{int(float(static_reference))}"
                gtfs_feed = self.query_feed_by_stable_id(gtfs_stable_id, "gtfs")
                already_referenced_ids = {ref.id for ref in gtfs_feed.gtfs_rt_feeds}
                if gtfs_feed and gtfs_rt_feed.id not in already_referenced_ids:
                    gtfs_feed.gtfs_rt_feeds.append(gtfs_rt_feed)
                    # Flush to avoid FK violation
                    self.db.session.flush()

    def process_redirects(self):
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
            feed = self.query_feed_by_stable_id(stable_id, None)
            raw_comments = row.get("redirect.comment", None)
            comments = raw_comments.split("|") if raw_comments is not None else []
            if len(redirects_ids) != len(comments) and len(comments) > 0:
                self.logger.warning(f"Number of redirect ids and redirect comments differ for feed {stable_id}")
            for mdb_source_id in redirects_ids:
                if len(mdb_source_id) == 0:
                    # since there is a 1:1 correspondence between redirect ids and comments, skip also the comment
                    comments = comments[1:]
                    continue
                if comments:
                    comment = comments.pop(0)
                else:
                    comment = ""

                target_stable_id = f"mdb-{int(float(mdb_source_id.strip()))}"
                target_feed = self.query_feed_by_stable_id(target_stable_id, None)
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
                        self.db.session.flush()

    def populate_db(self):
        """
        Populate the database with the sources.csv data
        """
        self.logger.info("Populating the database with sources.csv data")
        for index, row in self.df.iterrows():
            self.logger.debug(f"Populating Database with Feed [stable_id = {row['mdb_source_id']}]")
            # Create or update the GTFS feed
            data_type = self.get_data_type(row)
            stable_id = self.get_stable_id(row)
            feed = self.query_feed_by_stable_id(stable_id, data_type)
            if feed:
                self.logger.debug(f"Updating {feed.__class__.__name__}: {stable_id}")
            else:
                feed = self.get_model(data_type)(id=generate_unique_id(), data_type=data_type, stable_id=stable_id)
                self.logger.info(f"Creating {feed.__class__.__name__}: {stable_id}")
                self.db.session.add(feed)
                if data_type == "gtfs":
                    self.added_gtfs_feeds.append(feed)
                feed.externalids = [
                    Externalid(
                        feed_id=feed.id,
                        associated_id=str(int(float(row["mdb_source_id"]))),
                        source="mdb",
                    )
                ]
            # Populate common fields from Feed
            feed.feed_name = self.get_safe_value(row, "name", "")
            feed.note = self.get_safe_value(row, "note", "")
            feed.producer_url = self.get_safe_value(row, "urls.direct_download", "")
            feed.authentication_type = str(int(float(self.get_safe_value(row, "urls.authentication_type", "0"))))
            feed.authentication_info_url = self.get_safe_value(row, "urls.authentication_info", "")
            feed.api_key_parameter_name = self.get_safe_value(row, "urls.api_key_parameter_name", "")
            feed.license_url = self.get_safe_value(row, "urls.license", "")
            feed.status = self.get_safe_value(row, "status", "active")
            feed.feed_contact_email = self.get_safe_value(row, "feed_contact_email", "")
            feed.provider = self.get_safe_value(row, "provider", "")

            self.populate_location(feed, row, stable_id)
            if data_type == "gtfs_rt":
                self.process_entity_types(feed, row, stable_id)

            self.db.session.add(feed)
            self.db.session.flush()
        # This need to be done after all feeds are added to the session to avoid FK violation
        self.process_feed_references()
        self.process_redirects()

    def trigger_downstream_tasks(self):
        """
        Trigger downstream tasks after populating the database
        """
        self.logger.info("Triggering downstream tasks")
        self.logger.debug(
            f"New feeds added to the database: "
            f"{','.join([feed.stable_id for feed in self.added_gtfs_feeds] if self.added_gtfs_feeds else [])}"
        )
        if os.getenv("ENV", "local") != "local":
            publish_all(self.added_gtfs_feeds)  # Publishes the new feeds to the Pub/Sub topic to download the datasets


if __name__ == "__main__":
    db_helper = DatabasePopulateHelper(set_up_configs())
    try:
        configure_polymorphic_mappers()
        db_helper.populate_db()
        db_helper.db.session.commit()

        db_helper.logger.info("Refreshing MATERIALIZED FEED SEARCH VIEW - Started")
        db_helper.db.session.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {t_feedsearch.name}"))
        db_helper.logger.info("Refreshing MATERIALIZED FEED SEARCH VIEW - Completed")
        db_helper.db.session.commit()
        db_helper.logger.info("\n----- Database populated with sources.csv data. -----")
        db_helper.trigger_downstream_tasks()
    except Exception as e:
        db_helper.logger.error(f"\n------ Failed to populate the database with sources.csv: {e} -----\n")
        db_helper.db.session.rollback()
        exit(1)
