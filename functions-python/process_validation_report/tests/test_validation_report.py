import os
import unittest
from unittest import mock
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from faker import Faker

from shared.database_gen.sqlacodegen_models import (
    Feature,
    Gtfsdataset,
    Gtfsfeed,
    Notice,
    Validationreport,
)
from main import compute_validation_report_counters
from test_shared.test_utils.database_utils import default_db_url, get_testing_session
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

    def test_get_feature(self):
        """Test get_feature function."""
        session = get_testing_session()
        feature_name = faker.word()
        feature = get_feature(feature_name, session)
        session.add(feature)
        session.flush()
        same_feature = get_feature(feature_name, session)

        self.assertIsInstance(feature, Feature)
        self.assertEqual(feature.name, feature_name)
        self.assertEqual(feature, same_feature)
        session.rollback()
        session.close()

    def test_get_dataset(self):
        """Test get_dataset function."""
        session = get_testing_session()
        dataset_stable_id = faker.word()
        dataset = get_dataset(dataset_stable_id, session)
        self.assertIsNone(dataset)

        # Create GTFS Feed
        feed = Gtfsfeed(id=faker.word(), data_type="gtfs", stable_id=faker.word())
        # Create a new dataset
        dataset = Gtfsdataset(
            id=faker.word(), feed_id=feed.id, stable_id=dataset_stable_id, latest=True
        )
        try:
            session.add(feed)
            session.add(dataset)
            session.flush()
            returned_dataset = get_dataset(dataset_stable_id, session)
            self.assertIsNotNone(returned_dataset)
            self.assertEqual(returned_dataset, dataset)
        except Exception as e:
            session.rollback()
            session.close()
            raise e
        finally:
            session.rollback()
            session.close()

    @mock.patch.dict(os.environ, {"FEEDS_DATABASE_URL": default_db_url})
    @mock.patch("requests.get")
    def test_create_validation_report_entities(self, mock_get):
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
            id=faker.word(), feed_id=feed.id, stable_id=dataset_stable_id, latest=True
        )
        session = get_testing_session()
        try:
            session.add(feed)
            session.add(dataset)
            session.commit()
            create_validation_report_entities(feed_stable_id, dataset_stable_id, "1.0")

            # Validate that the validation report was created
            validation_report = (
                session.query(Validationreport)
                .filter(Validationreport.id == f"{dataset_stable_id}_1.0")
                .one_or_none()
            )
            self.assertIsNotNone(validation_report)
        except Exception as e:
            raise e
        finally:
            session.rollback()
            session.close()

    @mock.patch.dict(os.environ, {"FEEDS_DATABASE_URL": default_db_url})
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

    @mock.patch.dict(os.environ, {"FEEDS_DATABASE_URL": default_db_url})
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

    @patch("main.Logger")
    @patch("main.create_validation_report_entities")
    def test_process_validation_report(self, create_validation_report_entities_mock, _):
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

    @patch("main.Logger")
    @patch("main.create_validation_report_entities")
    def test_process_validation_report_invalid_request(
        self, create_validation_report_entities_mock, _
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
            id=faker.word(), feed_id=faker.word(), stable_id=faker.word(), latest=True
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
            id=faker.word(), feed_id=faker.word(), stable_id=faker.word(), latest=True
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

    @patch("main.Database")
    def test_compute_validation_report_counters(self, mock_database):
        """Test compute_validation_report_counters function."""
        # Mock database session
        mock_session = MagicMock()
        mock_database.return_value.start_db_session.return_value.__enter__.return_value = (
            mock_session
        )

        # Mock notices
        mock_notice_1 = Notice(
            severity="INFO", total_notices=5, notice_code="info_code_1"
        )
        mock_notice_2 = Notice(
            severity="WARNING", total_notices=3, notice_code="warning_code_1"
        )
        mock_notice_3 = Notice(
            severity="ERROR", total_notices=2, notice_code="error_code_1"
        )
        mock_notice_4 = Notice(
            severity="ERROR", total_notices=1, notice_code="error_code_2"
        )

        # Mock validation report
        mock_validation_report = MagicMock(
            id="report_1",
            notices=[mock_notice_1, mock_notice_2, mock_notice_3, mock_notice_4],
            total_info=None,
            total_warning=None,
            total_error=None,
            unique_info_count=None,
            unique_warning_count=None,
            unique_error_count=None,
        )

        # Mock query to return the validation report
        mock_session.query.return_value.filter.return_value.limit.return_value.offset.return_value.all.return_value = [
            mock_validation_report
        ]

        # Call the function
        compute_validation_report_counters(mock_session)

        # Assertions for computed counters
        self.assertEqual(mock_validation_report.total_info, 5)
        self.assertEqual(mock_validation_report.total_warning, 3)
        self.assertEqual(mock_validation_report.total_error, 3)
        self.assertEqual(mock_validation_report.unique_info_count, 1)
        self.assertEqual(mock_validation_report.unique_warning_count, 1)
        self.assertEqual(mock_validation_report.unique_error_count, 2)

        # Ensure the session's query method was called
        mock_session.query.assert_called_once()
