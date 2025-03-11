import os
import unittest
import pytest
from unittest.mock import patch, MagicMock

from faker import Faker

from shared.database_gen.sqlacodegen_models import Gtfsfeed, Location, Gtfsdataset
from test_shared.test_utils.database_utils import (
    default_db_url,
    clean_testing_db,
    get_testing_session,
)

faker = Faker()


class TestReverseGeolocationBatch(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "FEEDS_DATABASE_URL": default_db_url,
        },
    )
    def test_get_feed_data(self):
        from reverse_geolocation_batch import get_feeds_data

        clean_testing_db()
        session = get_testing_session()
        gtfs_dataset_1 = Gtfsdataset(
            id="test_dataset_latest",
            stable_id="test_dataset_latest",
            latest=True,
            hosted_url="test_url",
        )
        gtfs_dataset_2 = Gtfsdataset(
            id="test_dataset",
            stable_id="test_dataset",
            latest=False,
            hosted_url="test_url",
        )
        gtfs_dataset_3 = Gtfsdataset(
            id="test_dataset_3",
            stable_id="test_dataset_3",
            latest=True,
            hosted_url="test_url",
        )
        feed = Gtfsfeed(
            id="test_feed",
            stable_id="test_feed",
            status="active",
            gtfsdatasets=[gtfs_dataset_2, gtfs_dataset_1],
            locations=[Location(country_code="CA", id="CA")],
        )
        feed_2 = Gtfsfeed(
            id="test_feed_2",
            stable_id="test_feed_2",
            status="active",
            gtfsdatasets=[gtfs_dataset_3],
            locations=[Location(country_code="US", id="US")],
        )
        session.add(feed)
        session.add(feed_2)
        session.commit()

        results = get_feeds_data(["CA"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["stable_id"], "test_feed")
        self.assertEqual(results[0]["dataset_id"], "test_dataset_latest")
        self.assertEqual(results[0]["url"], "test_url")

        results_2 = get_feeds_data([])
        self.assertEqual(len(results_2), 2)

        results_3 = get_feeds_data(["US"])
        self.assertEqual(len(results_3), 1)
        self.assertEqual(results_3[0]["stable_id"], "test_feed_2")
        self.assertEqual(results_3[0]["dataset_id"], "test_dataset_3")
        self.assertEqual(results_3[0]["url"], "test_url")

        clean_testing_db()

    def test_parse_request_parameters(self):
        request = MagicMock()
        request.args.get = lambda value, default: {"country_codes": "Ca , uS"}.get(
            value, default
        )
        from reverse_geolocation_batch import parse_request_parameters

        country_codes = parse_request_parameters(request)
        self.assertEqual(country_codes, ["CA", "US"])

        with pytest.raises(ValueError):
            request.args.get = lambda value, default: {
                "country_codes": "CA , US, XX"
            }.get(value, default)
            parse_request_parameters(request)

    @patch("reverse_geolocation_batch.publish_messages")
    @patch("reverse_geolocation_batch.get_feeds_data")
    @patch("reverse_geolocation_batch.parse_request_parameters")
    @patch.dict(
        os.environ,
        {
            "DEBUG": "True",
        },
    )
    def test_reverse_geolocation_batch(self, mock_parse_request, mock_get_feeds, _):
        from reverse_geolocation_batch import reverse_geolocation_batch

        request = MagicMock()
        mock_parse_request.return_value = ["CA", "US"]
        mock_get_feeds.return_value = [
            {"stable_id": "test_feed", "dataset_id": "test_dataset", "url": "test_url"},
            {
                "stable_id": "test_feed_2",
                "dataset_id": "test_dataset_2",
                "url": "test_url_2",
            },
        ]
        response = reverse_geolocation_batch(request)
        self.assertEqual(response, ("Batch function triggered for 2 feeds.", 200))
