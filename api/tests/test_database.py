import pytest
from sqlalchemy.orm import Query
import os

from database.database import Database, generate_unique_id
from database_gen.sqlacodegen_models import Feature, Validationreport, Gtfsdataset
from feeds.impl.datasets_api_impl import DatasetsApiImpl, DATETIME_FORMAT
from feeds.impl.feeds_api_impl import FeedsApiImpl
from faker import Faker


from .test_utils.database import (
    NEW_VALIDATION_VERSION,
    NEW_VALIDATION_TIME,
    VALIDATION_INFO_COUNT_PER_NOTICE,
    VALIDATION_INFO_NOTICES,
    VALIDATION_WARNING_COUNT_PER_NOTICE,
    VALIDATION_WARNING_NOTICES,
    VALIDATION_ERROR_NOTICES,
    VALIDATION_ERROR_COUNT_PER_NOTICE,
    FEATURE_IDS,
)
from sqlalchemy.exc import SQLAlchemyError
from unittest.mock import patch
from .test_utils.database import TEST_GTFS_FEED_STABLE_IDS, TEST_DATASET_STABLE_IDS

BASE_QUERY = Query([Gtfsdataset, Gtfsdataset.bounding_box.ST_AsGeoJSON()]).filter(
    Gtfsdataset.stable_id == TEST_DATASET_STABLE_IDS[0]
)
fake = Faker()


def test_database_singleton(test_database):
    assert test_database is Database()


def test_bounding_box_dateset_exists(test_database):
    assert len(test_database.select(query=BASE_QUERY)) >= 1


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
        for feed in FeedsApiImpl().get_gtfs_feeds(None, None, None, None, None, None, None, None, None, None)
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


def test_validation_report(test_database):
    result = DatasetsApiImpl().get_dataset_gtfs(id=TEST_DATASET_STABLE_IDS[0])
    assert result is not None
    validation_report = result.validation_report
    assert validation_report is not None
    assert validation_report.validator_version == NEW_VALIDATION_VERSION
    assert validation_report.validated_at == NEW_VALIDATION_TIME.strftime(DATETIME_FORMAT)
    assert validation_report.total_info == VALIDATION_INFO_COUNT_PER_NOTICE * VALIDATION_INFO_NOTICES
    assert validation_report.total_warning == VALIDATION_WARNING_COUNT_PER_NOTICE * VALIDATION_WARNING_NOTICES
    assert validation_report.total_error == VALIDATION_ERROR_COUNT_PER_NOTICE * VALIDATION_ERROR_NOTICES


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
    db.merge(new_feature, auto_commit=True)
    retrieved_features = db.select(Feature, conditions=[Feature.name == feature_name])
    assert len(retrieved_features) == 1
    assert retrieved_features[0][0].name == feature_name

    # Ensure no active session exists
    if db.session:
        db.close_session()

    results_after_session_closed = db.select_from_active_session(Feature)
    assert len(results_after_session_closed) == 0


def test_select_from_active_session_success():
    db = Database()

    feature_name = fake.name()
    new_feature = Feature(name=feature_name)
    db.session.add(new_feature)

    # The active session should have one instance of the feature
    conditions = [Feature.name == feature_name]
    selected_features = db.select_from_active_session(Feature, conditions=conditions, attributes=["name"])
    all_features = db.select(Feature)
    assert len(all_features) >= 1
    assert len(selected_features) == 1
    assert selected_features[0]["name"] == feature_name

    db.session.rollback()

    # The database should have no instance of the feature
    retrieved_features = db.select(Feature, conditions=[Feature.name == feature_name])
    assert len(retrieved_features) == 0


def test_merge_relationship_w_uncommitted_changed():
    db = None
    try:
        db = Database()
        db.start_session()

        # Create and add a new Feature object (parent) to the session
        feature_name = fake.name()
        new_feature = Feature(name=feature_name)
        db.merge(new_feature)

        # Create a new Validationreport object (child)
        validation_id = fake.uuid4()
        new_validation = Validationreport(id=validation_id)

        # Merge this Validationreport into the FeatureValidationreport relationship
        db.merge_relationship(
            parent_model=Feature,
            parent_key_values={"name": feature_name},
            child=new_validation,
            relationship_name="validations",
            auto_commit=False,
            uncommitted=True,
        )

        # Retrieve the feature and check if the ValidationReport was added
        retrieved_feature = db.select_from_active_session(Feature, conditions=[Feature.name == feature_name])[0]
        validation_ids = [validation.id for validation in retrieved_feature.validations]
        assert validation_id in validation_ids
    except Exception as e:
        raise e
    finally:
        if db is not None:
            # Clean up
            db.session.rollback()


def test_merge_with_update_session():
    db = Database()
    feature_name = "TestFeature"
    new_feature = Feature(name=feature_name)

    with patch.object(db.session, "merge", side_effect=SQLAlchemyError("Mocked merge failure")):
        result = db.merge(new_feature, update_session=True, auto_commit=False, load=True)
        assert result is False, "Expected merge to fail and return False"


if __name__ == "__main__":
    os.environ["SHOULD_CLOSE_DB_SESSION"] = "true"
    pytest.main()
