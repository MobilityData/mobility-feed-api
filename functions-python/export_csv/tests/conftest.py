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
from geoalchemy2 import WKTElement

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Validationreport,
    Feature,
    Redirectingid,
    Gtfsfeed,
    Gtfsrealtimefeed,
    Gtfsdataset,
    Location,
    Entitytype,
    Feedosmlocationgroup,
    Osmlocationgroup,
    Geopolygon,
)
from test_shared.test_utils.database_utils import clean_testing_db, default_db_url


@with_db_session(db_url=default_db_url)
def populate_database(db_session):
    """
    Populates the database with fake data with the following distribution:
    - 5 GTFS feeds
        - 2 active
        - 1 inactive
        - 2 deprecated
    - 3 GTFS datasets
    - 4 GTFS Realtime feeds, with 1 of them inactive
    """
    fake = Faker()

    feeds = []
    # We create 3 feeds. The first one is active. The third one is inactive and redirected to the first one.
    # The second one is active but not redirected.
    # First fill the generic parameters
    for i in range(3):
        feed = Gtfsfeed(
            data_type="gtfs",
            feed_name=f"gtfs-{i} Some fake name",
            note=f"gtfs-{i} Some fake note",
            producer_url=f"https://gtfs-{i}_some_fake_producer_url",
            authentication_info_url=None,
            api_key_parameter_name=None,
            license_url=f"https://gtfs-{i}_some_fake_license_url",
            stable_id=f"gtfs-{i}",
            feed_contact_email=f"gtfs-{i}_some_fake_email@fake.com",
            provider=f"gtfs-{i} Some fake company",
            operational_status="published",
            official=True,
        )
        feeds.append(feed)
    db_session.flush()
    # Then fill the specific parameters for each feed
    target_feed = feeds[0]
    target_feed.id = "e3155a30-81d8-40bb-9e10-013a60436d86"  # Just an invented uuid
    target_feed.authentication_type = "0"
    target_feed.status = "active"

    feed = feeds[1]
    feed.id = fake.uuid4()
    feed.authentication_type = "0"
    feed.status = "active"

    source_feed = feeds[2]
    source_feed.id = "6e7c5f17-537a-439a-bf99-9c37f1f01030"
    source_feed.authentication_type = "0"
    source_feed.status = "inactive"
    source_feed.redirectingids = [
        Redirectingid(
            source_id=source_feed.id,
            target_id=target_feed.id,
            redirect_comment="Some redirect comment",
            target=target_feed,
        )
    ]

    for feed in feeds:
        db_session.add(feed)
    db_session.flush()
    for i in range(2):
        feed = Gtfsfeed(
            id=fake.uuid4(),
            data_type="gtfs",
            feed_name=f"gtfs-deprecated-{i} Some fake name",
            note=f"gtfs-deprecated-{i} Some fake note",
            producer_url=f"https://gtfs-deprecated-{i}_some_fake_producer_url",
            authentication_type="0" if (i == 0) else "1",
            authentication_info_url=None,
            api_key_parameter_name=None,
            license_url=f"https://gtfs-{i}_some_fake_license_url",
            stable_id=f"gtfs-deprecated-{i}",
            status="deprecated",
            feed_contact_email=f"gtfs-deprecated-{i}_some_fake_email@fake.com",
            provider=f"gtfs-deprecated-{i} Some fake company",
            operational_status="published",
            official=True,
        )
        db_session.add(feed)

    location_entity = Location(id="CA-quebec-montreal")

    location_entity.country = "Canada"
    location_entity.country_code = "CA"
    location_entity.subdivision_name = "Quebec"
    location_entity.municipality = "Montreal"
    db_session.add(location_entity)
    locations = [location_entity]

    feature1 = Feature(name="Shapes")
    db_session.add(feature1)
    feature2 = Feature(name="Route Colors")
    db_session.add(feature2)

    # GTFS datasets leaving one active feed without a dataset
    active_gtfs_feeds = (
        db_session.query(Gtfsfeed)
        .filter(Gtfsfeed.status == "active")
        .order_by(Gtfsfeed.stable_id)
        .all()
    )

    db_session.flush()
    # the first 2 datasets are for the first active feed, one dataset is for the second active feed
    for i in range(1, 4):
        feed_index = 0 if i in [1, 2] else 1
        wkt_polygon = "POLYGON((-18 -9, -18 9, 18 9, 18 -9, -18 -9))"
        wkt_element = WKTElement(wkt_polygon, srid=4326)
        feed_stable_id = active_gtfs_feeds[feed_index].stable_id
        gtfs_dataset = Gtfsdataset(
            id=fake.uuid4(),
            feed_id=active_gtfs_feeds[feed_index].id,
            bounding_box=wkt_element,
            # Use a url containing the stable id. The program should replace all the is after the feed stable id
            # by latest.zip
            hosted_url=f"https://url_prefix/{feed_stable_id}/dataset-{i}_some_fake_hosted_url",
            note=f"dataset-{i} Some fake note",
            hash=fake.sha256(),
            downloaded_at=datetime(2025, 1, 12),
            stable_id=f"dataset-{i}",
        )
        db_session.add(gtfs_dataset)
        db_session.flush()
        validation_report = Validationreport(
            id=fake.uuid4(),
            validator_version="6.0.1",
            validated_at=datetime(2025, 1, 12),
            html_report=fake.url(),
            json_report=fake.url(),
        )
        validation_report.features.append(feature1)
        validation_report.features.append(feature2)

        db_session.add(validation_report)
        gtfs_dataset.validation_reports.append(validation_report)

        gtfs_dataset.locations = locations

        active_gtfs_feeds[feed_index].gtfsdatasets.append(gtfs_dataset)
        if i != 2:
            active_gtfs_feeds[feed_index].latest_dataset_id = gtfs_dataset.id
        db_session.flush()
        active_gtfs_feeds[feed_index].bounding_box = gtfs_dataset.bounding_box
        active_gtfs_feeds[feed_index].bounding_box_dataset_id = gtfs_dataset.id
    active_gtfs_feeds[0].locations = locations
    active_gtfs_feeds[1].locations = locations

    # Add extracted locations to a feed
    geopolygons = [
        Geopolygon(
            osm_id=fake.random_int(),
            admin_level=2,
            name="Canada",
            iso_3166_1_code="CA",
        ),
        Geopolygon(
            osm_id=fake.random_int(),
            admin_level=4,
            name="Quebec",
            iso_3166_2_code="QC",
        ),
        Geopolygon(
            osm_id=fake.random_int(),
            admin_level=6,
            name="Montreal",
            iso_3166_2_code="QC",
        ),
        Geopolygon(
            osm_id=fake.random_int(),
            admin_level=8,
            name="Laval",
            iso_3166_2_code="QC",
        ),
    ]
    first_feed = active_gtfs_feeds[0]
    first_feed.feedosmlocationgroups = [
        # Location in Montreal, Quebec, Canada with fewer stops
        Feedosmlocationgroup(
            feed_id=first_feed.id,
            stops_count=10,
            group=Osmlocationgroup(
                group_id=".".join(
                    [str(geopolygon.osm_id) for geopolygon in geopolygons[0:3]]
                ),
                group_name="Canada, Quebec, Montreal",
                osms=geopolygons[0:3],
            ),
        ),
        # Location in Laval, Quebec, Canada with the most stops
        Feedosmlocationgroup(
            feed_id=first_feed.id,
            stops_count=100,
            group=Osmlocationgroup(
                group_id=".".join(
                    [
                        str(geopolygon.osm_id)
                        for geopolygon in geopolygons[0:2] + [geopolygons[3]]
                    ]
                ),
                group_name="Canada, Quebec, Laval",
                osms=geopolygons[0:2] + [geopolygons[3]],
            ),
        ),
    ]

    vp_entitytype = db_session.query(Entitytype).filter_by(name="vp").first()

    if not vp_entitytype:
        vp_entitytype = Entitytype(name="vp")
        db_session.add(vp_entitytype)
    tu_entitytype = db_session.query(Entitytype).filter_by(name="tu").first()
    if not tu_entitytype:
        tu_entitytype = Entitytype(name="tu")
        db_session.add(tu_entitytype)

    db_session.flush()
    # GTFS Realtime feeds
    gtfs_rt_feeds = []
    for i in range(3):
        feed = Gtfsrealtimefeed(
            id=fake.uuid4(),
            data_type="gtfs_rt",
            feed_name=f"gtfs-rt-{i} Some fake name",
            note=f"gtfs-rt-{i} Some fake note",
            producer_url=f"https://gtfs-rt-{i}_some_fake_producer_url",
            authentication_type=str(i),
            authentication_info_url=f"https://gtfs-rt-{i}_some_fake_authentication_info_url",
            api_key_parameter_name=f"gtfs-rt-{i}_fake_api_key_parameter_name",
            license_url=f"https://gtfs-rt-{i}_some_fake_license_url",
            stable_id=f"gtfs-rt-{i}",
            status="inactive" if i == 1 else "active",
            feed_contact_email=f"gtfs-rt-{i}_some_fake_email@fake.com",
            provider=f"gtfs-rt-{i} Some fake company",
            entitytypes=[vp_entitytype, tu_entitytype] if i == 0 else [vp_entitytype],
            operational_status="published",
            official=True,
            gtfs_feeds=[active_gtfs_feeds[0]] if i == 0 else [],
        )
        gtfs_rt_feeds.append(feed)

    # Add redirecting IDs (from main branch logic)
    gtfs_rt_feeds[1].redirectingids = [
        Redirectingid(
            source_id=gtfs_rt_feeds[1].id,
            target_id=gtfs_rt_feeds[0].id,
            redirect_comment="comment 1",
            target=gtfs_rt_feeds[0],
        ),
        Redirectingid(
            source_id=gtfs_rt_feeds[1].id,
            target_id=gtfs_rt_feeds[2].id,
            redirect_comment="comment 2",
            target=gtfs_rt_feeds[2],
        ),
    ]

    db_session.add_all(gtfs_rt_feeds)

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
    # clean_testing_db()


def pytest_unconfigure(config):
    """
    called before test process is exited.
    """
