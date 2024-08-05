import argparse
import logging
import os
from pathlib import Path

import pandas
from dotenv import load_dotenv

from database.database import Database
from utils.logger import Logger

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

    def filter_data(self):
        """
        Filter the data to only include the necessary columns
        """
        pass  # Should be implemented in the child class
