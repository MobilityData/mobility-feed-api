import argparse
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas
from dotenv import load_dotenv
from geoalchemy2 import WKTElement

from database.database import Database, generate_unique_id
from database_gen.sqlacodegen_models import Component, Feed, Entitytype, Externalid, Gtfsdataset, Gtfsfeed, \
    Gtfsrealtimefeed, Location
from utils.logger import Logger


def set_up_configs():
    """
    Set up function
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", help="Environment to use", default="local")
    parser.add_argument("--filepath", help="Absolute path for the data file", required=True)
    args = parser.parse_args()
    current_path = Path(__file__).resolve()
    dotenv_path = os.path.join(current_path.parents[3], 'config', f'.env.{args.env}')
    load_dotenv(dotenv_path=dotenv_path)
    return args.filepath


class DatabasePopulateHelper:
    """
    Helper class to populate the database
    """

    def __init__(self, filepath):
        self.logger = Logger(self.__class__.__module__).get_logger()
        self.db = Database()
        self.df = pandas.read_csv(filepath)  # contains the data to populate the database

        # Filter unsupported data types
        self.df = self.df[(self.df.data_type == 'gtfs') | (self.df.data_type == 'gtfs-rt')]
        self.set_up_defaults()
        self.logger.info(self.df)

    def set_up_defaults(self):
        """
        Updates the dataframe to match types defined in the database
        """
        self.df.status.fillna('active', inplace=True)
        self.df['urls.authentication_type'].fillna(0, inplace=True)
        self.df['features'].fillna('', inplace=True)
        self.df['entity_type'].fillna('', inplace=True)
        self.df['location.country_code'].fillna('', inplace=True)
        self.df['location.subdivision_name'].fillna('', inplace=True)
        self.df['location.municipality'].fillna('', inplace=True)
        self.df.replace(np.nan, None, inplace=True)
        self.df.replace('gtfs-rt', 'gtfs_rt', inplace=True)

    def populate(self):
        """
        Populates the database
        """
        if self.df is None:
            return
        for index, row in self.df.iterrows():
            mdb_id = f"mdb-{int(row['mdb_source_id'])}"

            # Feed
            feed_class = Gtfsfeed if row['data_type'] == 'gtfs' else Gtfsrealtimefeed
            feed = feed_class(
                id=generate_unique_id(),
                data_type=row['data_type'],
                feed_name=row['name'],
                note=row['note'],
                producer_url=row['urls.direct_download'],
                authentication_type=str(int(row['urls.authentication_type'])),
                authentication_info_url=row['urls.authentication_info'],
                api_key_parameter_name=row['urls.api_key_parameter_name'],
                license_url=row['urls.license'],
                stable_id=mdb_id,
                status=row['status'],
                provider=row['provider']
            )
            self.db.merge(feed)

            # Location
            country_code = row['location.country_code']
            subdivision_name = row['location.subdivision_name']
            municipality = row['location.municipality']
            composite_id = f'{country_code}-{subdivision_name}-{municipality}'.replace(' ', '_')
            location = Location(
                id=composite_id,
                country_code=country_code,
                subdivision_name=subdivision_name,
                municipality=municipality
            )
            self.db.merge(location)
            self.db.merge_relationship(Feed, {'id': feed.id}, location, 'location')

            if feed.data_type == 'gtfs':
                # GTFS Dataset
                min_lat = row['location.bounding_box.minimum_latitude']
                max_lat = row['location.bounding_box.maximum_latitude']
                min_lon = row['location.bounding_box.minimum_longitude']
                max_lon = row['location.bounding_box.maximum_longitude']
                bbox = None
                if min_lon is not None and min_lat is not None and max_lon is not None and max_lat is not None:
                    polygon = 'POLYGON(({} {}, {} {}, {} {}, {} {}, {} {}))'.format(
                        min_lon, min_lat,
                        min_lon, max_lat,
                        max_lon, max_lat,
                        max_lon, min_lat,
                        min_lon, min_lat
                    )
                    bbox = WKTElement(polygon, srid=4326)
                gtfs_dataset = Gtfsdataset(
                    id=generate_unique_id(),
                    feed_id=feed.id,
                    latest=True,
                    bounding_box=bbox,
                    hosted_url=row['urls.latest'],
                    note=row['note'],
                    download_date=datetime.fromisoformat(
                        row['location.bounding_box.extracted_on'].replace("Z", "+00:00")),
                    stable_id=mdb_id,
                )
                gtfs_dataset_merged = self.db.merge(gtfs_dataset)

                # GTFS Component
                if gtfs_dataset_merged:
                    for component_name in row['features'].replace('|', '-').split('-'):
                        if len(component_name) == 0:
                            continue
                        component = Component(name=component_name)
                        self.db.merge(component)
                        self.db.merge_relationship(Component, {'name': component_name}, gtfs_dataset, 'dataset')

            if feed.data_type == 'gtfs_rt':
                # Entity Type and Entity Type x GTFSRealtimeFeed relationship
                for entity_type_name in row['entity_type'].replace('|', '-').split('-'):
                    if len(entity_type_name) == 0:
                        continue
                    entity_type = Entitytype(name=entity_type_name)
                    self.db.merge(entity_type)
                    self.db.merge_relationship(Entitytype, {'name': entity_type_name}, feed, 'feed')

                # Feed Reference
                if row['static_reference'] is not None:
                    referenced_feeds_list = self.db.select(
                        Feed,
                        [Feed.stable_id == f"mdb-{int(row['static_reference'])}"]
                    )
                    if len(referenced_feeds_list) == 1:
                        self.db.merge_relationship(Gtfsfeed, {'id': referenced_feeds_list[0].id}, feed, 'gtfs_rt_feed')
                    else:
                        self.logger.error(
                            f'Couldn\'t create reference from {feed.stable_id} to {row["static_reference"]}'
                        )

            # External ID
            mdb_external_id = Externalid(feed_id=feed.id, associated_id=str(int(row['mdb_source_id'])),
                                         source='mdb')
            self.db.merge(mdb_external_id)


if __name__ == '__main__':
    filepath = set_up_configs()
    db_helper = DatabasePopulateHelper(filepath)
    db_helper.populate()
