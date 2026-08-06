import datetime
import unittest
from unittest.mock import MagicMock, patch

from faker import Faker

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Feedinfo, Gtfsdataset, Gtfsfeed
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

    @with_db_session(db_url=default_db_url)
    @patch("processor.requests")
    def test_process_success_writes_feedinfo(self, requests_mock, db_session):
        dataset_id = self._create_dataset(db_session)
        csv = (
            "feed_publisher_name,feed_start_date,feed_end_date\n"
            "Agency,20240101,20241231\n"
        )
        requests_mock.get.return_value.content = csv.encode("utf-8")

        from processor import process_file_data

        payload = {
            "stable_id": "feed",
            "dataset_id": dataset_id,
            "file_name": "feed_info.txt",
            "file_url": "http://example.com/feed_info.txt",
        }
        _, status = process_file_data(make_request(payload), db_session=db_session)
        self.assertEqual(status, 200)

        feed_info = (
            db_session.query(Feedinfo)
            .filter(Feedinfo.gtfs_dataset_id == dataset_id)
            .one()
        )
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
    def test_process_invalid_payload_returns_400(self, db_session):
        from processor import process_file_data

        _, status = process_file_data(make_request({}), db_session=db_session)
        self.assertEqual(status, 400)

    @with_db_session(db_url=default_db_url)
    @patch("processor.requests")
    def test_process_missing_dataset_returns_500(self, requests_mock, db_session):
        requests_mock.get.return_value.content = b"feed_publisher_name\nAgency\n"

        from processor import process_file_data

        payload = {
            "stable_id": "feed",
            "dataset_id": "does-not-exist",
            "file_name": "feed_info.txt",
            "file_url": "http://example.com/feed_info.txt",
        }
        _, status = process_file_data(make_request(payload), db_session=db_session)
        self.assertEqual(status, 500)


if __name__ == "__main__":
    unittest.main()
