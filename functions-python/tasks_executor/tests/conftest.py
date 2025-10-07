#
#   MobilityData 2025
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
import uuid
from datetime import datetime, UTC, timedelta

from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Gtfsfeed,
    Gtfsdataset,
    Gbfsfeed,
)
from test_shared.test_utils.database_utils import clean_testing_db, default_db_url


@with_db_session(db_url=default_db_url)
def populate_database(db_session: Session | None = None):
    """
    Populates the database with fake data with the following distribution:
    - 2 GTFS feeds
    - 7 GTFS datasets
    """
    # Create 2 GTFS Feeds
    feeds = []
    now = datetime.now(UTC)
    for i in range(2):
        feed = Gtfsfeed(
            id=f"feed_{i}",
            stable_id=f"stable_feed_{i}",
            data_type="gtfs",
            status="active" if i == 0 else "inactive",
            created_at=now,
        )
        db_session.add(feed)
        feeds.append(feed)
    wip_feed = Gtfsfeed(
        id="feed_wip",
        stable_id="stable_feed_wip_feed",
        data_type="gtfs",
        status="active",
        created_at=now,
        operational_status="wip",
    )
    with_visualization_feed = Gtfsfeed(
        id="feed_visualization",
        stable_id="stable_feed_visualization",
        data_type="gtfs",
        status="active",
        created_at=now,
        operational_status="wip",
    )
    db_session.add(wip_feed)
    db_session.add(with_visualization_feed)
    gbfs_feed = Gbfsfeed(
        id=f"feed_{uuid.uuid4()}",
        stable_id=f"stable_feed_gbfs_{uuid.uuid4()}",
        data_type="gbfs",
        status="active",
        created_at=now,
    )
    db_session.add(gbfs_feed)
    db_session.flush()

    datasets = []
    for i in range(7):
        feed = feeds[i % 2]
        dataset = Gtfsdataset(
            id=f"dataset_{i}",
            feed=feed,
            stable_id=f"dataset_stable_{i:04d}",
            downloaded_at=now - timedelta(days=i),
            bounding_box="POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))",
        )
        db_session.add(dataset)
        datasets.append(dataset)

    wip_dataset = Gtfsdataset(
        id="dataset_wip",
        feed=wip_feed,
        stable_id="dataset_stable_wip",
        downloaded_at=now - timedelta(days=i),
        bounding_box="POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))",
    )
    with_visualization_dataset = Gtfsdataset(
        id="dataset_visualization",
        feed=with_visualization_feed,
        stable_id="dataset_stable_visualization",
        downloaded_at=now - timedelta(days=i),
        bounding_box="POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))",
    )
    db_session.add(with_visualization_dataset)
    db_session.add(wip_dataset)
    db_session.flush()
    with_visualization_feed.visualization_dataset_id = with_visualization_dataset.id

    db_session.commit()


def pytest_configure(config):
    """
    Allows plugins and conftest files to perform initial configuration.
    This hook is called for every plugin and initial conftest
    file after command line options have been parsed.
    """


def pytest_sessionstart():
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
