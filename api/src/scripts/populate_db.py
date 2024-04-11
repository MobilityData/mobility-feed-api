import argparse
import os
from pathlib import Path
from queue import PriorityQueue

import pandas
from dotenv import load_dotenv
from sqlalchemy import inspect

from database.database import Database, generate_unique_id
from database_gen.sqlacodegen_models import (
    Entitytype,
    Externalid,
    Gtfsfeed,
    Gtfsrealtimefeed,
    Location,
    Redirectingid,
    Base,
    t_feedsearch,
)
from utils.data_utils import set_up_defaults
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
        self.df = set_up_defaults(self.df)
        self.logger.info(self.df)

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

        # Gather all stable IDs from csv
        stable_ids = [f"mdb-{int(row['mdb_source_id'])}" for index, row in self.df.iterrows()]

        # Query once to get all existing feeds information
        gtfs_feeds = self.db.session.query(Gtfsfeed).filter(Gtfsfeed.stable_id.in_(stable_ids)).all()
        gtfs_rt_feeds = self.db.session.query(Gtfsrealtimefeed).filter(Gtfsrealtimefeed.stable_id.in_(stable_ids)).all()
        locations = self.db.session.query(Location)
        redirects = self.db.session.query(Redirectingid)
        entity_types = self.db.session.query(Entitytype)

        # Keep dicts (maps) of id -> entity, so we can reference the feed information when processing
        feed_map = {feed.stable_id: feed for feed in gtfs_feeds + gtfs_rt_feeds}
        locations_map = {location.id: location for location in locations}
        entity_types_map = {entity_type.name: entity_type for entity_type in entity_types}
        redirects_set = {(redirect_entity.source_id, redirect_entity.target_id) for redirect_entity in redirects}

        for index, row in self.df.iterrows():
            mdb_id = f"mdb-{int(row['mdb_source_id'])}"
            self.logger.debug(f"Populating Database for with Feed [stable_id = {mdb_id}]")

            feed_exists = mdb_id in feed_map
            if not feed_exists:
                self.logger.info(f"New {row['data_type']} feed with stable_id = {mdb_id} has been added.")

            # Feed
            feed_class = Gtfsfeed if row["data_type"] == "gtfs" else Gtfsrealtimefeed
            feed = (
                feed_map[mdb_id]
                if mdb_id in feed_map
                else feed_class(
                    id=generate_unique_id(),
                    stable_id=mdb_id,
                )
            )
            feed_map[mdb_id] = feed
            feed.data_type = row["data_type"]
            feed.feed_name = row["name"]
            feed.note = row["note"]
            feed.producer_url = row["urls.direct_download"]
            feed.authentication_type = str(int(row.get("urls.authentication_type", "0") or "0"))
            feed.authentication_info_url = row["urls.authentication_info"]
            feed.api_key_parameter_name = row["urls.api_key_parameter_name"]
            feed.license_url = row["urls.license"]
            feed.status = row["status"]
            feed.provider = row["provider"]
            feed.feed_contact_email = row["feed_contact_email"]

            # Location
            country_code = row["location.country_code"]
            subdivision_name = row["location.subdivision_name"]
            municipality = row["location.municipality"]
            composite_id = f"{country_code}-{subdivision_name}-{municipality}".replace(" ", "_")
            location_id = composite_id if len(composite_id) > 0 else "unknown"
            location = (
                locations_map[location_id]
                if location_id in locations_map
                else Location(
                    id=location_id,
                    country_code=country_code if country_code != "" else None,
                    subdivision_name=subdivision_name if subdivision_name != "" else None,
                    municipality=municipality if municipality != "" else None,
                )
            )
            location = add_entity(location, 1)
            feed.locations.append(location)
            add_entity(feed, 1 if isinstance(feed, Gtfsfeed) else 3)

            if feed.data_type == "gtfs_rt":
                # Entity Type and Entity Type x GTFSRealtimeFeed relationship
                for entity_type_name in row["entity_type"].replace("|", "-").split("-"):
                    if len(entity_type_name) == 0:
                        continue
                    if entity_type_name not in entity_types_map:
                        entity_types_map[entity_type_name] = Entitytype(name=entity_type_name)
                    entity_type = entity_types_map[entity_type_name]
                    entity_type.feeds.append(feed)

            # External ID
            if not feed_exists:
                mdb_external_id = Externalid(
                    feed_id=feed.id,
                    associated_id=str(int(row["mdb_source_id"])),
                    source="mdb",
                )
                add_entity(mdb_external_id, 4)

        [add_entity(entity_type, 4) for entity_type in entity_types_map.values()]

        # Iterate again over the contents of the csv files to process the feed references.
        for index, row in self.df.iterrows():
            mdb_id = f"mdb-{int(row['mdb_source_id'])}"
            feed = feed_map[mdb_id]
            if row["data_type"] == "gtfs_rt":
                # Feed Reference
                if row["static_reference"] is not None:
                    static_reference_mdb_id = f"mdb-{int(row['static_reference'])}"
                    referenced_feed = feed_map.get(static_reference_mdb_id, None)
                    already_referenced_ids = {ref.id for ref in referenced_feed.gtfs_rt_feeds}
                    if referenced_feed and feed.id not in already_referenced_ids:
                        referenced_feed.gtfs_rt_feeds.append(feed)

            # Process redirects
            raw_redirects = row.get("redirect.id", None)
            redirects_ids = str(raw_redirects).split("|") if raw_redirects is not None else []
            raw_comments = row.get("redirect.comment", None)
            comments = raw_comments.split("|") if raw_comments is not None else []

            if len(redirects_ids) != len(comments):
                self.logger.warning(f"Number of redirect ids and redirect comments differ for feed {mdb_id}")

            for mdb_source_id in redirects_ids:
                if len(mdb_source_id) == 0:
                    # since there is a 1:1 correspondence between redirect ids and comments, skip also the comment
                    comments = comments[1:]
                    continue
                if comments:
                    comment = comments.pop(0)
                else:
                    comment = ""

                target_stable_id = f"mdb-{int(float(mdb_source_id))}"
                target_feed = feed_map.get(target_stable_id, None)

                if target_feed:
                    if target_feed.id != feed.id and (feed.id, target_feed.id) not in redirects_set:
                        redirect = Redirectingid(source_id=feed.id, target_id=target_feed.id, redirect_comment=comment)
                        add_entity(redirect, 5)
                    else:
                        self.logger.error(f"Feed has redirect pointing to itself {mdb_id}")
                else:
                    self.logger.warning(f"Could not find redirect target feed {target_stable_id} for feed {mdb_id}")

        priority = 1
        while not entities_index.empty():
            next_priority, entity_index = entities_index.get()
            if priority != next_priority:
                self.logger.debug(f"Flushing for priority {priority}")
                priority = next_priority
                self.db.flush()
            self.fast_merge(entities[entity_index])

        self.logger.info("Refreshing MATERIALIZED FEED SEARCH VIEW - Started")
        self.db.session.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {t_feedsearch.name}")
        self.logger.info("Refreshing MATERIALIZED FEED SEARCH VIEW - Completed")

        self.db.commit()


if __name__ == "__main__":
    filepath = set_up_configs()
    db_helper = DatabasePopulateHelper(filepath)
    db_helper.populate()
