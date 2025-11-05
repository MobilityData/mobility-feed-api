import argparse
import logging
import os
import traceback
from pathlib import Path
from typing import Type, TYPE_CHECKING

import pandas
from dotenv import load_dotenv
from sqlalchemy import text

from shared.database.database import Database
from shared.database.database import configure_polymorphic_mappers
from shared.database_gen.sqlacodegen_models import Feed, Gtfsrealtimefeed, Gtfsfeed, Gbfsfeed
from shared.database_gen.sqlacodegen_models import (
    t_feedsearch,
)
from utils.logger import get_logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logging.basicConfig()
logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)

feed_mapping = {"gtfs_rt": Gtfsrealtimefeed, "gtfs": Gtfsfeed, "gbfs": Gbfsfeed}


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

    def __init__(self, filepaths):
        """
        Specify a list of files to load the csv data from.
        Can also be a single string with a file name.
        """
        self.logger = get_logger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)
        self.db = Database(echo_sql=False)
        self.df = pandas.DataFrame()

        # If filepaths is a string, convert it to a list
        if isinstance(filepaths, str):
            filepaths = [filepaths]

        for filepath in filepaths:
            new_df = pandas.read_csv(filepath, low_memory=False)
            self.df = pandas.concat([self.df, new_df])

        self.filter_data()

    def query_feed_by_stable_id(
        self, session: "Session", stable_id: str, data_type: str | None
    ) -> Gtfsrealtimefeed | Gtfsfeed | None:
        """
        Query the feed by stable id
        """
        model = self.get_model(data_type)
        return session.query(model).filter(model.stable_id == stable_id).first()

    @staticmethod
    def get_model(data_type: str | None) -> Type[Feed]:
        """
        Get the model based on the data type
        """
        return feed_mapping.get(data_type, Feed)

    @staticmethod
    def get_safe_value(row, column_name, default_value):
        """
        Get a safe value from the row
        """
        value = row.get(column_name)
        if not value or pandas.isna(value) or f"{value}".strip() == "":
            return default_value
        return f"{value}".strip()

    @staticmethod
    def get_safe_boolean_value(row, column_name, default_value: bool | None) -> bool | None:
        """
        Get a safe boolean value from the row
        Only allowed values are "true" and "false" (case insensitive)
        Anything else returns the default.
        """
        value = row.get(column_name)
        if value is None or pandas.isna(value) or f"{value}".strip() == "":
            return default_value
        # I am not sure if pandas will convert "TRUE" and "FALSE" to boolean, so go back to using a string
        value = f"{value}".strip().lower()
        if value == "true":
            return True
        if value == "false":
            return False
        return default_value

    @staticmethod
    def get_location_id(country_code, subdivision_name, municipality):
        """
        Get the location ID
        """
        composite_id = f"{country_code}-{subdivision_name}-{municipality}".replace(" ", "_")
        location_id = composite_id if len(composite_id) > 2 else None
        return location_id

    def filter_data(self):
        """
        Filter the data to only include the necessary columns
        """
        pass  # Should be implemented in the child class

    def populate_db(self, session: "Session", fetch_url: bool = True):
        """
        Populate the database with the data
        """
        pass  # Should be implemented in the child class

    def trigger_downstream_tasks(self):
        """
        Trigger downstream tasks
        """
        pass  # Should be implemented in the child class

    # Extracted the following code from main, so it can be executed as a library function
    def initialize(self, trigger_downstream_tasks: bool = True, fetch_url: bool = True):
        try:
            configure_polymorphic_mappers()
            with self.db.start_db_session() as session:
                self.populate_db(session, fetch_url=fetch_url)
                session.commit()

                self.logger.info("Refreshing MATERIALIZED FEED SEARCH VIEW - Started")
                session.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {t_feedsearch.name}"))
                self.logger.info("Refreshing MATERIALIZED FEED SEARCH VIEW - Completed")
                session.commit()
                self.logger.info("\n----- Database populated with sources.csv data. -----")
                if trigger_downstream_tasks:
                    self.trigger_downstream_tasks()
        except Exception as e:
            self.logger.error(f"\n------ Failed to populate the database with sources.csv: {e} -----\n")
            traceback.print_exc()
            exit(1)
