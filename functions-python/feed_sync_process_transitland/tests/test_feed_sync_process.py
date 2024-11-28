import base64
import json
import logging
import uuid
from unittest import mock
from unittest.mock import patch, Mock, MagicMock
import os

import pytest
from google.api_core.exceptions import DeadlineExceeded
from google.cloud import pubsub_v1
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as DBSession

from database_gen.sqlacodegen_models import Feed
from helpers.feed_sync.models import TransitFeedSyncPayload as FeedPayload

with mock.patch("helpers.logger.Logger.init_logger") as mock_init_logger:
    from feed_sync_process_transitland.src.main import (
        FeedProcessor,
        process_feed_event,
        log_message,
    )

# Environment variables for tests
TEST_DB_URL = "postgresql://test:test@localhost:54320/test"


@pytest.fixture
def mock_feed():
    """Fixture for a Feed model instance"""
    return Mock()


@pytest.fixture
def mock_external_id():
    """Fixture for an ExternalId model instance"""
    return Mock()


@pytest.fixture
def mock_location():
    """Fixture for a Location model instance"""
    return Mock()


class MockLogger:
    """Mock logger for testing"""

    @staticmethod
    def init_logger():
        return MagicMock()

    def __init__(self, name):
        self.name = name
        self._logger = logging.getLogger(name)

    def get_logger(self):
        mock_logger = MagicMock()
        # Add all required logging methods
        mock_logger.info = MagicMock()
        mock_logger.error = MagicMock()
        mock_logger.warning = MagicMock()
        mock_logger.debug = MagicMock()
        mock_logger.addFilter = MagicMock()
        return mock_logger


@pytest.fixture(autouse=True)
def mock_logging():
    """Mock both local and GCP logging."""
    with patch("feed_sync_process_transitland.src.main.logger") as mock_log, patch(
        "feed_sync_process_transitland.src.main.gcp_logger"
    ) as mock_gcp_log, patch("helpers.logger.Logger", MockLogger):
        for logger in [mock_log, mock_gcp_log]:
            logger.info = MagicMock()
            logger.error = MagicMock()
            logger.warning = MagicMock()
            logger.debug = MagicMock()
            logger.addFilter = MagicMock()

        yield mock_log


@pytest.fixture
def feed_payload():
    """Fixture for feed payload."""
    return FeedPayload(
        external_id="test123",
        feed_id="feed1",
        feed_url="https://example.com/feed1",
        execution_id="exec123",
        spec="gtfs",
        auth_info_url=None,
        auth_param_name=None,
        type=None,
        operator_name="Test Operator",
        country="United States",
        state_province="CA",
        city_name="Test City",
        source="TLD",
        payload_type="new",
    )


