import argparse
import os
from datetime import datetime
from pathlib import Path
from queue import PriorityQueue

import numpy as np
import pandas
from dotenv import load_dotenv
from geoalchemy2 import WKTElement
from sqlalchemy import inspect

from database.database import Database, generate_unique_id
from database_gen.sqlacodegen_models import (
    Component,
    Entitytype,
    Externalid,
    Gtfsdataset,
    Gtfsfeed,
    Gtfsrealtimefeed,
    Location,
    Redirectingid,
    Base,
)
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
    dotenv_path = os.path.join(current_path.parents[3], "config", f".env.{args.env}")
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
        self.df = self.df[(self.df.data_type == "gtfs") | (self.df.data_type == "gtfs-rt")]
        self.set_up_defaults()
        self.logger.info(self.df)

    def set_up_defaults(self):
        """
        Updates the dataframe to match types defined in the database
        """
        self.df.status.fillna("active", inplace=True)
        self.df["urls.authentication_type"].fillna(0, inplace=True)
        self.df["features"].fillna("", inplace=True)
        self.df["entity_type"].fillna("", inplace=True)
        self.df["location.country_code"].fillna("", inplace=True)
        self.df["location.subdivision_name"].fillna("", inplace=True)
        self.df["location.municipality"].fillna("", inplace=True)
        self.df.replace(np.nan, None, inplace=True)
        self.df.replace("gtfs-rt", "gtfs_rt", inplace=True)
        self.df["location.country_code"].replace("unknown", "", inplace=True)
        self.df["location.subdivision_name"].replace("unknown", "", inplace=True)
        self.df["location.municipality"].replace("unknown", "", inplace=True)

    def fast_merge(self, orm_object: Base):
        """
        Faster merge of an orm object that strictly validates the PK in the active session
        This method assumes that the object is clean i.e. not present in the database
        :param orm_object: the object to merge
        :return: True if merge was successful, False otherwise
        """
        try:
            # Check if an object with the same primary key is already in the session
            primary_key = inspect(orm_object.__class__).primary_key
            existing_object = None
            if primary_key:
                conditions = [pk == getattr(orm_object, pk.name) for pk in primary_key]
                existing_objects = self.db.select_from_active_session(orm_object.__class__, conditions)
                if len(existing_objects) == 1:
                    existing_object = existing_objects[0]

            if existing_object:
                # If an object with the same primary key exists, update it with the new data
                for attr, value in orm_object.__dict__.items():
                    if attr != "_sa_instance_state":
                        setattr(existing_object, attr, value)
                return True
            else:
                # Otherwise simply add the object without loading
                return self.db.session.add(orm_object)
        except Exception as e:
            self.logger.error(f"Fast merge query failed with exception: \n{e}")
            return False

    def populate(self):
        """
        Populates the database
        """
        entities = []  # entities to add to the database
        entities_index = PriorityQueue()  # prioritization of the entities to avoid FK violation

        def add_entity(entity, priority):
            # validate that entity is not already added
            primary_key = inspect(entity.__class__).primary_key
            for e in [sim_entity for sim_entity in entities if isinstance(sim_entity, type(entity))]:
                entities_are_equal = all([getattr(e, pk.name) == getattr(entity, pk.name) for pk in primary_key])
                if entities_are_equal:
                    return e
            # add the entity
            entities_index.put((priority, len(entities)))
            entities.append(entity)
            return entity

        if self.df is None:
            return

        # Keep a dict (map) of stable_id -> feed so we can reference the feeds when processing the static_reference
        # and the redirects.
        feed_map = {}
        for index, row in self.df.iterrows():
            mdb_id = f"mdb-{int(row['mdb_source_id'])}"
            self.logger.debug(f"Populating Database for with Feed [stable_id = {mdb_id}]")

            # Feed
            feed_class = Gtfsfeed if row["data_type"] == "gtfs" else Gtfsrealtimefeed
            feed = feed_class(
                id=generate_unique_id(),
                data_type=row["data_type"],
                feed_name=row["name"],
                note=row["note"],
                producer_url=row["urls.direct_download"],
                authentication_type=str(int(row.get("urls.authentication_type", "0") or "0")),
                authentication_info_url=row["urls.authentication_info"],
                api_key_parameter_name=row["urls.api_key_parameter_name"],
                license_url=row["urls.license"],
                stable_id=mdb_id,
                status=row["status"],
                provider=row["provider"],
            )

            feed_map[mdb_id] = feed

            # Location
            country_code = row["location.country_code"]
            subdivision_name = row["location.subdivision_name"]
            municipality = row["location.municipality"]
            composite_id = f"{country_code}-{subdivision_name}-{municipality}".replace(" ", "_")
            location = Location(
                id=composite_id if len(composite_id) > 0 else "unknown",
                country_code=country_code if country_code != "" else None,
                subdivision_name=subdivision_name if subdivision_name != "" else None,
                municipality=municipality if municipality != "" else None,
            )
            location = add_entity(location, 1)
            feed.locations.append(location)
            add_entity(feed, 1 if isinstance(feed, Gtfsfeed) else 3)

            if feed.data_type == "gtfs":
                # GTFS Dataset
                min_lat = row["location.bounding_box.minimum_latitude"]
                max_lat = row["location.bounding_box.maximum_latitude"]
                min_lon = row["location.bounding_box.minimum_longitude"]
                max_lon = row["location.bounding_box.maximum_longitude"]
                bbox = None
                if min_lon is not None and min_lat is not None and max_lon is not None and max_lat is not None:
                    polygon = "POLYGON(({} {}, {} {}, {} {}, {} {}, {} {}))".format(
                        min_lon,
                        min_lat,
                        min_lon,
                        max_lat,
                        max_lon,
                        max_lat,
                        max_lon,
                        min_lat,
                        min_lon,
                        min_lat,
                    )
                    bbox = WKTElement(polygon, srid=4326)
                gtfs_dataset = Gtfsdataset(
                    id=generate_unique_id(),
                    feed_id=feed.id,
                    latest=True,
                    bounding_box=bbox,
                    hosted_url=row["urls.latest"],
                    note=row["note"],
                    download_date=datetime.fromisoformat(
                        row["location.bounding_box.extracted_on"].replace("Z", "+00:00")
                    ),
                    stable_id=mdb_id,
                )
                add_entity(gtfs_dataset, 3)

                # GTFS Component
                for component_name in row["features"].replace("|", "-").split("-"):
                    if len(component_name) == 0:
                        continue
                    component = Component(name=component_name)
                    component.datasets.append(gtfs_dataset)
                    add_entity(component, 4)

            if feed.data_type == "gtfs_rt":
                # Entity Type and Entity Type x GTFSRealtimeFeed relationship
                for entity_type_name in row["entity_type"].replace("|", "-").split("-"):
                    if len(entity_type_name) == 0:
                        continue
                    entity_type = Entitytype(name=entity_type_name)
                    entity_type.feeds.append(feed)
                    add_entity(entity_type, 4)

            # External ID
            mdb_external_id = Externalid(
                feed_id=feed.id,
                associated_id=str(int(row["mdb_source_id"])),
                source="mdb",
            )
            add_entity(mdb_external_id, 4)

        # Iterate again over the contents of the csv files to process the feed references.
        for index, row in self.df.iterrows():
            mdb_id = f"mdb-{int(row['mdb_source_id'])}"
            feed = feed_map[mdb_id]
            if row["data_type"] == "gtfs_rt":
                # Feed Reference
                if row["static_reference"] is not None:
                    static_reference_mdb_id = f"mdb-{int(row['static_reference'])}"
                    referenced_feed = feed_map.get(static_reference_mdb_id, None)
                    if referenced_feed:
                        referenced_feed.gtfs_rt_feeds.append(feed)

            # Process redirects
            raw_redirects = row.get("redirect.id", None)
            redirects_ids = raw_redirects.split("|") if raw_redirects is not None else []
            raw_comments = row.get("redirect.comment", None)
            comments = raw_comments.split("|") if raw_comments is not None else []

            if len(redirects_ids) != len(comments):
                self.logger.warn(f"Number of redirect ids and redirect comments differ for feed {mdb_id}")

            for mdb_source_id in redirects_ids:
                if len(mdb_source_id) == 0:
                    # since there is a 1:1 correspondence between redirect ids and comments, skip also the comment
                    comments = comments[1:]
                    continue
                if comments:
                    comment = comments.pop(0)
                else:
                    comment = ""

                target_stable_id = f"mdb-{mdb_source_id}"
                target_feed = feed_map.get(target_stable_id, None)

                if target_feed:
                    if target_feed.id != feed.id:
                        redirect = Redirectingid(source_id=feed.id, target_id=target_feed.id, redirect_comment=comment)
                        add_entity(redirect, 5)
                    else:
                        self.logger.error(f"Feed has redirect pointing to itself {mdb_id}")
                else:
                    self.logger.warn(f"Could not find redirect target feed {target_stable_id} for feed {mdb_id}")

        priority = 1
        while not entities_index.empty():
            next_priority, entity_index = entities_index.get()
            if priority != next_priority:
                self.logger.debug(f"Flushing for priority {priority}")
                priority = next_priority
                self.db.flush()
            self.fast_merge(entities[entity_index])
        self.db.commit()


if __name__ == "__main__":
    filepath = set_up_configs()
    db_helper = DatabasePopulateHelper(filepath)
    db_helper.populate()
