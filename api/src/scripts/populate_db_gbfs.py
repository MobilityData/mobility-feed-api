from datetime import datetime

import pytz
import requests
from database.database import generate_unique_id
from scripts.database_populate_helper import DatabasePopulateHelper, set_up_configs
import pandas as pd
from database_gen.sqlacodegen_models import GbfsFeed, Location, GbfsVersion

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
    "3.1-RC"
]


class GBFSDatabasePopulateHelper(DatabasePopulateHelper):
    def __init__(self, file_path):
        super().__init__(file_path)

    def filter_data(self):
        # Filtering out the authenticated feeds
        self.df = self.df[pd.isna(self.df['Authentication Info'])]

    @staticmethod
    def get_stable_id(row):
        return f"gbfs-{row['System ID']}"

    @staticmethod
    def get_system_information_content(auto_discovery_url):
        try:
            # Step 1: Access auto-discovery URL
            response = requests.get(auto_discovery_url)
            response.raise_for_status()  # Raise an error if the request failed
            data = response.json()

            # Step 2: Get the address of system_information.json
            feeds = data.get('data', {}).get('en', {}).get('feeds', [])
            system_information_url = None
            for feed in feeds:
                if feed.get('name') == 'system_information':
                    system_information_url = feed.get('url')
                    break

            if system_information_url:
                # Step 3: Get license_url or license_id from system_information.json
                response = requests.get(system_information_url)
                response.raise_for_status()
                system_info = response.json().get('data', {})
                return system_info
        except requests.RequestException as e:
            print(f"Error fetching data: {e}")
            return None

    @staticmethod
    def get_license_url(system_info):
        try:
            if system_info is None:
                return None
            # Fetching license_url or license_id
            license_url = system_info.get('license_url')
            if not license_url:
                license_id = system_info.get('license_id')
                if license_id:
                    # TODO: match id to url
                    return f"License ID: {license_id}"
                else:
                    # Default license URL
                    return "https://creativecommons.org/licenses/by/4.0/"
            return license_url
        except requests.RequestException as e:
            print(f"Error fetching data: {e}")
            return None

    @staticmethod
    def get_gbfs_versions(auto_discovery_url):
        auto_discovery_version = []
        try:
            print(f"auto_discovery_url = {auto_discovery_url}")
            response = requests.get(auto_discovery_url)
            response.raise_for_status()
            data = response.json()
            auto_discovery_version = [{
                "version": data.get('version', '1.0'),
                "url": auto_discovery_url
            }]
            print(f"auto_discovery_version = {auto_discovery_version}")
            feeds = data.get('data', {}).get('en', {}).get('feeds', [])
            gbfs_versions_url = None
            for feed in feeds:
                if feed.get('name') == 'gbfs_versions':
                    gbfs_versions_url = feed.get('url')
                    break
            print(f"gbfs_versions_url = {gbfs_versions_url}")
            if gbfs_versions_url:
                response = requests.get(gbfs_versions_url)
                response.raise_for_status()
                gbfs_versions = response.json().get('data', {}).get('versions', [])
                return gbfs_versions
            return auto_discovery_version
        except requests.RequestException as e:
            print(f"Error fetching data: {e}")
            return auto_discovery_version

    @staticmethod
    def get_feed_contact_email(system_info):
        if system_info is None:
            return None
        return system_info.get('feed_contact_email', None)

    def populate_db(self):
        for index, row in self.df.iterrows():
            gbfs_feed = self.query_feed_by_stable_id(self.get_stable_id(row), 'gbfs')
            if gbfs_feed:
                continue
            system_information = self.get_system_information_content(row['Auto-Discovery URL'])
            print(f"Processing {row['Name']} -- stable_id = {self.get_stable_id(row)}")
            feed_id = generate_unique_id()
            print(f"Feed ID: {feed_id}")
            print(f"System information: {system_information}")
            gbfs_feed = GbfsFeed(
                id=feed_id,
                data_type='gbfs',
                stable_id=self.get_stable_id(row),
                created_at=datetime.now(pytz.utc),
                feed_name=row['Name'],
                license_url=self.get_license_url(system_information),
                feed_contact_email=self.get_feed_contact_email(system_information),
                operator=row['Name'],
                operator_url=row['URL'],
            )
            country_code = self.get_safe_value(row, 'Country Code', "")
            municipality = self.get_safe_value(row, 'Location', "")
            location_id = self.get_location_id(country_code, None, municipality)
            location = self.db.session.get(Location, location_id)
            location = (
                location
                if location
                else Location(
                    id=location_id,
                    country_code=country_code,
                    municipality=municipality,
                )
            )
            gbfs_feed.locations = [location]
            versions = self.get_gbfs_versions(row['Auto-Discovery URL'])
            print(f"Versions = {versions}")
            for version in versions:
                if version.get('version') not in OFFICIAL_VERSIONS:
                    continue
                gbfs_version = GbfsVersion(
                    feed_id=feed_id,
                    auto_discovery_url=version.get('url'),
                    version=version.get('version'), )
                gbfs_feed.gbfs_versions.append(gbfs_version)
            self.db.session.add(gbfs_feed)
            self.db.session.flush()
            print(80 * "-")
        self.db.session.commit()


if __name__ == '__main__':
    GBFSDatabasePopulateHelper(set_up_configs()).populate_db()
