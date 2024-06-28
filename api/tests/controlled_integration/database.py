import contextlib
from datetime import datetime, timedelta, timezone
from typing import Final

from sqlalchemy import text
from sqlalchemy.engine.url import make_url

from database.database import Database

from scripts.populate_db import DatabasePopulateHelper
from scripts.populate_db_test_data import DatabasePopulateTestDataHelper

import os

TEST_GTFS_FEED_STABLE_IDS = ["mdb-1", "mdb-10", "mdb-20", "mdb-30"]

TEST_DATASET_STABLE_IDS = ["mdb-2", "mdb-3", "mdb-11", "mdb-12"]
TEST_GTFS_RT_FEED_STABLE_ID = "mdb-1561"
TEST_EXTERNAL_IDS = ["external_id_1", "external_id_2", "external_id_3", "external_id_4"]
OLD_VALIDATION_VERSION = "1.0.0"
NEW_VALIDATION_TIME: Final[datetime] = datetime(2023, 2, 1, 10, 10, 10, tzinfo=timezone.utc)
OLD_VALIDATION_TIME = NEW_VALIDATION_TIME - timedelta(hours=1)
NEW_VALIDATION_VERSION = "2.0.0"
VALIDATION_INFO_COUNT_PER_NOTICE = 5
VALIDATION_INFO_NOTICES = 10
VALIDATION_WARNING_COUNT_PER_NOTICE = 3
VALIDATION_WARNING_NOTICES = 4
VALIDATION_ERROR_COUNT_PER_NOTICE = 2
VALIDATION_ERROR_NOTICES = 7
FEATURE_IDS = ["Route Colors", "Bike Allowed", "Headsigns"]

date_string: Final[str] = "2024-01-31 00:00:00"
date_format: Final[str] = "%Y-%m-%d %H:%M:%S"
one_day: Final[timedelta] = timedelta(days=1)
datasets_download_first_date: Final[datetime] = datetime.strptime(date_string, date_format)


def is_localhost(url):
    return url is not None and url.host == "localhost"


@contextlib.contextmanager
def populate_database(db: Database):
    try:
        pwd = os.path.dirname(os.path.abspath(__file__))

        # Check if connected to localhost
        url = make_url(db.engine.url)
        if not is_localhost(url):
            raise Exception("Not connected to localhost, aborting operation")

        db_helper = DatabasePopulateHelper(pwd + "/test_data/sources.csv")
        db_helper.initialize(trigger_downstream_tasks=False)
        db_helper = DatabasePopulateTestDataHelper(pwd + "/test_data/test_datasets.json")
        db_helper.populate()

        yield db
    # except Exception as e:
    #     print(e)
    #     if url is None or not is_localhost(url.host):
    #         raise e
    finally:
        # clean up the testing data regardless of the test result
        if is_localhost(url):
            db.session.execute(text("DELETE FROM feedreference"))
            db.session.execute(text("DELETE FROM notice"))
            db.session.execute(text("DELETE FROM validationreportgtfsdataset"))
            db.session.execute(text("DELETE FROM gtfsdataset"))
            db.session.execute(text("DELETE FROM externalid"))
            db.session.execute(text("DELETE from redirectingid"))
            db.session.execute(text("DELETE FROM gtfsfeed"))
            db.session.execute(text("DELETE FROM gtfsrealtimefeed"))
            db.session.execute(text("DELETE FROM locationfeed"))
            db.session.execute(text("DELETE FROM feed"))
            db.session.execute(text("DELETE FROM location"))
            db.session.execute(text("DELETE FROM featurevalidationreport"))
            db.session.execute(text("DELETE FROM feature"))
            db.session.execute(text("DELETE FROM validationreport"))
            db.commit()
