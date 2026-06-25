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
from shared.database.users_database import with_users_db_session
from shared.database_gen.sqlacodegen_models import (
    Gtfsfeed,
    Gtfsdataset,
    Gbfsfeed,
)
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    NotificationEvent,
    NotificationEventFeed,
    NotificationLog,
    NotificationSubscription,
    NotificationType,
)
from shared.notifications.notification_constants import NotificationTypeId
from test_shared.test_utils.database_utils import (
    clean_testing_db,
    default_db_url,
    default_users_db_url,
    clean_testing_users_db,
)


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

    # Feeds for feed-availability tests
    availability_feeds = [
        Gtfsfeed(
            id="feed_availability_1",
            stable_id="stable_feed_availability_1",
            data_type="gtfs",
            status="active",
            operational_status="published",
            producer_url="http://producer1.example.com/feed.zip",
            created_at=now,
        ),
        Gtfsfeed(
            id="feed_availability_2",
            stable_id="stable_feed_availability_2",
            data_type="gtfs",
            status="active",
            operational_status="published",
            producer_url="http://producer2.example.com/feed.zip",
            created_at=now,
        ),
        # Should NOT be returned — inactive
        Gtfsfeed(
            id="feed_availability_inactive",
            stable_id="stable_feed_availability_inactive",
            data_type="gtfs",
            status="inactive",
            operational_status="published",
            producer_url="http://producer3.example.com/feed.zip",
            created_at=now,
        ),
        # Should NOT be returned — deprecated
        Gtfsfeed(
            id="feed_availability_deprecated",
            stable_id="stable_feed_availability_deprecated",
            data_type="gtfs",
            status="deprecated",
            operational_status="published",
            producer_url="http://producer5.example.com/feed.zip",
            created_at=now,
        ),
        # Should NOT be returned — no producer_url
        Gtfsfeed(
            id="feed_availability_no_url",
            stable_id="stable_feed_availability_no_url",
            data_type="gtfs",
            status="active",
            operational_status="published",
            producer_url=None,
            created_at=now,
        ),
    ]
    for feed in availability_feeds:
        db_session.add(feed)

    db_session.commit()


@with_users_db_session(db_url=default_users_db_url)
def populate_users_database(db_session: Session | None = None):
    """Seed baseline data into the users test database.

    Provides the reference notification types and a few app users that the
    notification dispatch tests build their subscriptions and events on top of.

    Idempotent: ``clean_testing_users_db`` operates on the feeds metadata and
    therefore does not clear users-specific tables, so we clear the
    notification write tables and upsert the baseline rows via ``merge`` to keep
    this safe to run on every session start.
    """
    db_session.query(NotificationLog).delete()
    db_session.query(NotificationEventFeed).delete()
    db_session.query(NotificationEvent).delete()
    db_session.query(NotificationSubscription).delete()
    db_session.flush()

    for notification_type in (
        NotificationType(
            id=NotificationTypeId.FEED_URL_UPDATED, description="Feed URL updated"
        ),
        NotificationType(
            id=NotificationTypeId.ADMIN_EVENT_SUMMARY, description="Admin summary"
        ),
        NotificationType(
            id=NotificationTypeId.API_ANNOUNCEMENTS, description="API announcements"
        ),
    ):
        db_session.merge(notification_type)
    for app_user in (
        AppUser(id="user-alice", email="alice@example.com", full_name="Alice"),
        AppUser(id="user-bob", email="bob@example.com", full_name="Bob"),
        AppUser(id="user-admin", email="admin@example.com", full_name="Admin"),
    ):
        db_session.merge(app_user)


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
    clean_testing_users_db()
    populate_database()
    populate_users_database()


def pytest_sessionfinish(session, exitstatus):
    """
    Called after whole test run finished, right before
    returning the exit status to the system.
    """
    clean_testing_db()
    clean_testing_users_db()


def pytest_unconfigure(config):
    """
    called before test process is exited.
    """
