import pytest
from sqlalchemy.orm import Query

from database.database import Database
from database_gen.sqlacodegen_models import Gtfsdataset
from feeds.impl.datasets_api_impl import DatasetsApiImpl
from feeds.impl.feeds_api_impl import FeedsApiImpl
from .test_utils.database import TEST_GTFS_FEED_STABLE_IDS, TEST_DATASET_STABLE_IDS, TEST_EXTERNAL_IDS

BASE_QUERY = Query([Gtfsdataset, Gtfsdataset.bounding_box.ST_AsGeoJSON()]).filter(
    Gtfsdataset.stable_id == TEST_DATASET_STABLE_IDS[0]
)


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
        ("37.7, 38", "-84.7,-84.6", "completely_enclosed", True),
        ("37, 38", "-84.7,-84.6", "completely_enclosed", False),  # min latitude is too low
        ("37.7, 39", "-84.7,-84.6", "completely_enclosed", False),  # max latitude is too high
        ("37.7, 38", "-85,-84.6", "completely_enclosed", False),  # min longitude is too low
        ("37.7, 38", "-84.7,-83", "completely_enclosed", False),  # max longitude is too high
    ],
)
def test_bounding_box_completed_closed(latitudes, longitudes, method, expected_found, test_database):
    assert_bounding_box_found(latitudes, longitudes, method, expected_found, test_database)


@pytest.mark.parametrize(
    "latitudes,longitudes,method,expected_found",
    [
        # completely enclosed, still considered as partially enclosed
        ("37.7, 38", "-84.7,-84.6", "partially_enclosed", True),
        ("37, 38", "-84.7,-84.6", "partially_enclosed", True),  # min latitude is too low
        ("37.7, 39", "-84.7,-84.6", "partially_enclosed", True),  # max latitude is too high
        ("37.7, 38", "-85,-84.6", "partially_enclosed", True),  # min longitude is too low
        ("37.7, 38", "-84.7,-83", "partially_enclosed", True),  # max longitude is too high
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
        for feed in FeedsApiImpl().get_gtfs_feeds(None, None, None, None, None, None, None, None, None, None, None, None)
        if feed.id in TEST_GTFS_FEED_STABLE_IDS
    }
    assert len(results) == len(TEST_GTFS_FEED_STABLE_IDS)
    feed_1 = results.get(TEST_GTFS_FEED_STABLE_IDS[0])
    feed_2 = results.get(TEST_GTFS_FEED_STABLE_IDS[1])

    assert feed_1 is not None
    assert sorted([external_id.external_id for external_id in feed_1.external_ids]) == TEST_EXTERNAL_IDS[:2]
    assert sorted([external_id.source for external_id in feed_1.external_ids]) == ["source1", "source2"]

    assert feed_1.latest_dataset.id == TEST_DATASET_STABLE_IDS[1]
    assert sorted([redirect for redirect in feed_1.redirects]) == [TEST_GTFS_FEED_STABLE_IDS[1]]

    assert feed_2 is not None
    assert sorted([external_id.external_id for external_id in feed_2.external_ids]) == TEST_EXTERNAL_IDS[2:]
    assert sorted([external_id.source for external_id in feed_2.external_ids]) == ["source3", "source4"]

    assert feed_2.latest_dataset.id == TEST_DATASET_STABLE_IDS[3]
    assert sorted([redirect for redirect in feed_2.redirects]) == [
        TEST_GTFS_FEED_STABLE_IDS[2],
        TEST_GTFS_FEED_STABLE_IDS[3],
    ]
