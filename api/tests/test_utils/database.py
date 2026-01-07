import contextlib
from datetime import datetime, timedelta
from distutils.util import strtobool
from typing import Final, List

from sqlalchemy.engine.url import make_url

from scripts.populate_db_gbfs import GBFSDatabasePopulateHelper
from tests.test_utils.db_utils import dump_database, is_test_db, dump_raw_database, empty_database
from shared.database.database import Database

from scripts.populate_db_gtfs import GTFSDatabasePopulateHelper
from scripts.populate_db_test_data import DatabasePopulateTestDataHelper

import os

TEST_GTFS_FEED_STABLE_IDS = ["mdb-1", "mdb-10", "mdb-20", "mdb-30"]
TEST_DATASET_STABLE_IDS = ["dataset-1", "dataset-2", "dataset-3", "dataset-4"]
TEST_GTFS_RT_FEED_STABLE_ID = "mdb-1561"

date_string: Final[str] = "2024-01-31 00:00:00"
date_format: Final[str] = "%Y-%m-%d %H:%M:%S"
one_day: Final[timedelta] = timedelta(days=1)
datasets_download_first_date: Final[datetime] = datetime.strptime(date_string, date_format)


@contextlib.contextmanager
def populate_database(db: Database, data_dirs: List[str], second_phase_data_dirs: List[str] = None):
    """
    Populate the database in two phases before yielding for tests.
    - First phase: populate with data_dirs.
    - Second phase: populate with more data to see the effect of adding to a DB that is not empty.
    """
    try:
        url = make_url(db.engine.url)
        if not is_test_db(url):
            raise Exception("Not connected to MobilityDatabaseTest, aborting operation")

        # Default is to empty the database before populating. To not empty the database, set the environment variable
        if (keep_db_before_populating := os.getenv("KEEP_DB_BEFORE_POPULATING")) is None or not strtobool(
            keep_db_before_populating
        ):
            empty_database(db, url)

        # --- Phase 1 population ---
        _populate_db_phase(db, data_dirs)

        # --- Phase 2 population (only if provided) ---
        if second_phase_data_dirs is not None:
            _populate_db_phase(db, second_phase_data_dirs)

        yield db

        # Optionally dump the database after tests
        if (test_db_dump_filename := os.getenv("TEST_DB_DUMP_FILENAME")) is not None:
            dump_database(db, test_db_dump_filename)
        if (test_raw_db_dump_filename := os.getenv("TEST_RAW_DB_DUMP_FILENAME")) is not None:
            dump_raw_database(db, test_raw_db_dump_filename)
    except Exception as e:
        print(e)
        raise e


def _populate_db_phase(db: Database, data_dirs: List[str]):
    """
    Populate the DB with files located in a set of directories.
    Populates GTFS, GBFS, and extra test data, if available.
    """
    csv_filepaths = [
        filepath
        for directory in data_dirs
        if (filepath := os.path.join(directory, "sources_test.csv")) and os.path.isfile(filepath)
    ]
    if csv_filepaths:
        gtfs_db_helper = GTFSDatabasePopulateHelper(csv_filepaths, test_mode=True)
        gtfs_db_helper.initialize(trigger_downstream_tasks=False)

    # GBFS
    gbfs_csv_filepaths = [
        filepath
        for directory in data_dirs
        if (filepath := os.path.join(directory, "systems_test.csv")) and os.path.isfile(filepath)
    ]
    if gbfs_csv_filepaths:
        GBFSDatabasePopulateHelper(gbfs_csv_filepaths, test_mode=True).initialize(
            trigger_downstream_tasks=False, fetch_url=False
        )

    # Extra test data
    json_filepaths = [
        filepath
        for dir in data_dirs
        if (filepath := os.path.join(dir, "extra_test_data.json")) and os.path.isfile(filepath)
    ]
    if json_filepaths:
        db_helper = DatabasePopulateTestDataHelper(json_filepaths)
        db_helper.populate()
