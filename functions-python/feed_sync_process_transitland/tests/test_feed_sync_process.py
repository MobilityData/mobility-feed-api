import base64
import json
import uuid
from unittest import mock
from unittest.mock import patch, Mock, MagicMock
import logging

import pytest
from google.cloud import pubsub_v1
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as DBSession

from feed_sync_process_transitland.src.main import (
    FeedProcessor,
    process_feed_event,
)
from helpers.feed_sync.models import TransitFeedSyncPayload as FeedPayload

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
        # Configure both loggers with all required methods
        for logger in [mock_log, mock_gcp_log]:
            logger.info = MagicMock()
            logger.error = MagicMock()
            logger.warning = MagicMock()
            logger.debug = MagicMock()
            logger.addFilter = MagicMock()

        yield mock_log


@pytest.fixture
def feed_payload():
    """Fixture for a standard feed payload"""
    return FeedPayload(
        external_id="onestop1",
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
        db_session = Mock(spec=DBSession)
        mock_publisher = Mock(spec=pubsub_v1.PublisherClient)
        processor = FeedProcessor(db_session)
        processor.publisher = mock_publisher
        return processor

    def test_get_current_feed_info(self, processor, feed_payload, mock_logging):
        """Test retrieving current feed information."""
        # Mock database query
        processor.session.query.return_value.filter.return_value.first.return_value = (
            Mock(
                id="feed-uuid",
                producer_url="http://example.com/feed",
                stable_id="TLD-test123",
                status="active",
            )
        )

        feed_id, url = processor.get_current_feed_info(
            feed_payload.external_id, feed_payload.source
        )

        # Assertions
        assert feed_id == "feed-uuid"
        assert url == "http://example.com/feed"
        mock_logging.info.assert_called_with(
            f"Retrieved feed TLD-test123 info for external_id: "
            f"{feed_payload.external_id} (status: active)"
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

    def test_check_feed_url_exists(self, processor, mock_logging):
        """Test checking if feed URL already exists."""
        test_url = "https://example.com/feed"

        # Test case: Active feed exists
        mock_feed = Mock(id="test-id", status="active")
        processor.session.query.return_value.filter.return_value.first.return_value = (
            mock_feed
        )

        result = processor.check_feed_url_exists(test_url)
        assert result is True
        mock_logging.info.assert_called_with(
            f"Found existing feed with URL: {test_url} (status: active)"
        )

        # Test case: Deprecated feed exists
        mock_feed.status = "deprecated"
        result = processor.check_feed_url_exists(test_url)
        assert result is True
        mock_logging.error.assert_called_with(
            f"Feed URL {test_url} exists in deprecated feed (id: test-id). "
            "Cannot reuse URLs from deprecated feeds."
        )

        # Test case: No feed exists
        processor.session.query.return_value.filter.return_value.first.return_value = (
            None
        )
        result = processor.check_feed_url_exists(test_url)
        assert result is False
        mock_logging.debug.assert_called_with(
            f"No existing feed found with URL: {test_url}"
        )

    def test_publish_to_batch_topic(self, processor, feed_payload, mock_logging):
        """Test publishing to batch topic."""
        processor.publisher.topic_path.return_value = "test_topic"
        mock_future = Mock()
        processor.publisher.publish.return_value = mock_future

        processor.publish_to_batch_topic(feed_payload)

        # Verify Pub/Sub publish was called
        processor.publisher.publish.assert_called_once()
        mock_logging.info.assert_called_with(
            f"Published feed {feed_payload.feed_id} to dataset batch topic"
        )

    def test_publish_to_batch_topic_error(self, processor, feed_payload, mock_logging):
        """Test Pub/Sub publishing error."""
        processor.publisher.publish.side_effect = Exception("Pub/Sub error")

        with pytest.raises(Exception, match="Pub/Sub error"):
            processor.publish_to_batch_topic(feed_payload)

        mock_logging.error.assert_called_with(
            "Error publishing to dataset batch topic: Pub/Sub error"
        )

    @patch("feed_sync_process_transitland.src.main.start_db_session")
    @patch("feed_sync_process_transitland.src.main.FeedProcessor")
    @patch("feed_sync_process_transitland.src.main.close_db_session")
    def test_process_feed_event_invalid_payload(
        self, close_db_mock, feed_processor_mock, start_db_mock, mock_logging
    ):
        """Test Cloud Function with invalid payload."""
        # Simulate an invalid payload
        cloud_event = Mock()
        cloud_event.data = {
            "message": {
                "data": base64.b64encode("invalid json".encode("utf-8")).decode()
            }
        }

        result = process_feed_event(cloud_event)

        # Assertions
        assert result[1] == 500
        mock_logging.error.assert_called_with(
            "Error processing feed event: Expecting value: line 1 column 1 (char 0)"
        )

    def test_process_feed_error_handling(self, processor, feed_payload, mock_logging):
        """Test error handling during feed processing."""
        processor.session.query.side_effect = SQLAlchemyError("Database error")
        with pytest.raises(SQLAlchemyError):
            processor.process_feed(feed_payload)

        processor.session.rollback.assert_called_once()
        mock_logging.error.assert_any_call(
            f"Database error processing feed {feed_payload.external_id}: "
            "Database error"
        )

        # Reset mocks for the next scenario
        processor.session.reset_mock()
        mock_logging.reset_mock()

        # General exception
        processor.session.query.side_effect = Exception("General error")
        with pytest.raises(Exception):
            processor.process_feed(feed_payload)

        processor.session.rollback.assert_called_once()
        mock_logging.error.assert_any_call(
            f"Error processing feed {feed_payload.external_id}: General error"
        )

    def test_process_feed_update(self, processor, feed_payload, mock_logging):
        """Test updating an existing feed."""
        old_feed_id = "12345678-1234-5678-1234-567812345678"  # Valid UUID format
        new_feed_id = "87654321-4321-8765-4321-876543210000"  # Valid UUID format

        # Create a mock session
        mock_session = MagicMock()

        # Mock the query chain for reference count
        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.count.return_value = 1
        mock_session.query.return_value = mock_query

        # Set up the mock session
        processor.session = mock_session

        # Mock old feed retrieval
        mock_old_feed = MagicMock()
        mock_old_feed.id = old_feed_id
        mock_old_feed.status = "active"
        mock_session.get.return_value = mock_old_feed

        # Create a mock Feed class
        mock_feed = MagicMock()
        mock_feed.locations = []
        mock_feed.externalids = []
        mock_feed.__name__ = "Feed"  # Add __name__ attribute

        # Create a mock Location
        mock_location = MagicMock()
        mock_location.id = "US-CA-Test City"
        mock_location.country_code = "US"
        mock_location.country = "United States"
        mock_location.subdivision_name = "CA"
        mock_location.municipality = "Test City"
        mock_location.feeds = []
        mock_location.__name__ = "Location"  # Add __name__ attribute

        with patch(
            "database_gen.sqlacodegen_models.Feed", return_value=mock_feed
        ), patch(
            "helpers.locations.create_or_get_location", return_value=mock_location
        ), patch(
            "uuid.uuid4", return_value=uuid.UUID(new_feed_id)
        ):
            # Call the method under test
            processor.process_feed_update(feed_payload, old_feed_id)

            # Verify old feed status update
            assert mock_old_feed.status == "deprecated"

            # Verify session operations
            assert (
                mock_session.add.call_count >= 3
            )  # New feed, external ID, and redirect
            mock_session.flush.assert_called_once()

            # Verify logging
            mock_logging.debug.assert_any_call(
                f"Deprecating old feed ID: {old_feed_id}"
            )
            mock_logging.debug.assert_any_call(
                f"Created new external ID mapping for feed_id: {new_feed_id}"
            )
            mock_logging.debug.assert_any_call(
                f"Created redirect from {old_feed_id} to {new_feed_id}"
            )
            mock_logging.info.assert_any_call(
                f"Updated feed for external_id: {feed_payload.external_id}, new feed_id: {new_feed_id}"
            )

    def test_multiple_feed_updates(self, processor, feed_payload, mock_logging):
        """Test handling multiple updates to the same feed."""
        # Setup initial feed state
        old_feed_id = str(uuid.uuid4())
        second_feed_id = str(uuid.uuid4())
        final_feed_id = str(uuid.uuid4())

        # Mock session behaviors
        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.count.side_effect = [1, 2, 3]
        # Simulate increasing reference counts
        processor.session.query.return_value = mock_query

        # Mock existing feeds
        mock_old_feed = MagicMock(id=old_feed_id, status="active")
        processor.session.get.return_value = mock_old_feed

        with patch(
            "uuid.uuid4",
            side_effect=[uuid.UUID(second_feed_id), uuid.UUID(final_feed_id)],
        ):
            # First update
            processor.process_feed_update(feed_payload, old_feed_id)
            assert mock_old_feed.status == "deprecated"
            # Verify first stable_id format
            mock_feed_calls = processor.session.add.call_args_list
            first_feed_call = mock_feed_calls[0][0][0]
            assert (
                first_feed_call.stable_id
                == f"{feed_payload.source}-{feed_payload.external_id}"
            )

            # Second update
            processor.process_feed_update(feed_payload, second_feed_id)
            # Verify second stable_id includes counter
            second_feed_call = processor.session.add.call_args_list[-3][0][0]
            assert (
                second_feed_call.stable_id
                == f"{feed_payload.source}-{feed_payload.external_id}_2"
            )

    def test_publish_to_batch_topic_message_format(
        self, processor, feed_payload, mock_logging
    ):
        """Test the format and content of messages published to batch topic."""
        # Define test_topic before using it
        test_topic = "test_topic"
        # Mock the publisher's topic_path
        processor.publisher.topic_path.return_value = test_topic

        # Mock successful publish
        mock_future = Mock()
        processor.publisher.publish.return_value = mock_future

        # Test case 1: Feed with no authentication
        feed_payload.type = None
        feed_payload.auth_info_url = None
        feed_payload.auth_param_name = None

        processor.publish_to_batch_topic(feed_payload)

        # Get the data that was published
        publish_call = processor.publisher.publish.call_args
        published_data = json.loads(base64.b64decode(publish_call[1]["data"]))

        # Verify the structure and content of the published message
        assert published_data == {
            "execution_id": feed_payload.execution_id,
            "producer_url": feed_payload.feed_url,
            "feed_stable_id": f"{feed_payload.source}-{feed_payload.external_id}",
            "feed_id": feed_payload.feed_id,
            "dataset_id": None,
            "dataset_hash": None,
            "authentication_type": "0",
            "authentication_info_url": None,
            "api_key_parameter_name": None,
        }

        # Test case 2: Feed with authentication
        processor.publisher.reset_mock()
        feed_payload.type = "api_key"
        feed_payload.auth_info_url = "https://auth.example.com"
        feed_payload.auth_param_name = "api_key"

        processor.publish_to_batch_topic(feed_payload)

        # Get the data that was published with auth
        publish_call = processor.publisher.publish.call_args
        published_data = json.loads(base64.b64decode(publish_call[1]["data"]))

        # Verify the structure and content of the authenticated message
        assert published_data == {
            "execution_id": feed_payload.execution_id,
            "producer_url": feed_payload.feed_url,
            "feed_stable_id": f"{feed_payload.source}-{feed_payload.external_id}",
            "feed_id": feed_payload.feed_id,
            "dataset_id": None,
            "dataset_hash": None,
            "authentication_type": "api_key",
            "authentication_info_url": "https://auth.example.com",
            "api_key_parameter_name": "api_key",
        }

        # Verify logging
        mock_logging.debug.assert_any_call(f"Publishing to topic: {test_topic}")
        mock_logging.debug.assert_any_call(
            f"Preparing to publish feed_id: {feed_payload.feed_id}"
        )
        mock_logging.info.assert_called_with(
            f"Published feed {feed_payload.feed_id} to dataset batch topic"
        )

        # Test case 3: Verify empty auth_type becomes "0"
        processor.publisher.reset_mock()
        feed_payload.type = ""  # Empty string

        processor.publish_to_batch_topic(feed_payload)

        publish_call = processor.publisher.publish.call_args
        published_data = json.loads(base64.b64decode(publish_call[1]["data"]))

        assert published_data["authentication_type"] == "0"

    def test_check_feed_url_exists_comprehensive(self, processor, mock_logging):
        """Test comprehensive validation of feed URL existence in different states."""
        test_urls = {
            "active_url": "https://example.com/feed/active",
            "deprecated_url": "https://example.com/feed/deprecated",
            "new_url": "https://example.com/feed/new",
        }

        # Mock feed objects with different statuses
        active_feed = Mock(
            id="active-feed-id",
            producer_url=test_urls["active_url"],
            status="active",
            stable_id="TLD-active",
        )

        deprecated_feed = Mock(
            id="deprecated-feed-id",
            producer_url=test_urls["deprecated_url"],
            status="deprecated",
            stable_id="TLD-deprecated",
        )

        # Setup query mock to return different results based on URL
        def mock_query_filter(*args, **kwargs):
            mock_filter = Mock()
            # Get the URL from the filter arguments
            url = args[0].right.value
            if url == test_urls["active_url"]:
                mock_filter.first.return_value = active_feed
            elif url == test_urls["deprecated_url"]:
                mock_filter.first.return_value = deprecated_feed
            else:
                mock_filter.first.return_value = None
            return mock_filter

        # Apply the mock to the session
        mock_query = Mock()
        mock_query.filter.side_effect = mock_query_filter
        processor.session.query.return_value = mock_query

        # Test Case 1: URL exists in active feed
        result = processor.check_feed_url_exists(test_urls["active_url"])
        assert result is True
        mock_logging.info.assert_any_call(
            f"Found existing feed with URL: {test_urls['active_url']} (status: active)"
        )

        # Reset mock_logging
        mock_logging.reset_mock()

        # Test Case 2: URL exists in deprecated feed
        result = processor.check_feed_url_exists(test_urls["deprecated_url"])
        assert result is True
        mock_logging.error.assert_any_call(
            f"Feed URL {test_urls['deprecated_url']} exists in deprecated feed (id: {deprecated_feed.id}). "
            "Cannot reuse URLs from deprecated feeds."
        )

        # Reset mock_logging
        mock_logging.reset_mock()

        # Test Case 3: New URL that doesn't exist
        result = processor.check_feed_url_exists(test_urls["new_url"])
        assert result is False
        mock_logging.debug.assert_any_call(
            f"No existing feed found with URL: {test_urls['new_url']}"
        )

        # Reset mock_logging
        mock_logging.reset_mock()

        # Test Case 4: Edge case - Empty URL
        result = processor.check_feed_url_exists("")
        assert result is False
        mock_logging.debug.assert_any_call("No existing feed found with URL: ")

        # Test Case 5: Database error during URL check
        processor.session.query.side_effect = SQLAlchemyError(
            "Database connection error"
        )

        with pytest.raises(SQLAlchemyError) as exc_info:
            processor.check_feed_url_exists(test_urls["active_url"])

        assert "Database connection error" in str(exc_info.value)
