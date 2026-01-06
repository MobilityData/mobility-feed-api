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
import os

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Gtfsfeed,
    Gtfsrealtimefeed,
    Entitytype,
    License,
    Rule,
)
from test_shared.test_utils.database_utils import clean_testing_db, default_db_url

feed_mdb_41 = Gtfsrealtimefeed(
    id="mdb-41",
    data_type="gtfs_rt",
    feed_name="London Transit Commission(RT",
    note="note",
    producer_url="producer_url",
    authentication_type="1",
    authentication_info_url="authentication_info_url",
    api_key_parameter_name="api_key_parameter_name",
    license_url="license_url",
    stable_id="mdb-41",
    status="active",
    feed_contact_email="feed_contact_email",
    provider="provider A",
    entitytypes=[Entitytype(name="vp")],
    operational_status="published",
)

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
    license_id="MIT",
    stable_id="mdb-40",
    status="active",
    feed_contact_email="feed_contact_email",
    provider="provider B",
    gtfs_rt_feeds=[feed_mdb_41],
    operational_status="wip",
)

feed_mdb_400 = Gtfsfeed(
    id="mdb-400",
    data_type="gtfs",
    feed_name="London Transit Commission",
    note="note",
    producer_url="producer_url",
    authentication_type="1",
    authentication_info_url="authentication_info_url",
    api_key_parameter_name="api_key_parameter_name",
    license_url="license_url",
    stable_id="mdb-400",
    status="active",
    feed_contact_email="feed_contact_email",
    provider="provider C",
    gtfs_rt_feeds=[],
    operational_status="published",
)

# Test license objects used by LicensesApiImpl tests
license_std_mit = License(
    id="MIT",
    type="standard",
    is_spdx=True,
    name="MIT License",
    url="https://opensource.org/licenses/MIT",
    description="A short and permissive license.",
)

license_custom_test = License(
    id="custom-test",
    type="custom",
    is_spdx=False,
    name="Custom Test License",
    url="https://example.com/custom-test-license",
    description="Custom license used for testing.",
)

# Test rules associated to licenses
rule_attribution = Rule(
    name="attribution",
    label="Attribution required",
    type="condition",
    description="Must attribute the data source when using the data.",
)

rule_share_alike = Rule(
    name="share-alike",
    label="Share alike",
    type="condition",
    description="Derivative works must be shared under the same terms.",
)

# Attach rules to licenses so LicenseWithRules has content
license_std_mit.rules = [rule_attribution]
license_custom_test.rules = [rule_attribution, rule_share_alike]


@with_db_session(db_url=default_db_url)
def populate_database(db_session):
    """
    Populates the database with fake data with the following distribution:
    - 1 GTFS feeds
    - 1 GTFS Realtime feeds
    """
    db_session.add(feed_mdb_41)
    db_session.add(feed_mdb_40)
    db_session.add(feed_mdb_400)
    db_session.add(rule_attribution)
    db_session.add(rule_share_alike)
    db_session.add(license_std_mit)
    db_session.add(license_custom_test)
    db_session.commit()


def pytest_configure(config):
    """
    Allows plugins and conftest files to perform initial configuration.
    This hook is called for every plugin and initial conftest
    file after command line options have been parsed.
    """
    os.environ["DB_POOL_SIZE"] = "100"


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
