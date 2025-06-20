from datetime import datetime, timezone
from typing import Final

import pytest
from faker import Faker
from sqlalchemy.orm import Query

from feeds.impl.datasets_api_impl import DatasetsApiImpl
from feeds.impl.feeds_api_impl import FeedsApiImpl
from shared.common.db_utils import apply_bounding_filtering
from shared.database.database import Database, generate_unique_id
from shared.database_gen.sqlacodegen_models import Feature, Gtfsfeed
from tests.test_utils.database import TEST_GTFS_FEED_STABLE_IDS, TEST_DATASET_STABLE_IDS

VALIDATION_ERROR_NOTICES = 7
NEW_VALIDATION_VERSION = "2.0.0"
NEW_VALIDATION_TIME: Final[datetime] = datetime(2023, 2, 1, 10, 10, 10, tzinfo=timezone.utc)
VALIDATION_INFO_COUNT_PER_NOTICE = 5
VALIDATION_INFO_NOTICES = 10
VALIDATION_WARNING_COUNT_PER_NOTICE = 3
VALIDATION_WARNING_NOTICES = 4
VALIDATION_ERROR_COUNT_PER_NOTICE = 2


BASE_QUERY = Query([Gtfsfeed])
fake = Faker()


def test_database_singleton(test_database):
    assert test_database is Database()


def test_bounding_box_dateset_exists(test_database):
    with test_database.start_db_session() as session:
        assert len(test_database.select(session, query=BASE_QUERY)) >= 1


def assert_bounding_box_found(latitudes, longitudes, method, expected_found, test_database):
    with test_database.start_db_session() as session:
        query = apply_bounding_filtering(BASE_QUERY, latitudes, longitudes, method)
        assert query is not None, "apply_bounding_filtering returned None"
        result = session.execute(query).all()
        assert (len(result) > 0) is expected_found


@pytest.mark.parametrize(
    "latitudes,longitudes,method,expected_found",
    [
        ("37, 39", "-85,-84", "completely_enclosed", True),  # completely enclosed
        # min latitude is too high
        ("37.7, 39", "-85,-84", "completely_enclosed", False),
        # max latitude is too low
        ("37, 38", "-85,-84", "completely_enclosed", False),
        # min longitude is too low
        ("37, 39", "-84.7,-84", "completely_enclosed", False),
        # max longitude is too high
        ("37, 39", "-85,-84.5", "completely_enclosed", False),
    ],
)
def test_bounding_box_completed_closed(latitudes, longitudes, method, expected_found, test_database):
    assert_bounding_box_found(latitudes, longitudes, method, expected_found, test_database)


@pytest.mark.parametrize(
    "latitudes,longitudes,method,expected_found",
    [
        # completely enclosed, still considered as partially enclosed
        ("37.7, 38", "-84.7,-84.6", "partially_enclosed", True),
        # min latitude is too low
        ("37, 38", "-84.7,-84.6", "partially_enclosed", True),
        # max latitude is too high
        ("37.7, 39", "-84.7,-84.6", "partially_enclosed", True),
        # min longitude is too low
        ("37.7, 38", "-85,-84.6", "partially_enclosed", True),
        # max longitude is too high
        ("37.7, 38", "-84.7,-83", "partially_enclosed", True),
        ("1, 2", "3, 4", "partially_enclosed", False),  # disjoint
        ("37, 39", "-85,-83", "partially_enclosed", False),  # contained
    ],
)
def test_bounding_box_partial_closed(latitudes, longitudes, method, expected_found, test_database):
    assert_bounding_box_found(latitudes, longitudes, method, expected_found, test_database)


@pytest.mark.parametrize(
    "latitudes,longitudes,method,expected_found",
    [
        ("37.7, 38", "-84.7,-84.6", "disjoint", False),  # completely enclosed
        ("37, 38", "-84.7,-84.6", "disjoint", False),  # overlap
        ("1, 2", "3, 4", "disjoint", True),  # disjoint
        ("37, 39", "-85,-83", "disjoint", False),  # contained
    ],
)
def test_bounding_box_disjoint(latitudes, longitudes, method, expected_found, test_database):
    assert_bounding_box_found(latitudes, longitudes, method, expected_found, test_database)


