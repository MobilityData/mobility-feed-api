import pytest
from sqlalchemy.orm import Query
import os

from database.database import Database, generate_unique_id
from database_gen.sqlacodegen_models import Gtfsdataset, Component
from feeds.impl.datasets_api_impl import DatasetsApiImpl
from feeds.impl.feeds_api_impl import FeedsApiImpl
from faker import Faker
from .test_utils.database import TEST_GTFS_FEED_STABLE_IDS, TEST_DATASET_STABLE_IDS

BASE_QUERY = Query([Gtfsdataset, Gtfsdataset.bounding_box.ST_AsGeoJSON()]).filter(
    Gtfsdataset.stable_id == TEST_DATASET_STABLE_IDS[0]
)
fake = Faker()


def test_database_singleton(test_database):
    assert test_database is Database()


def test_bounding_box_dateset_exists(test_database):
    assert len(test_database.select(query=BASE_QUERY)) == 1


def assert_bounding_box_found(latitudes, longitudes, method, expected_found, test_database):
    query = DatasetsApiImpl.apply_bounding_filtering(BASE_QUERY, latitudes, longitudes, method)
    result = test_database.select(query=query)
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
    results = {
        feed.id: feed
        for feed in FeedsApiImpl().get_gtfs_feeds(
            None, None, None, None, None, None, None, None, None, None, None, None
        )
        if feed.id in TEST_GTFS_FEED_STABLE_IDS
    }
    assert len(results) == len(TEST_GTFS_FEED_STABLE_IDS)
    feed_1 = results.get(TEST_GTFS_FEED_STABLE_IDS[0])
    feed_2 = results.get(TEST_GTFS_FEED_STABLE_IDS[1])

    assert feed_1 is not None

    assert feed_1.latest_dataset.id == TEST_DATASET_STABLE_IDS[1]
    assert sorted([redirect.target_id for redirect in feed_1.redirects]) == [TEST_GTFS_FEED_STABLE_IDS[1]]

    assert feed_2 is not None

    assert feed_2.latest_dataset.id == TEST_DATASET_STABLE_IDS[3]
    assert sorted([redirect.target_id for redirect in feed_2.redirects]) == [
        TEST_GTFS_FEED_STABLE_IDS[2],
        TEST_GTFS_FEED_STABLE_IDS[3],
    ]


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
    component_name = fake.name()
    new_component = Component(name=component_name)
    db.merge(new_component, auto_commit=True)
    retrieved_components = db.select(Component, conditions=[Component.name == component_name])
    assert len(retrieved_components) == 1
    assert retrieved_components[0][0].name == component_name

    # Ensure no active session exists
    if db.session:
        db.close_session()

    results_after_session_closed = db.select_from_active_session(Component)
    assert len(results_after_session_closed) == 0


def test_select_from_active_session_success():
    db = Database()

    component_name = fake.name()
    new_component = Component(name=component_name)
    db.session.add(new_component)

    # The active session should have one instance of the component
    conditions = [Component.name == component_name]
    selected_components = db.select_from_active_session(Component, conditions=conditions, attributes=["name"])
    all_components = db.select(Component)
    assert len(all_components) >= 1
    assert len(selected_components) == 1
    assert selected_components[0]["name"] == component_name

    db.session.rollback()

    # The database should have no instance of the component
    retrieved_components = db.select(Component, conditions=[Component.name == component_name])
    assert len(retrieved_components) == 0


def test_merge_relationship_w_uncommitted_changed():
    db = None
    try:
        db = Database()
        db.start_session()

        # Create and add a new Component object (parent) to the session
        component_name = fake.name()
        new_component = Component(name=component_name)
        db.merge(new_component)

        # Create a new GtfsDataset object (child)
        gtfs_dataset_id = fake.uuid4()
        new_gtfs_dataset = Gtfsdataset(id=gtfs_dataset_id)

        # Merge this GtfsDataset into the Component's datasets relationship
        db.merge_relationship(
            parent_model=Component,
            parent_key_values={"name": component_name},
            child=new_gtfs_dataset,
            relationship_name="datasets",
            auto_commit=False,
            uncommitted=True,
        )

        # Retrieve the component and check if the GtfsDataset was added
        retrieved_component = db.select_from_active_session(Component, conditions=[Component.name == component_name])[0]
        dataset_ids = [dataset.id for dataset in retrieved_component.datasets]
        assert gtfs_dataset_id in dataset_ids
    except Exception as e:
        raise e
    finally:
        if db is not None:
            # Clean up
            db.session.rollback()


if __name__ == "__main__":
    os.environ["SHOULD_CLOSE_DB_SESSION"] = "true"
    pytest.main()
    os.environ["SHOULD_CLOSE_DB_SESSION"] = "false"
