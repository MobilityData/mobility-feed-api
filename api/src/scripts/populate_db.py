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
    Gtfsrealtimefeed
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
        self.df.status.fillna('active', inplace=True)
        self.df['urls.authentication_type'].fillna(0, inplace=True)
        self.df['features'].fillna('', inplace=True)
        self.df['entity_type'].fillna('', inplace=True)
        self.df.replace(np.nan, None, inplace=True)
        self.df.replace('gtfs-rt', 'gtfs_rt', inplace=True)

    def populate(self):
        """
        Populates the database
        """
        if self.df is None:
            return
        for index, row in self.df.iterrows():
            # Feed
            feed = Feed(
                id=generate_unique_id(),
                data_type=row['data_type'],
                feed_name=row['name'],
                note=row['note'],
                producer_url=row['urls.direct_download'],
                authentication_type=row['urls.authentication_type'] == 1,
                authentication_info_url=row['urls.authentication_info'],
                api_key_parameter_name=row['urls.api_key_parameter_name'],
                license_url=row['urls.license'],
                stable_id=f"mdb-{row['mdb_source_id']}",
                status=row['status']
            )
            self.db.merge(feed)

            # GTFS Dataset
            if feed.data_type == 'gtfs':
                # GTFS Feed
                gtfs_feed = Gtfsfeed(id=feed.id)
                self.db.merge(gtfs_feed)

                # GTFS Dataset
                min_lat = row['location.bounding_box.minimum_latitude']
                max_lat = row['location.bounding_box.maximum_latitude']
                min_lon = row['location.bounding_box.minimum_longitude']
                max_lon = row['location.bounding_box.maximum_longitude']
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
                    stable_id=f"mdb-{row['mdb_source_id']}",
                )
                self.db.merge(gtfs_dataset)

            if feed.data_type == 'gtfs_rt':
                # GTFS RT Feed
                gtfs_rt_feed = Gtfsrealtimefeed(id=feed.id)
                self.db.merge(gtfs_rt_feed)

                # Feed Reference
                # TODO

            # GTFS Component
            for component_name in row['features'].split('-'):
                if len(component_name) == 0:
                    continue
                component = Component(name=component_name)
                self.db.merge(component)
                self.db.merge_relationship(Component, {'name': component_name}, gtfs_dataset, 'datasets')

            # External ID
            mdb_external_id = Externalid(feed_id=feed.id, associated_id=str(row['mdb_source_id']),
                                         source="spreadsheet")  # TODO confirm source
            self.db.merge(mdb_external_id)

            # Entity Type and Entity Type x Feed relationship
            for entity_type_name in row['entity_type'].split('|'):
                if len(entity_type_name) == 0:
                    continue
                entity_type = Entitytype(name=entity_type_name)
                self.db.merge(entity_type)
                self.db.merge_relationship(Entitytype, {'name': entity_type_name}, feed, 'feeds')


if __name__ == '__main__':
    filepath = set_up_configs()
    db_helper = DatabasePopulateHelper(filepath)
    db_helper.populate()
