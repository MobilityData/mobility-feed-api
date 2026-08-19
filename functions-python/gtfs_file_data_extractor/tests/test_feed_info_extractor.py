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
        FeedInfoExtractor().extract(df, dataset, "hash-1", db_session)
        db_session.commit()

        feed_info = dataset.feed_info
        self.assertIsNotNone(feed_info)
        self.assertEqual(feed_info.file_hash, "hash-1")
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
    def test_extract_upserts_by_hash(self, db_session):
        """Re-parsing the same content updates the shared row in place."""
        dataset = self._create_dataset(db_session)
        FeedInfoExtractor().extract(
            pd.DataFrame(
                [{"feed_publisher_name": "First", "feed_start_date": "20240101"}]
            ),
            dataset,
            "hash-1",
            db_session,
        )
        db_session.commit()

        FeedInfoExtractor().extract(
            pd.DataFrame(
                [{"feed_publisher_name": "Second", "feed_start_date": "20250101"}]
            ),
            dataset,
            "hash-1",
            db_session,
        )
        db_session.commit()

        rows = db_session.query(Feedinfo).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].feed_publisher_name, "Second")
        self.assertEqual(rows[0].feed_start_date, datetime.date(2025, 1, 1))
        self.assertEqual(dataset.feed_info_id, rows[0].id)

    @with_db_session(db_url=default_db_url)
    def test_extract_different_hash_creates_second_row(self, db_session):
        extractor = FeedInfoExtractor()
        first = self._create_dataset(db_session)
        second = self._create_dataset(db_session)
        extractor.extract(
            pd.DataFrame([{"feed_publisher_name": "First"}]),
            first,
            "hash-1",
            db_session,
        )
        extractor.extract(
            pd.DataFrame([{"feed_publisher_name": "Second"}]),
            second,
            "hash-2",
            db_session,
        )
        db_session.commit()

        self.assertEqual(db_session.query(Feedinfo).count(), 2)
        self.assertNotEqual(first.feed_info_id, second.feed_info_id)

    @with_db_session(db_url=default_db_url)
    def test_extract_missing_optional_columns(self, db_session):
        dataset = self._create_dataset(db_session)
        FeedInfoExtractor().extract(
            pd.DataFrame([{"feed_publisher_name": "Only Name"}]),
            dataset,
            "hash-1",
            db_session,
        )
        db_session.commit()

        self.assertEqual(dataset.feed_info.feed_publisher_name, "Only Name")
        self.assertIsNone(dataset.feed_info.feed_start_date)
        self.assertIsNone(dataset.feed_info.feed_lang)

    @with_db_session(db_url=default_db_url)
    def test_extract_empty_dataframe_is_noop(self, db_session):
        dataset = self._create_dataset(db_session)
        FeedInfoExtractor().extract(pd.DataFrame(), dataset, "hash-1", db_session)
        db_session.commit()

        self.assertEqual(db_session.query(Feedinfo).count(), 0)
        self.assertIsNone(dataset.feed_info_id)

    @with_db_session(db_url=default_db_url)
    def test_extract_without_hash_raises(self, db_session):
        dataset = self._create_dataset(db_session)
        with self.assertRaises(ValueError):
            FeedInfoExtractor().extract(
                pd.DataFrame([{"feed_publisher_name": "Agency"}]),
                dataset,
                None,
                db_session,
            )

    @with_db_session(db_url=default_db_url)
    def test_has_data(self, db_session):
        dataset = self._create_dataset(db_session)
        extractor = FeedInfoExtractor()
        self.assertFalse(extractor.has_data(dataset, db_session))

        extractor.extract(
            pd.DataFrame([{"feed_publisher_name": "Agency"}]),
            dataset,
            "hash-1",
            db_session,
        )
        db_session.commit()
        self.assertTrue(extractor.has_data(dataset, db_session))

    @with_db_session(db_url=default_db_url)
    def test_link_existing_data_shares_one_row(self, db_session):
        extractor = FeedInfoExtractor()
        source = self._create_dataset(db_session)
        target = self._create_dataset(db_session)
        extractor.extract(
            pd.DataFrame(
                [
                    {
                        "feed_publisher_name": "Agency",
                        "feed_lang": "en",
                        "feed_start_date": "20240101",
                    }
                ]
            ),
            source,
            "hash-1",
            db_session,
        )
        db_session.commit()

        self.assertTrue(extractor.link_existing_data(target, "hash-1", db_session))
        db_session.commit()

        # No duplicate entity: both datasets reference the same feedinfo row.
        self.assertEqual(db_session.query(Feedinfo).count(), 1)
        self.assertEqual(target.feed_info_id, source.feed_info_id)
        self.assertEqual(target.feed_info.feed_publisher_name, "Agency")
        self.assertCountEqual(
            [d.id for d in source.feed_info.gtfsdatasets], [source.id, target.id]
        )

    @with_db_session(db_url=default_db_url)
    def test_link_existing_data_without_match(self, db_session):
        extractor = FeedInfoExtractor()
        dataset = self._create_dataset(db_session)
        self.assertFalse(extractor.link_existing_data(dataset, "unknown", db_session))
        # An unknown hash cannot be matched either.
        self.assertFalse(extractor.link_existing_data(dataset, None, db_session))
        self.assertIsNone(dataset.feed_info_id)


if __name__ == "__main__":
    unittest.main()
