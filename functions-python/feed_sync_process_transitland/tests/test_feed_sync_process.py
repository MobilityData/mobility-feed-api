import base64
import json
from unittest import mock
from unittest.mock import patch, Mock, MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as DBSession

from shared.database_gen.sqlacodegen_models import Feed, Gtfsfeed
from shared.helpers.feed_sync.models import TransitFeedSyncPayload as FeedPayload

from main import FeedProcessor, process_feed_event


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


@pytest.fixture
def mock_db_session():
    return Mock()


@pytest.fixture
def feed_payload():
    """Fixture for feed payload."""
    return FeedPayload(
        external_id="test123",
        stable_id="feed1",
        feed_id="feed1",
        feed_url="https://example.com",
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

        # Mock the PublisherClient
        with patch("google.cloud.pubsub_v1.PublisherClient") as MockPublisherClient:
            mock_publisher = MockPublisherClient.return_value
            processor = FeedProcessor(mock_session)
            processor.publisher = mock_publisher
            mock_publisher.topic_path = Mock()
            mock_publisher.publish = Mock()

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

    def test_get_current_feed_info(self, processor, feed_payload):
        """Test retrieving current feed information."""
        # Mock database query
        processor.session.query.return_value.filter.return_value.all.return_value = [
            Feed(
                id="feed-uuid",
                producer_url="https://example.com/feed",
                stable_id="TLD-test123",
                status="active",
            )
        ]

        feeds = processor._get_current_feeds(
            feed_payload.external_id, feed_payload.source
        )

        # Assertions
        assert len(feeds) == 1
        feed_id, url = feeds[0].id, feeds[0].producer_url
        assert feed_id == "feed-uuid"
        assert url == "https://example.com/feed"

        # Test case when feed does not exist
        processor.session.query.return_value.filter.return_value.all.return_value = []
        feeds = processor._get_current_feeds(
            feed_payload.external_id, feed_payload.source
        )
        assert len(feeds) == 0

    def test_check_feed_url_exists_comprehensive(self, processor):
        """Test comprehensive feed URL existence checks."""
        test_url = "https://example.com/feed"

        # Test case 1: Active feed exists
        processor.session.query.return_value.filter_by.return_value.count.return_value = (
            1
        )

        result = processor._check_feed_url_exists(test_url)
        assert result is True

    @patch("main.check_url_status")
    def test_database_error_handling(
        self, mock_check_url_status, processor, feed_payload
    ):
        """Test database error handling in different scenarios."""

        mock_check_url_status.return_value = True
        # Test case 1: General database error during feed processing
        processor.session.query.side_effect = SQLAlchemyError("Database error")
        processor._rollback_transaction = MagicMock(return_value=None)
        processor.process_feed(feed_payload)

        processor._rollback_transaction.assert_called_once()

    def test_publish_to_batch_topic_comprehensive(self, processor, feed_payload):
        """Test publishing to batch topic including success, error, and message format validation."""

        # Test case 1: Successful publish with message format validation
        processor.publisher.topic_path.return_value = "test_topic"
        mock_future = Mock()
        processor.publisher.publish.return_value = mock_future

        processor._publish_to_batch_topic_if_needed(
            feed_payload,
            Feed(
                id="test-id",
                authentication_type="0",
                producer_url=feed_payload.feed_url,
                stable_id=f"{feed_payload.source}-{feed_payload.feed_id}".lower(),
            ),
        )

        # Verify publish was called and message format
        topic_arg, message_arg = processor.publisher.publish.call_args
        assert topic_arg == ("test_topic",)
        assert "feed_stable_id" in json.loads(message_arg["data"])
        assert "tld-feed1" == json.loads(message_arg["data"])["feed_stable_id"]

    def test_process_feed_event_validation(self):
        """Test feed event processing with various invalid payloads."""

        # Test case 1: Empty payload
        empty_payload_data = base64.b64encode(json.dumps({}).encode("utf-8")).decode()
        cloud_event = Mock()
        cloud_event.data = {"message": {"data": empty_payload_data}}

        process_feed_event(cloud_event)

        # Test case 2: Invalid field
        invalid_payload_data = base64.b64encode(
            json.dumps({"invalid": "data"}).encode("utf-8")
        ).decode()
        cloud_event.data = {"message": {"data": invalid_payload_data}}

        process_feed_event(cloud_event)

        # Test case 3: Type error
        type_error_payload = {"external_id": 12345, "feed_url": True, "feed_id": None}
        payload_data = base64.b64encode(
            json.dumps(type_error_payload).encode("utf-8")
        ).decode()
        cloud_event.data = {"message": {"data": payload_data}}

        process_feed_event(cloud_event)

    def test_process_feed_event_pubsub_error(
        self, processor, feed_payload, mock_db_session
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
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = []

        process_feed_event(cloud_event, db_session=mock_session)

    def test_process_feed_event_malformed_cloud_event(self):
        """Test feed event processing with malformed cloud event."""
        # Test case 1: Missing message data
        cloud_event = Mock()
        cloud_event.data = {}

        process_feed_event(cloud_event)

        # Test case 2: Invalid base64 data
        cloud_event.data = {"message": {"data": "invalid-base64"}}

        process_feed_event(cloud_event)

    def test_process_feed_event_invalid_json(self):
        """Test handling of invalid JSON in cloud event"""
        # Create invalid base64 encoded JSON
        invalid_json = base64.b64encode(b'{"invalid": "json"').decode()

        cloud_event = Mock()
        cloud_event.data = {"message": {"data": invalid_json}}

        # Process the event
        result = process_feed_event(cloud_event)

        # Verify error handling
        assert result.startswith("Error processing feed event")

    @patch("main.create_new_feed")
    def test_process_new_feed_or_skip(
        self, create_new_feed_mock, processor, feed_payload
    ):
        """Test processing new feed or skipping existing feed."""
        processor._check_feed_url_exists = MagicMock()
        # Test case 1: New feed
        processor._check_feed_url_exists.return_value = False
        processor._process_new_feed_or_skip(feed_payload)
        create_new_feed_mock.assert_called_once()

    @patch("main.create_new_feed")
    def test_process_new_feed_skip(self, create_new_feed_mock, processor, feed_payload):
        """Test processing new feed or skipping existing feed."""
        processor._check_feed_url_exists = MagicMock()
        # Test case 2: Existing feed
        processor._check_feed_url_exists.return_value = True
        processor._process_new_feed_or_skip(feed_payload)
        create_new_feed_mock.assert_not_called()

    @patch("main.create_new_feed")
    def test_process_existing_feed_refs(
        self, create_new_feed_mock, processor, feed_payload
    ):
        """Test processing existing feed references."""
        # 1. Existing feed with same url
        matching_feeds = [
            Gtfsfeed(
                id="feed-uuid",
                producer_url="https://example.com",
                stable_id="TLD-test123",
                status="active",
            )
        ]
        new_feed = processor._process_existing_feed_refs(feed_payload, matching_feeds)
        assert new_feed is None

        # 2. Existing feed with same stable_id
        matching_feeds = [
            Gtfsfeed(
                id="feed-uuid",
                producer_url="https://example.com/different",
                stable_id="tld-feed1",
                status="active",
            )
        ]
        processor.feed_stable_id = "tld-feed1"
        processor._deprecate_old_feed = MagicMock(
            return_value=Feed(
                id="feed-uuid",
                producer_url="https://example.com/different",
                stable_id="tld-feed1_2",
                status="active",
            )
        )
        new_feed = processor._process_existing_feed_refs(feed_payload, matching_feeds)
        assert new_feed is not None

        # 3. No existing feed with same stable_id
        matching_feeds = [
            Gtfsfeed(
                id="feed-uuid",
                producer_url="https://example.com/different",
                stable_id="tld-different",
                status="active",
            )
        ]
        processor.feed_stable_id = "tld-feed1"
        _ = processor._process_existing_feed_refs(feed_payload, matching_feeds)
        create_new_feed_mock.assert_called_once()

    @patch("main.create_new_feed")
    def test_update_feed(self, create_new_feed_mock, processor, feed_payload):
        """Test updating an existing feed."""
        # No matching feed
        processor._deprecate_old_feed(feed_payload, None)
        create_new_feed_mock.assert_called_once()
        # Provided id but no db entity
        processor.session.get.return_value = None
        processor._deprecate_old_feed(feed_payload, "feed-uuid")
        create_new_feed_mock.assert_called()
        # Update existing feed
        returned_feed = Gtfsfeed(
            id="feed-uuid",
            producer_url="https://example.com",
            stable_id="TLD-test123",
            status="active",
        )
        processor.session.get.return_value = returned_feed
        processor._deprecate_old_feed(feed_payload, "feed-uuid")
        assert returned_feed.status == "deprecated"