def test_merge_gtfs_feed(test_database):
    with test_database.start_db_session() as session:
        results = {
            feed.id: feed
            for feed in FeedsApiImpl().get_gtfs_feeds(
                None, None, None, None, None, None, None, None, None, None, None, db_session=session
            )
            if feed.id in TEST_GTFS_FEED_STABLE_IDS
        }

    assert len(results) == len(TEST_GTFS_FEED_STABLE_IDS)
    feed_1 = results.get(TEST_GTFS_FEED_STABLE_IDS[0])
    feed_2 = results.get(TEST_GTFS_FEED_STABLE_IDS[1])

    assert feed_1 is not None

    assert feed_1.latest_dataset.id == TEST_DATASET_STABLE_IDS[1]
    assert sorted([redirect.target_id for redirect in feed_1.redirects]) == [
        TEST_GTFS_FEED_STABLE_IDS[1],
        TEST_GTFS_FEED_STABLE_IDS[2],
    ]

    assert feed_2 is not None


def test_validation_report(test_database):
    with test_database.start_db_session() as session:
        result = DatasetsApiImpl().get_dataset_gtfs(id=TEST_DATASET_STABLE_IDS[0], db_session=session)

    assert result is not None
    validation_report = result.validation_report
    assert validation_report is not None
    assert validation_report.validator_version == NEW_VALIDATION_VERSION
    assert validation_report.validated_at == NEW_VALIDATION_TIME


def test_generate_unique_id():
    unique_id = generate_unique_id()
    assert len(unique_id) == 36  # UUIDs are 36 characters long
    generated_ids = []
    for _ in range(100):
        generated_ids.append(generate_unique_id())
    unique_ids = set(generated_ids)
    assert len(unique_ids) == len(generated_ids)  # All ids are unique


def test_database_connection():
    db = Database()
    assert db.is_connected()


def test_insert_and_select():
    db = Database()
    feature_name = fake.name()
    new_feature = Feature(name=feature_name)
    with db.start_db_session() as session:
        session.merge(new_feature)

    with db.start_db_session() as new_session:
        results_after_session_closed = db.select(new_session, Feature, conditions=[Feature.name == feature_name])
        assert len(results_after_session_closed) == 1
        assert results_after_session_closed[0][0].name == feature_name

from shared.database_gen.sqlacodegen_models import (
    Feed,
    FeedLog,
    Gtfsfeed,
    Gtfsrealtimefeed,
    Location,
    LocationFeed,
    Gtfsdataset,
    Provider,
    ProviderFeed,
    EntityType,
    EntityTypeFeed,
    FeedReference,
    Redirectingid,
)
from sqlalchemy import select as sql_select

def test_cascade_delete_basic_feed(test_database):
    db = test_database
    feed_id = generate_unique_id()
    location_id = generate_unique_id()
    dataset_id = generate_unique_id()

    with db.start_db_session() as session:
        # Create Feed
        feed = Feed(id=feed_id, stable_id=feed_id, data_type="gtfs", feed_name="Test Feed for Cascade Delete")
        session.add(feed)

        # Create related entities
        location = Location(id=location_id, country_code="US", subdivision_name="CA", municipality="Testville")
        session.add(location)
        location_feed = LocationFeed(location_id=location_id, feed_id=feed_id)
        session.add(location_feed)

        gtfs_dataset = Gtfsdataset(id=dataset_id, feed_id=feed_id, stable_id=dataset_id, downloaded_at=datetime.now(timezone.utc))
        session.add(gtfs_dataset)
        session.commit()

        # Verify creation
        assert session.get(Feed, feed_id) is not None
        assert session.get(LocationFeed, (location_id, feed_id)) is not None
        assert session.get(Gtfsdataset, dataset_id) is not None

    # Delete Feed
    with db.start_db_session() as session:
        feed_to_delete = session.get(Feed, feed_id)
        session.delete(feed_to_delete)
        session.commit()

    # Verify deletion
    with db.start_db_session() as session:
        assert session.get(Feed, feed_id) is None
        assert session.get(LocationFeed, (location_id, feed_id)) is None
        assert session.get(Gtfsdataset, dataset_id) is None
        # Location and Provider should not be deleted as they are not directly dependent
        assert session.get(Location, location_id) is not None


