from datetime import datetime
from sqlalchemy.orm import joinedload
import pytz
import requests
from database.database import generate_unique_id, configure_polymorphic_mappers
from scripts.database_populate_helper import DatabasePopulateHelper, set_up_configs
import pandas as pd
from database_gen.sqlacodegen_models import GbfsFeed, Location, GbfsVersion, Externalid

OFFICIAL_VERSIONS = [
    "1.0",
    "1.1-RC",
    "1.1",
    "2.0-RC",
    "2.0",
    "2.1-RC",
    "2.1-RC2",
    "2.1",
    "2.2-RC",
    "2.2",
    "2.3-RC",
    "2.3-RC2",
    "2.3",
    "3.0-RC",
    "3.0-RC2",
    "3.0",
    "3.1-RC",
]


class GBFSDatabasePopulateHelper(DatabasePopulateHelper):
    def __init__(self, file_path):
        super().__init__(file_path)

    def filter_data(self):
        # Filtering out the authenticated feeds
        self.df = self.df[pd.isna(self.df["Authentication Info"])]
        # Filtering out feeds with duplicate System IDs
        self.df = self.df[~self.df.duplicated(subset="System ID", keep=False)]

    def fetch_data(self, auto_discovery_url, urls=[], fields=[]):
        fetched_data = {}
        if not auto_discovery_url:
            return
        try:
            response = requests.get(auto_discovery_url)
            response.raise_for_status()
            data = response.json()
            for field in fields:
                fetched_data[field] = data.get(field)
            feeds = None
            for lang_code, lang_data in data.get("data", {}).items():
                if isinstance(lang_data, list):
                    lang_feeds = lang_data
                else:
                    lang_feeds = lang_data.get("feeds", [])
                if lang_code == "en":
                    feeds = lang_feeds
                    break
                elif not feeds:
                    feeds = lang_feeds
            for url in urls:
                fetched_data[url] = self.get_field_url(feeds, url)
            return fetched_data
        except requests.RequestException as e:
            self.logger.error(f"Error fetching data: {e}")
            return {}

    def generate_system_csv_from_db(self):
        # TODO: generate system.csv from db
        stable_ids = "gbfs-" + self.df["System ID"]
        query = self.db.session.query(GbfsFeed)
        query = query.filter(GbfsFeed.stable_id.in_(stable_ids.to_list()))
        query = query.options(
            joinedload(GbfsFeed.locations),
            joinedload(GbfsFeed.gbfs_versions),
            joinedload(GbfsFeed.externalids)
        )
        feeds = query.all()
        data = []
        for feed in feeds:
            system_id = feed.externalids[0].associated_id
            auto_discovery_url = feed.auto_discovery_url
            feed.gbfs_versions.sort(key=lambda x: x.version, reverse=False)
            supported_versions = [version.version for version in feed.gbfs_versions]
            data.append(
                {
                    "System ID": system_id,
                    "Name": feed.operator,
                    "URL": feed.operator_url,
                    "Country Code": feed.locations[0].country_code,
                    "Location": feed.locations[0].municipality,
                    "Auto-Discovery URL": auto_discovery_url,
                    "Supported Versions": " ; ".join(supported_versions)
                }
            )
        df = pd.DataFrame(data)
        return df

    def compare_db_to_csv(self):
        df_from_db = self.generate_system_csv_from_db()
        df_from_csv = self.df[df_from_db.columns]
        df_from_db = df_from_db.fillna("")
        df_from_csv = df_from_csv.fillna("")
        if df_from_db.empty:
            self.logger.debug("No data found in the database.")
            return

        # Align both DataFrames by "System ID"
        df_from_db.set_index("System ID", inplace=True)
        df_from_csv.set_index("System ID", inplace=True)

        # Find rows that are in the CSV but not in the DB
        missing_in_db = df_from_csv[~df_from_csv.index.isin(df_from_db.index)]
        if not missing_in_db.empty:
            self.logger.info("New feeds found in CSV:")
            self.logger.info(missing_in_db)

        # Find rows that are in both, but with differences
        common_ids = df_from_db.index.intersection(df_from_csv.index)

        # Calculate differences only for rows with common IDs
        df_db_common = df_from_db.loc[common_ids]
        df_csv_common = df_from_csv.loc[common_ids]

        # Calculate differences and create a boolean mask
        differences = df_db_common != df_csv_common

        # Select rows where any difference exists
        differing_rows = df_db_common[differences.any(axis=1)]

        if not differing_rows.empty:
            print("Rows with differences:")
            for idx in differing_rows.index:
                print(f"Differences for System ID {idx}:")
                db_row = df_db_common.loc[idx]
                csv_row = df_csv_common.loc[idx]
                diff = db_row != csv_row
                print(f"DB Row: {db_row[diff].to_dict()}")
                print(f"CSV Row: {csv_row[diff].to_dict()}")
                print(80 * "-")
        self.df = differing_rows.reset_index()

    @staticmethod
    def get_stable_id(row):
        return f"gbfs-{row['System ID']}"

    @staticmethod
    def get_external_id(feed_id, system_id):
        return Externalid(
            feed_id=feed_id,
            associated_id=str(system_id),
            source="gbfs")

    def get_data_content(self, url):
        try:
            if url:
                response = requests.get(url)
                response.raise_for_status()
                system_info = response.json().get("data", {})
                return system_info

        except requests.RequestException as e:
            self.logger.error(f"Error fetching data: {e}")
            return None

    @staticmethod
    def get_field_url(fields, field_name):
        """Helper function to get the URL of a specific feed by name."""
        for field in fields:
            if field.get("name") == field_name:
                return field.get("url")
        return None

    def get_license_url(self, system_info):
        try:
            if system_info is None:
                return None
            # Fetching license_url or license_id
            license_url = system_info.get("license_url")
            if not license_url:
                license_id = system_info.get("license_id")
                if license_id:
                    # TODO: match id to url
                    return f"License ID: {license_id}"
                else:
                    # Default license URL
                    return "https://creativecommons.org/licenses/by/4.0/"
            return license_url
        except Exception as e:
            self.logger.error(f"Error fetching data: {e}")
            return None

    def get_gbfs_versions(self, gbfs_versions_url, auto_discovery_url, auto_discovery_version):
        try:
            version_info = {
                "version": auto_discovery_version if auto_discovery_version else "1.0",
                "url": auto_discovery_url,
            }

            try:
                self.logger.debug(f"Fetching GBFS versions from: {gbfs_versions_url}")
                data = self.get_data_content(gbfs_versions_url)
                gbfs_versions = data.get("versions", [])

                # Update or append the version info from auto-discovery
                version_exists = any(
                    gbfs_version.update({"url": auto_discovery_url}) or True
                    for gbfs_version in gbfs_versions
                    if gbfs_version.get("version") == auto_discovery_version
                )
                if not version_exists:
                    gbfs_versions.append(version_info)
                return gbfs_versions
            except Exception as e:
                self.logger.error(f"Error fetching version data: {e}")

            return [version_info]

        except requests.RequestException as e:
            self.logger.error(f"Error fetching data: {e}")
            return [{"version": "1.0", "url": auto_discovery_url}]

    @staticmethod
    def get_feed_contact_email(system_info):
        if system_info is None:
            return None
        return system_info.get("feed_contact_email", None)

    def populate_db(self):
        start_time = datetime.now()
        configure_polymorphic_mappers()
        self.compare_db_to_csv()

        for index, row in self.df.iterrows():
            stable_id = self.get_stable_id(row)
            gbfs_feed = self.query_feed_by_stable_id(stable_id, "gbfs")
            fetched_data = self.fetch_data(row["Auto-Discovery URL"], ["system_information", "gbfs_versions"], ["version"])
            # If gbfs_feed exists, update its fields; otherwise, create a new feed
            if gbfs_feed:
                feed_id = gbfs_feed.id
                self.logger.info(f"Updating feed {stable_id} - {row['Name']}")
            else:
                feed_id = generate_unique_id()
                self.logger.info(f"Creating new feed for {stable_id} - {row['Name']}")
                gbfs_feed = GbfsFeed(
                    id=feed_id,
                    data_type="gbfs",
                    stable_id=stable_id,
                    created_at=datetime.now(pytz.utc),
                )
                gbfs_feed.externalids = [self.get_external_id(feed_id, row["System ID"])]
                self.db.session.add(gbfs_feed)

            # Update fields for both new and existing feeds
            system_information_content = self.get_data_content(
                fetched_data.get("system_information")
            )
            gbfs_feed.license_url = self.get_license_url(system_information_content)
            gbfs_feed.feed_contact_email = self.get_feed_contact_email(system_information_content)
            gbfs_feed.operator = row["Name"]
            gbfs_feed.operator_url = row["URL"]
            gbfs_feed.auto_discovery_url = row["Auto-Discovery URL"]
            gbfs_feed.updated_at = datetime.now(pytz.utc)  # Assuming there's an updated_at field

            # Manage location
            country_code = self.get_safe_value(row, "Country Code", "")
            municipality = self.get_safe_value(row, "Location", "")
            location_id = self.get_location_id(country_code, None, municipality)
            location = self.db.session.get(Location, location_id) or Location(
                id=location_id,
                country_code=country_code,
                municipality=municipality,
            )
            gbfs_feed.locations.clear()
            gbfs_feed.locations = [location]

            # Update GBFS versions
            versions = self.get_gbfs_versions(
                fetched_data.get("gbfs_versions"), row["Auto-Discovery URL"], fetched_data.get("version")
            )
            existing_versions = [version.version for version in gbfs_feed.gbfs_versions]
            for version in versions:
                version_value = version.get("version")
                if version_value.upper() in OFFICIAL_VERSIONS and version_value not in existing_versions:
                    gbfs_feed.gbfs_versions.append(GbfsVersion(
                        feed_id=feed_id,
                        url=version.get("url"),
                        version=version_value,
                    ))

            # Flush after each iteration
            self.db.session.flush()
            self.logger.info(80 * "-")

        # Commit all changes at the end
        self.db.session.commit()
        end_time = datetime.now()
        self.logger.info(f"Time taken: {end_time - start_time} seconds")


if __name__ == "__main__":
    GBFSDatabasePopulateHelper(set_up_configs()).populate_db()
