#
#   MobilityData 2023
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

from faker import Faker
from faker.generator import random
from datetime import datetime
from shared.database_gen.sqlacodegen_models import (
    Gtfsfeed,
    Gtfsrealtimefeed,
    Gtfsdataset,
)
from test_shared.test_utils.database_utils import clean_testing_db, default_db_url
from shared.database.database import with_db_session


@with_db_session(db_url=default_db_url)
def populate_database(db_session):
    """
    Populates the database with fake data with the following distribution:
    - 10 GTFS feeds
        - 5 active
        - 5 inactive
    - 5 GTFS Realtime feeds
    - 9 GTFS datasets
        - 3 active in active feeds
        - 6 active in inactive feeds
    """
    fake = Faker()
    for i in range(10):
        feed = Gtfsfeed(
            id=fake.uuid4(),
            data_type="gtfs",
            feed_name=fake.name(),
            note=fake.sentence(),
            producer_url=fake.url(),
            authentication_type="0" if (i in [0, 1, 2]) else "1",
            authentication_info_url=None,
            api_key_parameter_name=None,
            license_url=fake.url(),
            stable_id=fake.uuid4(),
            status="active" if (i in [0, 1, 2]) else "inactive",
            feed_contact_email=fake.email(),
            provider=fake.company(),
        )
        db_session.add(feed)

    db_session.flush()
    # GTFS datasets leaving one active feed without a dataset
    active_gtfs_feeds = db_session.query(Gtfsfeed).all()
    for i in range(1, 9):
        gtfs_dataset = Gtfsdataset(
            id=fake.uuid4(),
            feed_id=active_gtfs_feeds[i].id,
            bounding_box="POLYGON((-180 -90, -180 90, 180 90, 180 -90, -180 -90))",
            hosted_url=fake.url(),
            note=fake.sentence(),
            hash=fake.sha256(),
            downloaded_at=datetime.utcnow(),
            stable_id=fake.uuid4(),
        )
        db_session.add(gtfs_dataset)
        db_session.flush()
        active_gtfs_feeds[i].latest_gtfsdataset_id = gtfs_dataset.id

    db_session.flush()
    # GTFS Realtime feeds
    for _ in range(5):
        gtfs_rt_feed = Gtfsrealtimefeed(
            id=fake.uuid4(),
            data_type="gtfs_rt",
            feed_name=fake.company(),
            note=fake.sentence(),
            producer_url=fake.url(),
            authentication_type=random.choice(["0", "1", "2"]),
            authentication_info_url=fake.url(),
            api_key_parameter_name=fake.word(),
            license_url=fake.url(),
            stable_id=fake.uuid4(),
            status=random.choice(["active", "inactive"]),
            feed_contact_email=fake.email(),
            provider=fake.company(),
        )
        db_session.add(gtfs_rt_feed)

    db_session.commit()


def pytest_configure(config):
    """
    Allows plugins and conftest files to perform initial configuration.
    This hook is called for every plugin and initial conftest
    file after command line options have been parsed.
    """


def pytest_sessionstart(session):
    """
    Called after the Session object has been created and
    before performing collection and entering the run test loop.
    """
    clean_testing_db()
    populate_database()


def pytest_sessionfinish(session, exitstatus):
    """
    Called after whole test run finished, right before
    returning the exit status to the system.
    """
    clean_testing_db()


def pytest_unconfigure(config):
    """
    called before test process is exited.
    """