@mock.patch.dict(
    "os.environ",
    {
        "FEEDS_DATABASE_URL": TEST_DB_URL,
        "GOOGLE_APPLICATION_CREDENTIALS": "dummy-credentials.json",
    },
)
class TestFeedProcessor:
    """Test suite for FeedProcessor."""

    @pytest.fixture
    def processor(self):
        """Fixture for FeedProcessor with mocked dependencies."""
        # mock for the database session
        mock_session = Mock(spec=DBSession)
        mock_publisher = Mock(spec=pubsub_v1.PublisherClient)

        processor = FeedProcessor(mock_session)
        processor.publisher = mock_publisher
        mock_publisher.topic_path = Mock()  # Ensure `topic_path` method exists
        mock_publisher.publish = Mock()
        processor.publisher = mock_publisher

        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = None
        mock_session.query.return_value = mock_query

        return processor

    @staticmethod
    def _create_payload_dict(feed_payload: FeedPayload) -> dict:
        """Helper method to create a payload dictionary from a FeedPayload object."""
        return {
            "external_id": feed_payload.external_id,
            "feed_id": feed_payload.feed_id,
            "feed_url": feed_payload.feed_url,
            "execution_id": feed_payload.execution_id,
            "spec": feed_payload.spec,
            "auth_info_url": feed_payload.auth_info_url,
            "auth_param_name": feed_payload.auth_param_name,
            "type": feed_payload.type,
            "operator_name": feed_payload.operator_name,
            "country": feed_payload.country,
            "state_province": feed_payload.state_province,
            "city_name": feed_payload.city_name,
            "source": feed_payload.source,
            "payload_type": feed_payload.payload_type,
        }

    def test_get_current_feed_info(self, processor, feed_payload, mock_logging):
        """Test retrieving current feed information."""
        # Mock database query
        processor.session.query.return_value.filter.return_value.first.return_value = (
            Mock(
                id="feed-uuid",
                producer_url="https://example.com/feed",
                stable_id="TLD-test123",
                status="active",
            )
        )

        feed_id, url = processor.get_current_feed_info(
            feed_payload.external_id, feed_payload.source
        )

        # Assertions
        assert feed_id == "feed-uuid"
        assert url == "https://example.com/feed"
        mock_logging.info.assert_called_with(
            "Retrieved feed TLD-test123 "
            f"info for external_id: {feed_payload.external_id} (status: active)"
        )

        # Test case when feed does not exist
        processor.session.query.return_value.filter.return_value.first.return_value = (
            None
        )
        feed_id, url = processor.get_current_feed_info(
            feed_payload.external_id, feed_payload.source
        )

        assert feed_id is None
        assert url is None
        mock_logging.info.assert_called_with(
            f"No existing feed found for external_id: {feed_payload.external_id}"
        )

    def test_check_feed_url_exists_comprehensive(self, processor, mock_logging):
        """Test comprehensive feed URL existence checks."""
        test_url = "https://example.com/feed"

        # Test case 1: Active feed exists
        mock_feed = Mock(id="test-id", status="active")
        processor.session.query.return_value.filter.return_value.all.return_value = [
            mock_feed
        ]

        result = processor.check_feed_url_exists(test_url)
        assert result is True
        mock_logging.info.assert_called_with(
            f"Found existing feed with URL: {test_url} (status: active)"
        )

        # Test case 2: Deprecated feed exists
        mock_logging.info.reset_mock()
        mock_feed.status = "deprecated"
        result = processor.check_feed_url_exists(test_url)
        assert result is True
        mock_logging.error.assert_called_with(
            f"Feed URL {test_url} exists in deprecated feed (id: {mock_feed.id}). "
            "Cannot reuse URLs from deprecated feeds."
        )

        # Test case 3: No feed exists
        mock_logging.error.reset_mock()
        processor.session.query.return_value.filter.return_value.all.return_value = []
        result = processor.check_feed_url_exists(test_url)
        assert result is False
        mock_logging.debug.assert_called_with(
            f"No existing feed found with URL: {test_url}"
        )

        # Test case 4: Multiple feeds with same URL
        mock_logging.debug.reset_mock()
        mock_feeds = [
            Mock(id="feed1", status="active"),
            Mock(id="feed2", status="deprecated"),
        ]
        processor.session.query.return_value.filter.return_value.all.return_value = (
            mock_feeds
        )
        result = processor.check_feed_url_exists(test_url)
        assert result is True
        mock_logging.warning.assert_called_with(
            f"Multiple feeds found with URL: {test_url}"
        )

    def test_log_message_function(self, mock_logging):
        """Test the log_message function for different log levels."""
        levels = ["info", "error", "warning", "debug"]
        messages = ["Info message", "Error message", "Warning message", "Debug message"]

        for level, message in zip(levels, messages):
            log_message(level, message)

            if level == "info":
                mock_logging.info.assert_called_with(message)
            elif level == "error":
                mock_logging.error.assert_called_with(message)
            elif level == "warning":
                mock_logging.warning.assert_called_with(message)
            elif level == "debug":
                mock_logging.debug.assert_called_with(message)

    def test_database_error_handling(self, processor, feed_payload, mock_logging):
        """Test database error handling in different scenarios."""

        # Test case 1: General database error during feed processing
        processor.session.query.side_effect = SQLAlchemyError("Database error")
        with pytest.raises(SQLAlchemyError, match="Database error"):
            processor.process_feed(feed_payload)

        processor.session.rollback.assert_called_once()
        mock_logging.error.assert_called_with(
            "Database transaction rolled back due to error"
        )

        # Reset mocks for next test
        processor.session.rollback.reset_mock()
        mock_logging.error.reset_mock()

        # Test case 2: Connection failure during feed processing
        processor.session.query.side_effect = SQLAlchemyError("Connection refused")

        with pytest.raises(SQLAlchemyError, match="Connection refused"):
            processor.process_feed(feed_payload)

        processor.session.rollback.assert_called_once()
        mock_logging.error.assert_called_with(
            "Database transaction rolled back due to error"
        )

    def test_publish_to_batch_topic_comprehensive(
        self, processor, feed_payload, mock_logging
    ):
        """Test publishing to batch topic including success, error, and message format validation."""

        # Test case 1: Successful publish with message format validation
        processor.publisher.topic_path.return_value = "test_topic"
        mock_future = Mock()
        processor.publisher.publish.return_value = mock_future

        processor.publish_to_batch_topic(feed_payload)

        # Verify publish was called and message format
        call_args = processor.publisher.publish.call_args
        assert call_args is not None
        _, kwargs = call_args

        # Decode and verify message content
        message_data = json.loads(base64.b64decode(kwargs["data"]).decode("utf-8"))
        assert message_data["execution_id"] == feed_payload.execution_id
        assert message_data["producer_url"] == feed_payload.feed_url
        assert (
            message_data["feed_stable_id"]
            == f"{feed_payload.source}-{feed_payload.external_id}"
        )

        mock_logging.info.assert_called_with(
            f"Published feed {feed_payload.feed_id} to dataset batch topic"
        )

        # Test case 2: Publish error
        processor.publisher.publish.side_effect = Exception("Pub/Sub error")

        with pytest.raises(Exception, match="Pub/Sub error"):
            processor.publish_to_batch_topic(feed_payload)

        mock_logging.error.assert_called_with(
            "Error publishing to dataset batch topic: Pub/Sub error"
        )

        # Test case 3: Timeout error
        processor.publisher.publish.side_effect = DeadlineExceeded("Timeout error")

        with pytest.raises(DeadlineExceeded, match="Timeout error"):
            processor.publish_to_batch_topic(feed_payload)

        mock_logging.error.assert_called_with(
            "Error publishing to dataset batch topic: 504 Timeout error"
        )

    def test_process_feed_event_validation(self, mock_logging):
        """Test feed event processing with various invalid payloads."""

        # Test case 1: Empty payload
        empty_payload_data = base64.b64encode(json.dumps({}).encode("utf-8")).decode()
        cloud_event = Mock()
        cloud_event.data = {"message": {"data": empty_payload_data}}

        result = process_feed_event(cloud_event)
        assert result[1] == 500
        mock_logging.error.assert_called_with(
            "Error processing feed event: TransitFeedSyncPayload.__init__() missing 14 "
            "required positional arguments: 'external_id', 'feed_id', 'feed_url', "
            "'execution_id', 'spec', 'auth_info_url', 'auth_param_name', 'type', "
            "'operator_name', 'country', 'state_province', 'city_name', 'source', and "
            "'payload_type'"
        )

        # Test case 2: Invalid field
        mock_logging.error.reset_mock()
        invalid_payload_data = base64.b64encode(
            json.dumps({"invalid": "data"}).encode("utf-8")
        ).decode()
        cloud_event.data = {"message": {"data": invalid_payload_data}}

        result = process_feed_event(cloud_event)
        assert result[1] == 500
        mock_logging.error.assert_called_with(
            "Error processing feed event: TransitFeedSyncPayload.__init__() got an "
            "unexpected keyword argument 'invalid'"
        )

        # Test case 3: Type error
        mock_logging.error.reset_mock()
        type_error_payload = {"external_id": 12345, "feed_url": True, "feed_id": None}
        payload_data = base64.b64encode(
            json.dumps(type_error_payload).encode("utf-8")
        ).decode()
        cloud_event.data = {"message": {"data": payload_data}}

        result = process_feed_event(cloud_event)
        assert result[1] == 500
        mock_logging.error.assert_called_with(
            "Error processing feed event: TransitFeedSyncPayload.__init__() missing 11 "
            "required positional arguments: 'execution_id', 'spec', 'auth_info_url', "
            "'auth_param_name', 'type', 'operator_name', 'country', 'state_province', "
            "'city_name', 'source', and 'payload_type'"
        )

    def test_process_new_feed_with_location(
        self, processor, feed_payload, mock_logging
    ):
        """Test creating a new feed with location information."""
        # Mock UUID generation
        new_feed_id = str(uuid.uuid4())

        # Mock database query to return no existing feeds
        processor.session.query.return_value.filter.return_value.all.return_value = []

        with patch("uuid.uuid4", return_value=uuid.UUID(new_feed_id)):
            # Mock Location class
            mock_location_cls = Mock(name="Location")
            mock_location = mock_location_cls.return_value
            mock_location.id = "US-CA-Test City"
            mock_location.country_code = "US"
            mock_location.country = "United States"
            mock_location.subdivision_name = "CA"
            mock_location.municipality = "Test City"
            mock_location.__eq__ = (
                lambda self, other: isinstance(other, Mock) and self.id == other.id
            )

            # Create a Feed class with a real list for locations
            class MockFeed:
                def __init__(self):
                    self.locations = []
                    self.externalids = []
                    self.id = new_feed_id
                    self.producer_url = feed_payload.feed_url
                    self.data_type = feed_payload.spec
                    self.provider = feed_payload.operator_name
                    self.status = "active"
                    self.stable_id = f"{feed_payload.source}-{feed_payload.external_id}"

            mock_feed = MockFeed()

            with patch(
                "database_gen.sqlacodegen_models.Feed", return_value=mock_feed
            ), patch(
                "database_gen.sqlacodegen_models.Location", mock_location_cls
            ), patch(
                "helpers.locations.create_or_get_location", return_value=mock_location
            ):
                processor.process_new_feed(feed_payload)

                # Verify feed creation
                created_feed = processor.session.add.call_args[0][0]
                assert created_feed.id == new_feed_id
                assert created_feed.producer_url == feed_payload.feed_url
                assert created_feed.data_type == feed_payload.spec
                assert created_feed.provider == feed_payload.operator_name

                # Verify location was added to feed
                assert len(created_feed.locations) == 1
                assert created_feed.locations[0].id == "US-CA-Test City"
                assert created_feed.locations[0].country_code == "US"
                assert created_feed.locations[0].country == "United States"
                assert created_feed.locations[0].subdivision_name == "CA"
                assert created_feed.locations[0].municipality == "Test City"
                mock_logging.debug.assert_any_call(
                    f"Added location information for feed: {new_feed_id}"
                )

    def test_process_new_feed_without_location(
        self, processor, feed_payload, mock_logging
    ):
        """Test creating a new feed without location information."""
        # Modify payload to have no location info
        feed_payload.country = None
        feed_payload.state_province = None
        feed_payload.city_name = None

        # Mock database query to return no existing feeds
        processor.session.query.return_value.filter.return_value.all.return_value = []

        # Mock UUID generation
        new_feed_id = str(uuid.uuid4())

        # Create a Feed class with a real list for locations
        class MockFeed:
            def __init__(self):
                self.locations = []
                self.externalids = []
                self.id = new_feed_id
                self.producer_url = feed_payload.feed_url
                self.data_type = feed_payload.spec
                self.provider = feed_payload.operator_name
                self.status = "active"
                self.stable_id = f"{feed_payload.source}-{feed_payload.external_id}"

        mock_feed = MockFeed()

        with patch("uuid.uuid4", return_value=uuid.UUID(new_feed_id)), patch(
            "database_gen.sqlacodegen_models.Feed", return_value=mock_feed
        ), patch("helpers.locations.create_or_get_location", return_value=None):
            processor.process_new_feed(feed_payload)

            # Verify feed creation
            created_feed = processor.session.add.call_args[0][0]
            assert created_feed.id == new_feed_id
            assert not created_feed.locations

    def test_process_feed_update_with_location(
        self, processor, feed_payload, mock_logging
    ):
        """Test updating a feed with location information."""
        old_feed_id = str(uuid.uuid4())
        new_feed_id = str(uuid.uuid4())

        # Mock database query to return no existing feeds
        processor.session.query.return_value.filter.return_value.all.return_value = []

        # Mock old feed
        mock_old_feed = Mock(id=old_feed_id, status="active")
        processor.session.get.return_value = mock_old_feed

        # Mock Location class
        mock_location_cls = Mock(name="Location")
        mock_location = mock_location_cls.return_value
        mock_location.id = "US-CA-Test City"
        mock_location.country_code = "US"
        mock_location.country = "United States"
        mock_location.subdivision_name = "CA"
        mock_location.municipality = "Test City"
        mock_location.__eq__ = (
            lambda self, other: isinstance(other, Mock) and self.id == other.id
        )

        # Create a Feed class with a real list for locations
        class MockFeed:
            def __init__(self):
                self.locations = []
                self.externalids = []
                self.id = new_feed_id
                self.producer_url = feed_payload.feed_url
                self.data_type = feed_payload.spec
                self.provider = feed_payload.operator_name
                self.status = "active"
                self.stable_id = f"{feed_payload.source}-{feed_payload.external_id}"

        mock_new_feed = MockFeed()

        with patch("uuid.uuid4", return_value=uuid.UUID(new_feed_id)), patch(
            "database_gen.sqlacodegen_models.Feed", return_value=mock_new_feed
        ), patch("database_gen.sqlacodegen_models.Location", mock_location_cls), patch(
            "helpers.locations.create_or_get_location", return_value=mock_location
        ):
            processor.process_feed_update(feed_payload, old_feed_id)

            # Verify feed update
            assert mock_old_feed.status == "deprecated"

            # Find the Feed object in the add calls
            feed_add_call = None
            for call in processor.session.add.call_args_list:
                obj = call[0][0]
                if hasattr(obj, "locations"):  # This is our Feed object
                    feed_add_call = call
                    break

            assert (
                feed_add_call is not None
            ), "Feed object not found in session.add calls"
            created_feed = feed_add_call[0][0]

            # Verify new feed creation with location
            assert len(created_feed.locations) == 1
            assert created_feed.locations[0].id == "US-CA-Test City"
            assert created_feed.locations[0].country_code == "US"
            assert created_feed.locations[0].country == "United States"
            assert created_feed.locations[0].subdivision_name == "CA"
            assert created_feed.locations[0].municipality == "Test City"
            mock_logging.debug.assert_any_call(
                f"Added location information for feed: {new_feed_id}"
            )

    def test_process_feed_update_without_location(
        self, processor, feed_payload, mock_logging
    ):
        """Test updating a feed without location information."""
        old_feed_id = str(uuid.uuid4())
        new_feed_id = str(uuid.uuid4())

        # Mock database query to return no existing feeds
        processor.session.query.return_value.filter.return_value.all.return_value = []

        # Modify payload to have no location info
        feed_payload.country = None
        feed_payload.state_province = None
        feed_payload.city_name = None

        # Mock old feed
        mock_old_feed = Mock(id=old_feed_id, status="active")
        processor.session.get.return_value = mock_old_feed

        # Create a Feed class with a real list for locations
        class MockFeed:
            def __init__(self):
                self.locations = []
                self.externalids = []
                self.id = new_feed_id
                self.producer_url = feed_payload.feed_url
                self.data_type = feed_payload.spec
                self.provider = feed_payload.operator_name
                self.status = "active"
                self.stable_id = f"{feed_payload.source}-{feed_payload.external_id}"

        mock_new_feed = MockFeed()

        with patch("uuid.uuid4", return_value=uuid.UUID(new_feed_id)), patch(
            "database_gen.sqlacodegen_models.Feed", return_value=mock_new_feed
        ), patch("helpers.locations.create_or_get_location", return_value=None):
            processor.process_feed_update(feed_payload, old_feed_id)

            # Verify feed update
            assert mock_old_feed.status == "deprecated"

            # Verify new feed creation without location
            assert not mock_new_feed.locations

    def test_process_feed_event_database_connection_error(
        self, processor, feed_payload, mock_logging
    ):
        """Test feed event processing with database connection error."""
        # Create cloud event with valid payload
        payload_dict = self._create_payload_dict(feed_payload)
        payload_data = base64.b64encode(
            json.dumps(payload_dict).encode("utf-8")
        ).decode()
        cloud_event = Mock()
        cloud_event.data = {"message": {"data": payload_data}}

        # Mock database session to raise error
        with patch(
            "feed_sync_process_transitland.src.main.start_db_session"
        ) as mock_start_session:
            mock_start_session.side_effect = SQLAlchemyError(
                "Database connection error"
            )

            result = process_feed_event(cloud_event)
            assert result[1] == 500
            mock_logging.error.assert_called_with(
                "Error processing feed event: Database connection error"
            )

    def test_process_feed_event_pubsub_error(
        self, processor, feed_payload, mock_logging
    ):
        """Test feed event processing handles missing credentials error."""
        # Create cloud event with valid payload
        payload_dict = self._create_payload_dict(feed_payload)
        payload_data = base64.b64encode(
            json.dumps(payload_dict).encode("utf-8")
        ).decode()

        # Create cloud event mock with minimal required structure
        cloud_event = Mock()
        cloud_event.data = {"message": {"data": payload_data}}

        # Mock database session with minimal setup
        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.all.return_value = []

        # Process event and verify error handling
        with patch(
            "feed_sync_process_transitland.src.main.start_db_session",
            return_value=mock_session,
        ):
            result = process_feed_event(cloud_event)
            assert result[1] == 500
            mock_logging.error.assert_called_with(
                "Error processing feed event: File dummy-credentials.json was not found."
            )

    def test_process_feed_event_malformed_cloud_event(self, mock_logging):
        """Test feed event processing with malformed cloud event."""
        # Test case 1: Missing message data
        cloud_event = Mock()
        cloud_event.data = {}

        result = process_feed_event(cloud_event)
        assert result[1] == 500
        mock_logging.error.assert_called_with("Error processing feed event: 'message'")

        # Test case 2: Invalid base64 data
        mock_logging.error.reset_mock()
        cloud_event.data = {"message": {"data": "invalid-base64"}}

        result = process_feed_event(cloud_event)
        error_msg = (
            "Error processing feed event: Invalid base64-encoded string: "
            "number of data characters (13) cannot be 1 more than a multiple of 4"
        )
        mock_logging.error.assert_called_with(error_msg)

    def test_publish_to_batch_topic(self, processor, feed_payload, mock_logging):
        """Test publishing feed to batch topic."""
        # Mock the topic path
        topic_path = "projects/test-project/topics/test-topic"
        processor.publisher.topic_path.return_value = topic_path

        # Mock the publish future
        mock_future = Mock()
        mock_future.result.return_value = "message_id"
        processor.publisher.publish.return_value = mock_future

        # Call the method
        processor.publish_to_batch_topic(feed_payload)

        # Verify topic path was created correctly
        processor.publisher.topic_path.assert_called_once_with(
            os.getenv("PROJECT_ID"), os.getenv("DATASET_BATCH_TOPIC")
        )

        # Expected message data
        expected_data = {
            "execution_id": feed_payload.execution_id,
            "producer_url": feed_payload.feed_url,
            "feed_stable_id": f"{feed_payload.source}-{feed_payload.external_id}",
            "feed_id": feed_payload.feed_id,
            "dataset_id": None,
            "dataset_hash": None,
            "authentication_type": "0",  # default value when type is None
            "authentication_info_url": feed_payload.auth_info_url,
            "api_key_parameter_name": feed_payload.auth_param_name,
        }

        # Verify publish was called with correct data
        encoded_data = base64.b64encode(json.dumps(expected_data).encode("utf-8"))
        processor.publisher.publish.assert_called_once_with(
            topic_path, data=encoded_data
        )

        # Verify success was logged
        mock_logging.info.assert_called_with(
            f"Published feed {feed_payload.feed_id} to dataset batch topic"
        )

    def test_publish_to_batch_topic_error(self, processor, feed_payload, mock_logging):
        """Test error handling when publishing to batch topic fails."""
        # Mock the topic path
        topic_path = "projects/test-project/topics/test-topic"
        processor.publisher.topic_path.return_value = topic_path

        # Mock publish to raise an error
        error_msg = "Failed to publish"
        processor.publisher.publish.side_effect = Exception(error_msg)

        # Call the method and verify it raises the error
        with pytest.raises(Exception) as exc_info:
            processor.publish_to_batch_topic(feed_payload)

        assert str(exc_info.value) == error_msg

        # Verify error was logged
        mock_logging.error.assert_called_with(
            f"Error publishing to dataset batch topic: {error_msg}"
        )

    def test_process_feed_update_with_multiple_references(
        self, processor, feed_payload, mock_logging
    ):
        """Test updating feed with multiple external ID references"""
        old_feed_id = "old-feed-uuid"

        # Mock multiple references to the external ID
        processor.session.query.return_value.join.return_value.filter.return_value.count.return_value = (
            3
        )

        # Mock getting old feed
        mock_old_feed = Mock(spec=Feed)
        processor.session.get.return_value = mock_old_feed

        # Process the update
        processor.process_feed_update(feed_payload, old_feed_id)

        # Verify stable_id includes reference count
        expected_stable_id = f"{feed_payload.source}-{feed_payload.external_id}_3"
        mock_logging.debug.assert_any_call(
            f"Generated new stable_id: {expected_stable_id} (reference count: 3)"
        )

        # Verify old feed was deprecated
        assert mock_old_feed.status == "deprecated"

    def test_process_feed_with_auth_info(self, processor, feed_payload, mock_logging):
        """Test processing feed with authentication info"""
        # Modify payload to include auth info
        feed_payload.auth_info_url = "https://auth.example.com"
        feed_payload.type = "oauth2"
        feed_payload.auth_param_name = "access_token"

        # Mock the methods
        with patch.object(
            processor, "get_current_feed_info", return_value=(None, None)
        ), patch.object(
            processor, "check_feed_url_exists", return_value=False
        ), patch.object(
            processor, "process_new_feed"
        ) as mock_process_new_feed:
            # Process the feed
            processor.process_feed(feed_payload)

            # Verify feed was processed
            mock_process_new_feed.assert_called_once_with(feed_payload)
            mock_logging.debug.assert_any_call(
                "Database transaction committed successfully"
            )

            # Verify not published to batch topic (because auth_info_url is set)
            processor.publisher.publish.assert_not_called()

    def test_process_feed_event_invalid_json(self, mock_logging):
        """Test handling of invalid JSON in cloud event"""
        # Create invalid base64 encoded JSON
        invalid_json = base64.b64encode(b'{"invalid": "json"').decode()

        cloud_event = Mock()
        cloud_event.data = {"message": {"data": invalid_json}}

        # Process the event
        result, status_code = process_feed_event(cloud_event)

        # Verify error handling
        assert status_code == 500
        assert "Error processing feed event" in result
        mock_logging.error.assert_called()

    def test_process_feed_update_without_old_feed(
        self, processor, feed_payload, mock_logging
    ):
        """Test feed update when old feed is not found"""
        old_feed_id = "non-existent-feed"

        # Mock old feed not found
        processor.session.get.return_value = None

        # Process the update
        processor.process_feed_update(feed_payload, old_feed_id)

        # Verify processing continued without error
        mock_logging.debug.assert_any_call(
            f"Old feed_id: {old_feed_id}, New URL: {feed_payload.feed_url}"
        )

        # Verify no deprecation log since old feed wasn't found
        deprecation_log = f"Deprecating old feed ID: {old_feed_id}"
        assert mock.call(deprecation_log) not in mock_logging.debug.call_args_list
