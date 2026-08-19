import datetime
import unittest
from unittest.mock import MagicMock, patch

from faker import Faker

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Feedinfo,
    Gtfsdataset,
    Gtfsfeed,
    Gtfsfile,
)
from test_shared.test_utils.database_utils import clean_testing_db, default_db_url

faker = Faker()


def make_request(payload):
    request = MagicMock()
    request.get_json.return_value = payload
    return request


class TestParseRequestParameters(unittest.TestCase):
    def test_valid(self):
        from processor import parse_request_parameters

        payload = {
            "stable_id": "feed",
            "dataset_id": "dataset",
            "file_name": "feed_info.txt",
            "file_url": "http://example.com/feed_info.txt",
        }
        self.assertEqual(
            parse_request_parameters(make_request(payload)),
            ("feed", "dataset", "feed_info.txt", "http://example.com/feed_info.txt"),
        )

    def test_missing_parameters(self):
        from processor import parse_request_parameters

        with self.assertRaises(ValueError):
            parse_request_parameters(make_request({"stable_id": "feed"}))

    def test_no_body(self):
        from processor import parse_request_parameters

        with self.assertRaises(ValueError):
            parse_request_parameters(make_request(None))


class TestProcessFileData(unittest.TestCase):
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
        return dataset_id

    def _create_dataset_with_file(
        self, db_session, feed=None, file_hash="h1", downloaded_at=None
    ):
        """Create a dataset owning a feed_info.txt file with the given hash."""
        if feed is None:
            feed = Gtfsfeed(
                id=faker.uuid4(cast_to=str),
                data_type="gtfs",
                stable_id=faker.uuid4(cast_to=str),
            )
        dataset_id = faker.uuid4(cast_to=str)
        dataset = Gtfsdataset(
            id=dataset_id,
            stable_id=dataset_id,
            feed=feed,
            downloaded_at=downloaded_at or datetime.datetime.now(datetime.timezone.utc),
        )
        dataset.gtfsfiles = [
            Gtfsfile(
                id=faker.uuid4(cast_to=str),
                file_name="feed_info.txt",
                file_size_bytes=100,
                hash=file_hash,
                hosted_url="http://example.com/feed_info.txt",
            )
        ]
        db_session.add(dataset)
        db_session.commit()
        return dataset

    def _payload(self, dataset_stable_id):
        return {
            "stable_id": "feed",
            "dataset_id": dataset_stable_id,
            "file_name": "feed_info.txt",
            "file_url": "http://example.com/feed_info.txt",
        }

    @with_db_session(db_url=default_db_url)
    @patch("processor.requests")
    def test_process_success_writes_feedinfo(self, requests_mock, db_session):
        dataset = self._create_dataset_with_file(db_session)
        csv = (
            "feed_publisher_name,feed_start_date,feed_end_date\n"
            "Agency,20240101,20241231\n"
        )
        requests_mock.get.return_value.content = csv.encode("utf-8")

        from processor import process_file_data

        _, status = process_file_data(
            make_request(self._payload(dataset.stable_id)), db_session=db_session
        )
        self.assertEqual(status, 200)

        feed_info = dataset.feed_info
        self.assertIsNotNone(feed_info)
        self.assertEqual(feed_info.feed_publisher_name, "Agency")
        self.assertEqual(feed_info.feed_start_date, datetime.date(2024, 1, 1))
        self.assertEqual(feed_info.feed_end_date, datetime.date(2024, 12, 31))

    @with_db_session(db_url=default_db_url)
    @patch("processor.requests")
    def test_process_unregistered_file_skips(self, requests_mock, db_session):
        from processor import process_file_data

        payload = {
            "stable_id": "feed",
            "dataset_id": "dataset",
            "file_name": "stops.txt",
            "file_url": "http://example.com/stops.txt",
        }
        message, status = process_file_data(
            make_request(payload), db_session=db_session
        )
        self.assertEqual(status, 200)
        self.assertIn("No extractor", message)
        requests_mock.get.assert_not_called()

    @with_db_session(db_url=default_db_url)
    def test_process_invalid_payload_does_not_trigger_retry(self, db_session):
        from processor import process_file_data

        # Failures return 200 so Cloud Tasks does not retry them.
        message, status = process_file_data(make_request({}), db_session=db_session)
        self.assertEqual(status, 200)
        self.assertIn("Missing or invalid JSON body", message)

        message, status = process_file_data(
            make_request({"stable_id": "feed"}), db_session=db_session
        )
        self.assertEqual(status, 200)
        self.assertIn("Missing required parameters", message)

    @with_db_session(db_url=default_db_url)
    @patch("processor.requests")
    def test_process_missing_dataset_does_not_trigger_retry(
        self, requests_mock, db_session
    ):
        requests_mock.get.return_value.content = b"feed_publisher_name\nAgency\n"

        from processor import process_file_data

        message, status = process_file_data(
            make_request(self._payload("does-not-exist")), db_session=db_session
        )
        self.assertEqual(status, 200)
        self.assertIn("does not exist", message)

    @with_db_session(db_url=default_db_url)
    @patch("processor.requests")
    def test_process_download_failure_does_not_trigger_retry(
        self, requests_mock, db_session
    ):
        requests_mock.get.side_effect = Exception("connection reset")
        dataset_id = self._create_dataset(db_session)

        from processor import process_file_data

        message, status = process_file_data(
            make_request(self._payload(dataset_id)), db_session=db_session
        )
        self.assertEqual(status, 200)
        self.assertIn("connection reset", message)

    @with_db_session(db_url=default_db_url)
    @patch("processor.requests")
    def test_process_links_to_existing_data(self, requests_mock, db_session):
        """Unchanged file, already extracted -> link to the same row, no download."""
        source = self._create_dataset_with_file(db_session)
        target = self._create_dataset_with_file(db_session, feed=source.feed)
        feed_info = Feedinfo(file_hash="h1", feed_publisher_name="Agency")
        source.feed_info = feed_info
        db_session.commit()

        from processor import process_file_data

        message, status = process_file_data(
            make_request(self._payload(target.stable_id)), db_session=db_session
        )
        self.assertEqual(status, 200)
        self.assertIn("Linked", message)
        requests_mock.get.assert_not_called()

        # One shared entity, referenced by both datasets.
        self.assertEqual(db_session.query(Feedinfo).count(), 1)
        self.assertEqual(target.feed_info_id, source.feed_info_id)
        self.assertEqual(target.feed_info.feed_publisher_name, "Agency")

    @with_db_session(db_url=default_db_url)
    @patch("processor.requests")
    def test_process_extracts_when_unchanged_but_never_extracted(
        self, requests_mock, db_session
    ):
        """Unchanged file that was never extracted -> download and extract."""
        source = self._create_dataset_with_file(db_session)
        target = self._create_dataset_with_file(db_session, feed=source.feed)
        requests_mock.get.return_value.content = b"feed_publisher_name\nAgency\n"

        from processor import process_file_data

        message, status = process_file_data(
            make_request(self._payload(target.stable_id)), db_session=db_session
        )
        self.assertEqual(status, 200)
        self.assertIn("Successfully extracted", message)
        requests_mock.get.assert_called_once()
        self.assertEqual(target.feed_info.feed_publisher_name, "Agency")
        self.assertEqual(target.feed_info.file_hash, "h1")

    @with_db_session(db_url=default_db_url)
    @patch("processor.requests")
    def test_process_extracts_when_hash_differs(self, requests_mock, db_session):
        """A different hash is different content: extract into its own row."""
        source = self._create_dataset_with_file(db_session, file_hash="h1")
        target = self._create_dataset_with_file(
            db_session, feed=source.feed, file_hash="h2"
        )
        source.feed_info = Feedinfo(file_hash="h1", feed_publisher_name="Old")
        db_session.commit()
        requests_mock.get.return_value.content = b"feed_publisher_name\nNew\n"

        from processor import process_file_data

        _, status = process_file_data(
            make_request(self._payload(target.stable_id)), db_session=db_session
        )
        self.assertEqual(status, 200)
        requests_mock.get.assert_called_once()
        self.assertEqual(db_session.query(Feedinfo).count(), 2)
        self.assertEqual(target.feed_info.feed_publisher_name, "New")
        self.assertEqual(source.feed_info.feed_publisher_name, "Old")

    @with_db_session(db_url=default_db_url)
    @patch("processor.requests")
    def test_process_skips_when_already_extracted(self, requests_mock, db_session):
        dataset = self._create_dataset_with_file(db_session)
        dataset.feed_info = Feedinfo(file_hash="h1", feed_publisher_name="Agency")
        db_session.commit()

        from processor import process_file_data

        message, status = process_file_data(
            make_request(self._payload(dataset.stable_id)), db_session=db_session
        )
        self.assertEqual(status, 200)
        self.assertIn("already extracted", message)
        requests_mock.get.assert_not_called()

    @with_db_session(db_url=default_db_url)
    @patch("processor.requests")
    def test_process_without_file_hash_does_not_trigger_retry(
        self, requests_mock, db_session
    ):
        """Without a hash the data cannot be shared, so this fails loudly - once."""
        dataset = self._create_dataset_with_file(db_session, file_hash=None)
        requests_mock.get.return_value.content = b"feed_publisher_name\nAgency\n"

        from processor import process_file_data

        message, status = process_file_data(
            make_request(self._payload(dataset.stable_id)), db_session=db_session
        )
        self.assertEqual(status, 200)
        self.assertIn("content hash", message)
        self.assertEqual(db_session.query(Feedinfo).count(), 0)


if __name__ == "__main__":
    unittest.main()
