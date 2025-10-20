import unittest
from unittest import mock
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from faker import Faker

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Feature,
    Gtfsdataset,
    Gtfsfeed,
    Validationreport,
)

from test_shared.test_utils.database_utils import default_db_url
from main import compute_validation_report_counters
from main import (
    read_json_report,
    get_feature,
    get_dataset,
    create_validation_report_entities,
    process_validation_report,
    populate_service_date,
)

faker = Faker()


class TestValidationReportProcessor(unittest.TestCase):
    @mock.patch("requests.get")
    def test_read_json_report_success(self, mock_get):
        """Test read_json_report function with a successful response."""
        mock_get.return_value = MagicMock(
            status_code=200, json=lambda: {"key": "value"}
        )
        json_report_url = "http://example.com/report.json"
        result, status = read_json_report(json_report_url)

        self.assertEqual(result, {"key": "value"})
        self.assertEqual(status, 200)
        mock_get.assert_called_once_with(json_report_url)

    @mock.patch("requests.get")
    def test_read_json_report_failure(self, mock_get):
        """Test read_json_report function handling a non-200 response."""
        mock_get.return_value = MagicMock(status_code=404).side_effect = Exception(
            "404 Not Found"
        )
        json_report_url = "http://example.com/nonexistent.json"

        with self.assertRaises(Exception):
            read_json_report(json_report_url)

    @with_db_session(db_url=default_db_url)
    def test_get_feature(self, db_session):
        """Test get_feature function."""
        feature_name = faker.word()
        feature = get_feature(feature_name, db_session)
        db_session.add(feature)
        db_session.flush()
        same_feature = get_feature(feature_name, db_session)

        self.assertIsInstance(feature, Feature)
        self.assertEqual(feature.name, feature_name)
        self.assertEqual(feature, same_feature)
        db_session.rollback()
        db_session.close()

    @with_db_session(db_url=default_db_url)
    def test_get_dataset(self, db_session):
        """Test get_dataset function."""
        dataset_stable_id = faker.word()
        dataset = get_dataset(dataset_stable_id, db_session)
        self.assertIsNone(dataset)

        # Create GTFS Feed
        feed = Gtfsfeed(id=faker.word(), data_type="gtfs", stable_id=faker.word())
        # Create a new dataset
        dataset = Gtfsdataset(
            id=faker.word(),
            feed_id=feed.id,
            stable_id=dataset_stable_id,
        )
        try:
            db_session.add(feed)
            db_session.flush()
            db_session.add(dataset)
            db_session.flush()
            feed.latest_dataset_id = dataset.id
            returned_dataset = get_dataset(dataset_stable_id, db_session)
            self.assertIsNotNone(returned_dataset)
            self.assertEqual(returned_dataset, dataset)
        except Exception as e:
            db_session.rollback()
            db_session.close()
            raise e
        finally:
            db_session.rollback()
            db_session.close()

    @mock.patch("requests.get")
    @with_db_session(db_url=default_db_url)
    def test_create_validation_report_entities(self, mock_get, db_session):
        """Test create_validation_report_entities function."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "summary": {
                    "validatedAt": "2021-01-01T00:00:00Z",
                    "validatorVersion": "1.0",
                    "gtfsFeatures": ["stops", "routes"],
                },
                "notices": [
                    {"code": "notice_code", "severity": "ERROR", "totalNotices": 1}
                ],
            },
        )
        feed_stable_id = faker.word()
        dataset_stable_id = faker.word()

        # Create GTFS Feed
        feed = Gtfsfeed(id=faker.word(), data_type="gtfs", stable_id=feed_stable_id)
        # Create a new dataset
        dataset = Gtfsdataset(
            id=faker.word(), feed_id=feed.id, stable_id=dataset_stable_id
        )
        try:
            db_session.add(feed)
            db_session.flush()
            db_session.add(dataset)
            db_session.flush()
            feed.latest_dataset_id = dataset.id
            db_session.commit()
            create_validation_report_entities(feed_stable_id, dataset_stable_id, "1.0")

            # Validate that the validation report was created
            validation_report = (
                db_session.query(Validationreport)
                .filter(Validationreport.id == f"{dataset_stable_id}_1.0")
                .one_or_none()
            )
            self.assertIsNotNone(validation_report)
        except Exception as e:
            raise e
        finally:
            db_session.rollback()
            db_session.close()

    @mock.patch("requests.get")
    def test_create_validation_report_entities_json_error1(self, mock_get):
        """Test create_validation_report_entities function with a JSON error."""
        mock_get.return_value = MagicMock(
            status_code=400,
            json=lambda: {
                "summary": {
                    "validatedAt": "2021-01-01T00:00:00Z",
                    "validatorVersion": "1.0",
                    "gtfsFeatures": ["stops", "routes"],
                },
                "notices": [
                    {"code": "notice_code", "severity": "ERROR", "totalNotices": 1}
                ],
            },
        )
        feed_stable_id = faker.word()
        dataset_stable_id = faker.word()
        _, status = create_validation_report_entities(
            feed_stable_id, dataset_stable_id, "1.0"
        )
        self.assertEqual(status, 400)

    @mock.patch("requests.get")
    def test_create_validation_report_entities_json_error2(self, mock_get):
        """Test create_validation_report_entities function with JSON parsing exception."""
        mock_get.return_value = MagicMock().side_effect = Exception(
            "Exception occurred"
        )
        feed_stable_id = faker.word()
        dataset_stable_id = faker.word()
        _, status = create_validation_report_entities(
            feed_stable_id, dataset_stable_id, "1.0"
        )
        self.assertEqual(status, 500)

    @mock.patch("requests.get")
    def test_create_validation_report_entities_missing_dataset(self, mock_get):
        """
        Test the create_validation_report_entities function when the dataset is not found in the DB
        """
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "summary": {
                    "validatedAt": "2021-01-01T00:00:00Z",
                    "validatorVersion": "1.0",
                    "gtfsFeatures": ["stops", "routes"],
                },
                "notices": [
                    {"code": "notice_code", "severity": "ERROR", "totalNotices": 1}
                ],
            },
        )
        feed_stable_id = faker.word()
        dataset_stable_id = "MISSING_ID"

        message, status = create_validation_report_entities(
            feed_stable_id, dataset_stable_id, "1.0"
        )
        self.assertEqual(500, status)
        self.assertEqual(
            "Error creating validation report entities: Dataset MISSING_ID not found.",
            message,
        )

    @patch("main.create_validation_report_entities")
    def test_process_validation_report(self, create_validation_report_entities_mock):
        request = MagicMock(
            get_json=MagicMock(
                return_value={
                    "dataset_id": faker.word(),
                    "feed_id": faker.word(),
                    "validator_version": "1.0",
                }
            )
        )
        process_validation_report(request)
        create_validation_report_entities_mock.assert_called_once()

    @patch("main.create_validation_report_entities")
    def test_process_validation_report_invalid_request(
        self, create_validation_report_entities_mock
    ):
        request = MagicMock(
            get_json=MagicMock(
                return_value={
                    "dataset_id": faker.word(),
                }
            )
        )
        __, status = process_validation_report(request)
        self.assertEqual(status, 400)
        create_validation_report_entities_mock.assert_not_called()

    def test_populate_service_date_valid_dates(self):
        """Test populate_service_date function with valid date values."""
        dataset = Gtfsdataset(
            id=faker.word(), feed_id=faker.word(), stable_id=faker.word()
        )
        json_report = {
            "summary": {
                "feedInfo": {
                    "feedServiceWindowStart": "2024-01-01",
                    "feedServiceWindowEnd": "2024-12-31",
                }
            }
        }

        populate_service_date(dataset, json_report)

        expected_range_start = datetime.strptime("2024-01-01", "%Y-%m-%d").replace(
            hour=0, minute=0, tzinfo=timezone.utc
        )
        expected_range_end = datetime.strptime("2024-12-31", "%Y-%m-%d").replace(
            hour=23, minute=59, tzinfo=timezone.utc
        )

        self.assertEqual(dataset.service_date_range_start, expected_range_start)
        self.assertEqual(dataset.service_date_range_end, expected_range_end)

    def test_populate_service_date_valid_empty_dates(self):
        """Test populate_service_date function."""
        dataset = Gtfsdataset(
            id=faker.word(), feed_id=faker.word(), stable_id=faker.word()
        )
        json_report = {
            "summary": {
                "feedInfo": {
                    "feedServiceWindowStart": "",
                    "feedServiceWindowEnd": "2024-12-31",
                }
            }
        }
        populate_service_date(dataset, json_report)
        self.assertEqual(dataset.service_date_range_start, None)
        self.assertEqual(dataset.service_date_range_end, None)

        json_report = {
            "summary": {
                "feedInfo": {
                    "feedServiceWindowStart": "2024-12-31",
                    "feedServiceWindowEnd": "",
                }
            }
        }
        populate_service_date(dataset, json_report)
        self.assertEqual(dataset.service_date_range_start, None)
        self.assertEqual(dataset.service_date_range_end, None)

        json_report = {
            "summary": {
                "feedInfo": {
                    "feedServiceWindowStart": "2024-12-31",
                    "feedServiceWindowEnd": None,
                }
            }
        }
        populate_service_date(dataset, json_report)
        self.assertEqual(dataset.service_date_range_start, None)
        self.assertEqual(dataset.service_date_range_end, None)

        json_report = {
            "summary": {
                "feedInfo": {
                    "feedServiceWindowStart": None,
                    "feedServiceWindowEnd": "2024-12-31",
                }
            }
        }
        populate_service_date(dataset, json_report)
        self.assertEqual(dataset.service_date_range_start, None)
        self.assertEqual(dataset.service_date_range_end, None)

    @with_db_session(db_url=default_db_url)
    def test_compute_validation_report_counters(self, db_session):
        """Test compute_validation_report_counters function."""
        # Mock the request object
        request = MagicMock()
        compute_validation_report_counters(request)
        validation_report = db_session.query(Validationreport).one()
        self.assertEqual(validation_report.total_info, 5)
        self.assertEqual(validation_report.total_warning, 3)
        self.assertEqual(validation_report.total_error, 3)
        self.assertEqual(validation_report.unique_info_count, 1)
        self.assertEqual(validation_report.unique_warning_count, 1)
        self.assertEqual(validation_report.unique_error_count, 2)

    @mock.patch("requests.get")
    @with_db_session(db_url=default_db_url)
    def test_create_validation_report_entities_missing_validator_version(
        self, mock_get, db_session
    ):
        """Test create_validation_report_entities function
        when the validator version is missing from the JSON report."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "summary": {
                    "validatedAt": "2021-01-01T00:00:00Z",
                    "gtfsFeatures": ["stops", "routes"],
                },
                "notices": [
                    {"code": "notice_code", "severity": "ERROR", "totalNotices": 1}
                ],
            },
        )
        feed_stable_id = faker.uuid4()
        dataset_stable_id = faker.uuid4()

        # Create GTFS Feed
        feed = Gtfsfeed(id=faker.uuid4(), data_type="gtfs", stable_id=feed_stable_id)
        # Create a new dataset
        dataset = Gtfsdataset(
            id=faker.uuid4(),
            feed_id=feed.id,
            stable_id=dataset_stable_id,
        )
        try:
            db_session.add(feed)
            db_session.flush()
            db_session.add(dataset)
            db_session.flush()
            feed.latest_dataset_id = dataset.id
            db_session.commit()
            create_validation_report_entities(feed_stable_id, dataset_stable_id, "1.0")

            # Validate that the validation report was created
            validation_report = (
                db_session.query(Validationreport)
                .filter(Validationreport.id == f"{dataset_stable_id}_1.0")
                .one_or_none()
            )
            self.assertIsNotNone(validation_report)
        except Exception as e:
            raise e
        finally:
            db_session.rollback()
            db_session.close()

    @mock.patch("requests.get")
    @with_db_session(db_url=default_db_url)
    def test_create_validation_report_entities_validation_report_exists(
        self, mock_get, db_session
    ):
        """Test create_validation_report_entities function
        when the validation report already exists."""
        version = "1.0"
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "summary": {
                    "validatedAt": "2021-01-01T00:00:00Z",
                    "gtfsFeatures": ["stops", "routes"],
                    "validatorVersion": version,
                },
                "notices": [
                    {"code": "notice_code", "severity": "ERROR", "totalNotices": 1}
                ],
            },
        )
        feed_stable_id = faker.word()
        dataset_stable_id = faker.word()
        report_id = f"{dataset_stable_id}_{version}"
        # Create GTFS Feed
        feed = Gtfsfeed(id=faker.word(), data_type="gtfs", stable_id=feed_stable_id)
        # Create a new dataset
        dataset = Gtfsdataset(
            id=faker.word(),
            feed_id=feed.id,
            stable_id=dataset_stable_id,
            validation_reports=[
                Validationreport(
                    id=report_id, validator_version="1.0", notices=[], features=[]
                )
            ],
        )

        try:
            db_session.add(feed)
            db_session.add(dataset)
            db_session.flush()
            feed.latest_dataset_id = dataset.id
            db_session.commit()
            # Validate that the validation report is already in the DB
            validation_report = (
                db_session.query(Validationreport)
                .filter(Validationreport.id == report_id)
                .one_or_none()
            )
            self.assertIsNotNone(validation_report)
            create_validation_report_entities(feed_stable_id, dataset_stable_id, "1.0")

            # Validate that the validation report remained in the DB
            validation_report = (
                db_session.query(Validationreport)
                .filter(Validationreport.id == report_id)
                .one_or_none()
            )
            self.assertIsNotNone(validation_report)
        except Exception as e:
            raise e
        finally:
            db_session.rollback()
            db_session.close()
