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
from database_gen.sqlacodegen_models import Gtfsfeed
from test_utils.database_utils import clean_testing_db, get_testing_session

feed_mdb_40 = Gtfsfeed(
    id="mdb-40",
    data_type="gtfs",
    feed_name="London Transit Commission",
    note="note",
    producer_url="producer_url",
    authentication_type="1",
    authentication_info_url="authentication_info_url",
    api_key_parameter_name="api_key_parameter_name",
    license_url="license_url",
    stable_id="mdb-40",
    status="active",
    feed_contact_email="feed_contact_email",
    provider="provider",
)


def populate_database():
    """
    Populates the database with fake data with the following distribution:
    - 1 GTFS feeds
        - 5 active
        - 5 inactive
    - 5 GTFS Realtime feeds
    - 9 GTFS datasets
        - 3 active in active feeds
        - 6 active in inactive feeds
    """
    session = get_testing_session()

    session.add(feed_mdb_40)
    session.commit()


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