def test_cascade_delete_gtfs_feed(test_database):
    db = test_database
    gtfs_feed_id = generate_unique_id()
    related_gtfs_rt_feed_id = generate_unique_id() # For FeedReference

    with db.start_db_session() as session:
        # Create GTFSFeed (also creates a base Feed)
        gtfs_feed = Gtfsfeed(id=gtfs_feed_id, stable_id=gtfs_feed_id, feed_name="Test GTFS Feed")
        session.add(gtfs_feed)

        # Create a GTFS RT Feed for the reference
        gtfs_rt_feed = Gtfsrealtimefeed(id=related_gtfs_rt_feed_id, stable_id=related_gtfs_rt_feed_id, feed_name="Test GTFS RT Feed for Ref")
        session.add(gtfs_rt_feed)
        session.flush() # Ensure IDs are available for FeedReference

        # Create FeedReference
        feed_reference = FeedReference(gtfs_rt_feed_id=related_gtfs_rt_feed_id, gtfs_feed_id=gtfs_feed_id)
        session.add(feed_reference)
        session.commit()

        # Verify creation
        assert session.get(Gtfsfeed, gtfs_feed_id) is not None
        assert session.get(Feed, gtfs_feed_id) is not None # Base feed
        assert session.get(FeedReference, (related_gtfs_rt_feed_id, gtfs_feed_id)) is not None

    # Delete GTFSFeed
    with db.start_db_session() as session:
        feed_to_delete = session.get(Gtfsfeed, gtfs_feed_id)
        session.delete(feed_to_delete)
        session.commit()

    # Verify deletion
    with db.start_db_session() as session:
        assert session.get(Gtfsfeed, gtfs_feed_id) is None
        assert session.get(Feed, gtfs_feed_id) is None # Base feed should also be deleted
        assert session.get(FeedReference, (related_gtfs_rt_feed_id, gtfs_feed_id)) is None
        assert session.get(Gtfsrealtimefeed, related_gtfs_rt_feed_id) is not None # The other feed should still exist


