import datetime
import unittest

import pandas as pd
from faker import Faker

from extractors.feed_info_extractor import (
    FeedInfoExtractor,
    clean_str,
    parse_gtfs_date,
)
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Feedinfo, Gtfsdataset, Gtfsfeed
from test_shared.test_utils.database_utils import clean_testing_db, default_db_url

faker = Faker()


class TestParsingHelpers(unittest.TestCase):
    def test_clean_str(self):
        self.assertIsNone(clean_str(None))
        self.assertIsNone(clean_str(float("nan")))
        self.assertIsNone(clean_str("   "))
        self.assertEqual(clean_str("  Agency  "), "Agency")
        self.assertEqual(clean_str(123), "123")

    def test_parse_gtfs_date_valid(self):
        self.assertEqual(parse_gtfs_date("20240115"), datetime.date(2024, 1, 15))

    def test_parse_gtfs_date_numeric(self):
        # pandas may read a purely numeric column as int or float
        self.assertEqual(parse_gtfs_date("20240115.0"), datetime.date(2024, 1, 15))
        self.assertEqual(parse_gtfs_date(20240115), datetime.date(2024, 1, 15))

    def test_parse_gtfs_date_missing_or_invalid(self):
        self.assertIsNone(parse_gtfs_date(None))
        self.assertIsNone(parse_gtfs_date(""))
        self.assertIsNone(parse_gtfs_date("not-a-date"))


class TestFeedInfoExtractor(unittest.TestCase):
    def setUp(self):
        clean_testing_db()

    def _create_dataset(self, db_session):
        feed = Gtfsfeed(
            id=faker.uuid4(cast_to=str),
            data_type="gtfs",
            stable_id=faker.uuid4(cast_to=str),
        )
        dataset_id = faker.uuid4(cast_to=str)
        dataset = Gtfsdataset(id=dataset_id, stable_id=dataset_id, feed=feed)
        db_session.add(dataset)
        db_session.commit()
        return dataset

    @with_db_session(db_url=default_db_url)
    def test_extract_inserts_feedinfo(self, db_session):
        dataset = self._create_dataset(db_session)
        df = pd.DataFrame(
            [
                {
                    "feed_publisher_name": "Test Agency",
                    "feed_publisher_url": "https://example.com",
                    "feed_lang": "en",
                    "default_lang": "fr",
                    "feed_start_date": "20240101",
                    "feed_end_date": "20241231",
                    "feed_version": "v1",
                    "feed_contact_email": "info@example.com",
                    "feed_contact_url": "https://example.com/contact",
                }
            ]
        )
        FeedInfoExtractor().extract(df, dataset, db_session)
        db_session.commit()

        feed_info = (
            db_session.query(Feedinfo)
            .filter(Feedinfo.gtfs_dataset_id == dataset.id)
            .one()
        )
        self.assertEqual(feed_info.feed_publisher_name, "Test Agency")
        self.assertEqual(feed_info.feed_publisher_url, "https://example.com")
        self.assertEqual(feed_info.feed_lang, "en")
        self.assertEqual(feed_info.default_lang, "fr")
        self.assertEqual(feed_info.feed_start_date, datetime.date(2024, 1, 1))
        self.assertEqual(feed_info.feed_end_date, datetime.date(2024, 12, 31))
        self.assertEqual(feed_info.feed_version, "v1")
        self.assertEqual(feed_info.feed_contact_email, "info@example.com")
        self.assertEqual(feed_info.feed_contact_url, "https://example.com/contact")

    @with_db_session(db_url=default_db_url)
    def test_extract_upserts_existing(self, db_session):
        dataset = self._create_dataset(db_session)
        FeedInfoExtractor().extract(
            pd.DataFrame(
                [{"feed_publisher_name": "First", "feed_start_date": "20240101"}]
            ),
            dataset,
            db_session,
        )
        db_session.commit()

        FeedInfoExtractor().extract(
            pd.DataFrame(
                [{"feed_publisher_name": "Second", "feed_start_date": "20250101"}]
            ),
            dataset,
            db_session,
        )
        db_session.commit()

        rows = (
            db_session.query(Feedinfo)
            .filter(Feedinfo.gtfs_dataset_id == dataset.id)
            .all()
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].feed_publisher_name, "Second")
        self.assertEqual(rows[0].feed_start_date, datetime.date(2025, 1, 1))

    @with_db_session(db_url=default_db_url)
    def test_extract_missing_optional_columns(self, db_session):
        dataset = self._create_dataset(db_session)
        FeedInfoExtractor().extract(
            pd.DataFrame([{"feed_publisher_name": "Only Name"}]),
            dataset,
            db_session,
        )
        db_session.commit()

        feed_info = (
            db_session.query(Feedinfo)
            .filter(Feedinfo.gtfs_dataset_id == dataset.id)
            .one()
        )
        self.assertEqual(feed_info.feed_publisher_name, "Only Name")
        self.assertIsNone(feed_info.feed_start_date)
        self.assertIsNone(feed_info.feed_lang)

    @with_db_session(db_url=default_db_url)
    def test_extract_empty_dataframe_is_noop(self, db_session):
        dataset = self._create_dataset(db_session)
        FeedInfoExtractor().extract(pd.DataFrame(), dataset, db_session)
        db_session.commit()

        count = (
            db_session.query(Feedinfo)
            .filter(Feedinfo.gtfs_dataset_id == dataset.id)
            .count()
        )
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
