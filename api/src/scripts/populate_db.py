import argparse
import logging
import os
from pathlib import Path
from typing import Type, TYPE_CHECKING

import pandas
from dotenv import load_dotenv

from shared.database.database import Database
from shared.database_gen.sqlacodegen_models import Feed, Gtfsrealtimefeed, Gtfsfeed, Gbfsfeed
from utils.logger import Logger

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
        self.logger = Logger(self.__class__.__name__).get_logger()
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
        if not row[column_name] or pandas.isna(row[column_name]) or f"{row[column_name]}".strip() == "":
            return default_value if default_value is not None else None
        return f"{row[column_name]}".strip()

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
