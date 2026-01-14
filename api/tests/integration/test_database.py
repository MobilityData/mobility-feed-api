from datetime import datetime, timezone
from typing import Final

import pytest
from faker import Faker
from sqlalchemy.orm import Query

from feeds.impl.datasets_api_impl import DatasetsApiImpl
from feeds.impl.feeds_api_impl import FeedsApiImpl
from shared.common.db_utils import apply_bounding_filtering, normalize_url_str
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


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Trim whitespace and surrounding quotes; remove scheme, www, query params and fragment; lowercase host
        ("  'https://www.Example.com/path/page?query=1#section'  ", "example.com/path/page"),
        # Remove BOM characters and query
        ("\ufeffhttps://example.com/license?x=1", "example.com/license"),
        # Strip fragment
        ("http://example.com/path#frag", "example.com/path"),
        # Strip query
        ("https://example.com/path?param=value", "example.com/path"),
        # Remove trailing slashes
        ("https://www.example.com/path///", "example.com/path"),
        # Host only with scheme and www; trailing slash removed; host lowercased
        ("http://www.EXAMPLE.com/", "example.com"),
        # Path case preserved (only host lowercased)
        ("https://Example.com/Case/Sensitive", "example.com/case/sensitive"),
        # None becomes empty string
        (None, ""),
        # Blank / whitespace-only becomes empty string
        ("   ", ""),
        # Quotes without scheme
        ('"Example.com/path"', "example.com/path"),
    ],
)
def test_normalize_url_str(raw, expected):
    """Test normalize_url_str utility for all documented normalization steps.
    Steps verified:
    - Trim whitespace and quotes
    - Remove BOM characters
    - Strip fragments and query parameters
    - Remove scheme (http/https) and www prefix
    - Lowercase the host (only host)
    - Remove trailing slashes
    - Preserve path case
    - Handle None / empty inputs
    """
    assert normalize_url_str(raw) == expected
