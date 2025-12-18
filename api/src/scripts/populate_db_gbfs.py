from datetime import datetime

import pandas as pd
import pycountry
import pytz

from scripts.gbfs_utils.comparison import generate_system_csv_from_db, compare_db_to_csv
from scripts.gbfs_utils.fetching import fetch_data, get_data_content
from scripts.gbfs_utils.license import get_license_url
from scripts.populate_db import DatabasePopulateHelper, set_up_configs
from shared.database.database import generate_unique_id, configure_polymorphic_mappers
from shared.database_gen.sqlacodegen_models import Gbfsfeed, Location, Externalid


class GBFSDatabasePopulateHelper(DatabasePopulateHelper):
    def __init__(self, filepaths, test_mode=False):
        super().__init__(filepaths, test_mode)

    def filter_data(self):
        """Filter out rows with Authentication Info and duplicate System IDs"""
        self.df = self.df[pd.isna(self.df["Authentication Info URL"])]
        self.df = self.df[~self.df.duplicated(subset="System ID", keep=False)]
        self.logger.info(f"Data = {self.df}")

    @staticmethod
    def get_stable_id(row):
        return f"gbfs-{row['System ID']}"

    @staticmethod
    def get_external_id(feed_id, system_id):
        return Externalid(feed_id=feed_id, associated_id=str(system_id), source="gbfs")

    def deprecate_feeds(self, deprecated_feeds):
        """Deprecate feeds that are no longer in systems.csv"""
        if deprecated_feeds is None or deprecated_feeds.empty:
            self.logger.info("No feeds to deprecate.")
            return

        self.logger.info(f"Deleting {len(deprecated_feeds)} feed(s).")
        with self.db.start_db_session() as session:
            for index, row in deprecated_feeds.iterrows():
                stable_id = self.get_stable_id(row)
                gbfs_feed = self.query_feed_by_stable_id(session, stable_id, "gbfs")
                if gbfs_feed:
                    # A note about the deletion done here:
                    # Some other tables have a foreign key pointing to the feed, and these cannot be null
                    # (e.g. gbfsversion). So the delete will fail, unless we cascade the deletion of the
                    # gbfs_feed to the deletion of the entry in gbfsversion, which is done in the DB
                    # schema. It's also the case for other tables and other foreign keys.
                    self.logger.info(f"Deleting feed with stable_id={stable_id}")
                    session.delete(gbfs_feed)
                    session.flush()

    def populate_db(self, session, fetch_url=True):
        """Populate the database with the GBFS feeds"""
        start_time = datetime.now()
        configure_polymorphic_mappers()

        try:
            # Compare the database to the CSV file
            df_from_db = generate_system_csv_from_db(self.df, session)
            added_or_updated_feeds, deprecated_feeds = compare_db_to_csv(df_from_db, self.df, self.logger)

            self.deprecate_feeds(deprecated_feeds)
            if added_or_updated_feeds is None:
                added_or_updated_feeds = self.df
            for index, row in added_or_updated_feeds.iterrows():
                self.logger.info(f"Processing row {index + 1} of {len(added_or_updated_feeds)}")
                stable_id = self.get_stable_id(row)
                gbfs_feed = self.query_feed_by_stable_id(session, stable_id, "gbfs")
                if fetch_url:
                    fetched_data = fetch_data(row["Auto-Discovery URL"], self.logger, ["system_information"])
                else:
                    fetched_data = dict()
                # If the feed already exists, update it. Otherwise, create a new feed.
                if gbfs_feed:
                    self.logger.info(f"Updating feed {stable_id} - {row['Name']}")
                else:
                    feed_id = generate_unique_id()
                    self.logger.info(f"Creating new feed for {stable_id} - {row['Name']}")
                    gbfs_feed = Gbfsfeed(
                        id=feed_id,
                        data_type="gbfs",
                        stable_id=stable_id,
                        created_at=datetime.now(pytz.utc),
                        operational_status="published",
                    )
                    gbfs_feed.externalids = [self.get_external_id(feed_id, row["System ID"])]
                    session.add(gbfs_feed)

                system_information_content = get_data_content(fetched_data.get("system_information"), self.logger)
                gbfs_feed.license_url = get_license_url(system_information_content, self.logger)
                gbfs_feed.feed_contact_email = (
                    system_information_content.get("feed_contact_email") if system_information_content else None
                )
                gbfs_feed.system_id = str(row["System ID"]).strip()
                gbfs_feed.operator = row["Name"]
                gbfs_feed.provider = row["Name"]
                gbfs_feed.operator_url = row["URL"]
                gbfs_feed.producer_url = row["Auto-Discovery URL"]
                gbfs_feed.auto_discovery_url = row["Auto-Discovery URL"]
                gbfs_feed.updated_at = datetime.now(pytz.utc)

                if not gbfs_feed.locations:  # If locations are empty, create a new location (no overwrite)
                    country_code = self.get_safe_value(row, "Country Code", "")
                    municipality = self.get_safe_value(row, "Location", "")
                    location_id = self.get_location_id(country_code, None, municipality)
                    country = pycountry.countries.get(alpha_2=country_code) if country_code else None
                    location = session.get(Location, location_id) or Location(
                        id=location_id,
                        country_code=country_code,
                        country=country.name if country else None,
                        municipality=municipality,
                    )
                    gbfs_feed.locations.clear()
                    gbfs_feed.locations = [location]

                session.flush()
                self.logger.info(80 * "-")

                # self.db.session.commit()
                end_time = datetime.now()
                self.logger.info(f"Time taken: {end_time - start_time} seconds")
        except Exception as e:
            self.logger.error(f"Error populating the database: {e}")
            raise e


if __name__ == "__main__":
    GBFSDatabasePopulateHelper(set_up_configs()).initialize(trigger_downstream_tasks=False)