def test_cascade_delete_gtfs_realtime_feed(test_database):
    db = test_database
    gtfs_rt_feed_id = generate_unique_id()
    related_gtfs_feed_id = generate_unique_id() # For FeedReference
    entity_type_name = "vehicle_positions"


    with db.start_db_session() as session:
        # Create GTFSRealtimeFeed (also creates a base Feed)
        gtfs_rt_feed = Gtfsrealtimefeed(id=gtfs_rt_feed_id, stable_id=gtfs_rt_feed_id, feed_name="Test GTFS RT Feed")
        session.add(gtfs_rt_feed)

        # Create EntityType if it doesn't exist
        entity_type = session.get(EntityType, entity_type_name)
        if not entity_type:
            entity_type = EntityType(name=entity_type_name)
            session.add(entity_type)
        session.flush()


        # Create EntityTypeFeed
        entity_type_feed = EntityTypeFeed(entity_name=entity_type_name, feed_id=gtfs_rt_feed_id)
        session.add(entity_type_feed)

        # Create a GTFS Feed for the reference
        gtfs_feed = Gtfsfeed(id=related_gtfs_feed_id, stable_id=related_gtfs_feed_id, feed_name="Test GTFS Feed for Ref")
        session.add(gtfs_feed)
        session.flush() # Ensure IDs are available for FeedReference

        # Create FeedReference
        feed_reference = FeedReference(gtfs_rt_feed_id=gtfs_rt_feed_id, gtfs_feed_id=related_gtfs_feed_id)
        session.add(feed_reference)
        session.commit()

        # Verify creation
        assert session.get(Gtfsrealtimefeed, gtfs_rt_feed_id) is not None
        assert session.get(Feed, gtfs_rt_feed_id) is not None # Base feed
        assert session.get(EntityTypeFeed, (entity_type_name, gtfs_rt_feed_id)) is not None
        assert session.get(FeedReference, (gtfs_rt_feed_id, related_gtfs_feed_id)) is not None


    # Delete GTFSRealtimeFeed
    with db.start_db_session() as session:
        feed_to_delete = session.get(Gtfsrealtimefeed, gtfs_rt_feed_id)
        session.delete(feed_to_delete)
        session.commit()

    # Verify deletion
    with db.start_db_session() as session:
        assert session.get(Gtfsrealtimefeed, gtfs_rt_feed_id) is None
        assert session.get(Feed, gtfs_rt_feed_id) is None # Base feed should also be deleted
        assert session.get(EntityTypeFeed, (entity_type_name, gtfs_rt_feed_id)) is None
        assert session.get(FeedReference, (gtfs_rt_feed_id, related_gtfs_feed_id)) is None
        assert session.get(Gtfsfeed, related_gtfs_feed_id) is not None # The other feed should still exist
        assert session.get(EntityType, entity_type_name) is not None # EntityType itself should not be deleted


def test_cascade_delete_redirecting_id(test_database):
    db = test_database
    feed_a_id = generate_unique_id()
    feed_b_id = generate_unique_id()

    with db.start_db_session() as session:
        feed_a = Feed(id=feed_a_id, stable_id=feed_a_id, data_type="gtfs", feed_name="Feed A")
        feed_b = Feed(id=feed_b_id, stable_id=feed_b_id, data_type="gtfs", feed_name="Feed B")
        session.add_all([feed_a, feed_b])
        session.flush()

        redirect_ab = Redirectingid(source_id=feed_a_id, target_id=feed_b_id, redirect_comment="A to B")
        session.add(redirect_ab)
        session.commit()

        # Verify creation
        assert session.get(Redirectingid, (feed_a_id, feed_b_id)) is not None

    # Delete Feed A (source)
    with db.start_db_session() as session:
        feed_to_delete = session.get(Feed, feed_a_id)
        session.delete(feed_to_delete)
        session.commit()

    # Verify RedirectingID is deleted
    with db.start_db_session() as session:
        assert session.get(Redirectingid, (feed_a_id, feed_b_id)) is None
        assert session.get(Feed, feed_a_id) is None
        assert session.get(Feed, feed_b_id) is not None # Feed B should still exist

    # Recreate Feed A and a new redirect where Feed B is the source
    feed_a_id_new = generate_unique_id()
    with db.start_db_session() as session:
        feed_a_new = Feed(id=feed_a_id_new, stable_id=feed_a_id_new, data_type="gtfs", feed_name="Feed A New")
        session.add(feed_a_new)
        session.flush()
        redirect_ba = Redirectingid(source_id=feed_b_id, target_id=feed_a_id_new, redirect_comment="B to A New")
        session.add(redirect_ba)
        session.commit()
        assert session.get(Redirectingid, (feed_b_id, feed_a_id_new)) is not None

    # Delete Feed B (source in redirect_ba)
    with db.start_db_session() as session:
        feed_to_delete = session.get(Feed, feed_b_id)
        session.delete(feed_to_delete)
        session.commit()

    # Verify RedirectingID is deleted
    with db.start_db_session() as session:
        assert session.get(Redirectingid, (feed_b_id, feed_a_id_new)) is None
        assert session.get(Feed, feed_b_id) is None
        assert session.get(Feed, feed_a_id_new) is not None # New Feed A should still exist
