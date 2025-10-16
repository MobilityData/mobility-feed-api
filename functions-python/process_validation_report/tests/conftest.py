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

from datetime import datetime

from faker import Faker

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Gtfsfeed,
    Gtfsdataset,
    Validationreport,
    Notice,
)
from test_shared.test_utils.database_utils import clean_testing_db, default_db_url


@with_db_session(db_url=default_db_url)
def populate_database(db_session):
    """
    Populates the database with fake data with the following distribution:
    """
    fake = Faker()
    # Create GTFS feeds
    feed = Gtfsfeed(
        id="feed_1",
        data_type="gtfs",
        feed_name="feed_name",
        note="gtfs-Some fake note",
        producer_url="https://some_fake_producer_url",
        authentication_info_url=None,
        api_key_parameter_name=None,
        license_url="https://some_fake_license_url",
        stable_id="feed_stable_id",
        feed_contact_email="some_fake_email@fake.com",
        provider="Some fake company",
        operational_status="published",
        official=True,
    )
    db_session.add(feed)

    # Create GTFS datasets
    gtfs_dataset = Gtfsdataset(
        id="dataset_1",
        feed_id="feed_1",
        # Use an url containing the stable id. The program should replace all the is after the feed stable id
        # by latest.zip
        hosted_url="https://some_fake_hosted_url",
        note="dataset_1 Some fake note",
        hash=fake.sha256(),
        downloaded_at=datetime.utcnow(),
        stable_id="feed_stable_id",
    )
    # Create validation reports
    validation_reports = []
    validation_report = Validationreport(
        id="report1",
        validator_version="6.0.1",
        validated_at=datetime(2025, 1, 12),
        html_report=fake.url(),
        json_report=fake.url(),
    )
    validation_reports.append(validation_report)
    db_session.add_all(validation_reports)
    gtfs_dataset.validation_reports.append(validation_report)
    db_session.add(gtfs_dataset)
    db_session.flush()
    feed.latest_dataset_id = gtfs_dataset.id
    # Create notices
    notice_list = []

    notice = Notice(
        dataset_id="dataset_1",
        validation_report_id="report1",
        severity="INFO",
        total_notices=5,
        notice_code="info_code_1",
    )
    notice_list.append(notice)
    notice = Notice(
        dataset_id="dataset_1",
        validation_report_id="report1",
        severity="WARNING",
        total_notices=3,
        notice_code="warning_code_1",
    )
    notice_list.append(notice)
    notice = Notice(
        dataset_id="dataset_1",
        validation_report_id="report1",
        severity="ERROR",
        total_notices=2,
        notice_code="error_code_1",
    )
    notice_list.append(notice)
    notice = Notice(
        dataset_id="dataset_1",
        validation_report_id="report1",
        severity="ERROR",
        total_notices=1,
        notice_code="error_code_2",
    )
    notice_list.append(notice)

    db_session.add_all(notice_list)

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
    # Cleaned at the beginning instead of the end so we can examine the DB after the test.
    clean_testing_db()


def pytest_unconfigure(config):
    """
    called before test process is exited.
    """
