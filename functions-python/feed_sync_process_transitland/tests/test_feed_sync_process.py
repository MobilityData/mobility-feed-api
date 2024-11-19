import base64
import json
import uuid
from unittest.mock import Mock, patch, call
import pytest
from google.cloud import pubsub_v1
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.exc import SQLAlchemyError

from feed_sync_process_transitland.src.main import (
    FeedProcessor,
    process_feed_event
)
from helpers.feed_sync.models import TransitFeedSyncPayload as FeedPayload
from database_gen.sqlacodegen_models import Feed, Externalid, Location, Redirectingid


@pytest.fixture
def mock_feed():
    """Fixture for a Feed model instance"""
    return Mock(spec=Feed)


@pytest.fixture
def mock_external_id():
    """Fixture for an ExternalId model instance"""
    return Mock(spec=Externalid)


@pytest.fixture
def mock_location():
    """Fixture for a Location model instance"""
    return Mock(spec=Location)


@pytest.fixture(autouse=True)
def mock_logger():
    with patch("feed_sync_process_transitland.src.main.logger") as mock_log:
        mock_log.info = Mock()
        mock_log.error = Mock()
        mock_log.warning = Mock()
        mock_log.debug = Mock()
        yield mock_log


@pytest.fixture
def mock_publisher():
    """Fixture for PubSub publisher"""
    return Mock(spec=pubsub_v1.PublisherClient)


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


@pytest.fixture
def db_session():
    """Fixture for database session"""
    return Mock(spec=DBSession)


@pytest.fixture
def processor(db_session, mock_publisher):
    """Fixture for FeedProcessor with mocked dependencies"""
    processor = FeedProcessor(db_session)
    processor.publisher = mock_publisher
    return processor


def test_get_current_feed_info(processor, db_session, mock_logger):
    """Test retrieving current feed information"""
    test_external_id = "test123"
    test_source = "TLD"

    mock_feed = Mock(spec=Feed)
    mock_feed.id = "feed-uuid"
    mock_feed.producer_url = "http://example.com/feed"
    mock_feed.stable_id = "TLD-test123"
    mock_feed.status = "active"

    db_session.query.return_value.filter.return_value.first.return_value = mock_feed

    feed_id, url = processor.get_current_feed_info(test_external_id, test_source)

    assert feed_id == mock_feed.id
    assert url == mock_feed.producer_url

    mock_logger.info.assert_called_with(
        f"Retrieved feed {mock_feed.stable_id} info for external_id: {test_external_id} (status: {mock_feed.status})"
    )

    # Test case when feed doesn't exist
    db_session.query.reset_mock()
    mock_logger.info.reset_mock()
    db_session.query.return_value.filter.return_value.first.return_value = None

    feed_id, url = processor.get_current_feed_info(test_external_id, test_source)

    assert feed_id is None
    assert url is None
    mock_logger.info.assert_called_with(
        f"No existing feed found for external_id: {test_external_id}"
    )


def test_check_feed_url_exists(processor, db_session, mock_logger):
    """Test checking if feed URL already exists"""
    test_url = "http://example.com/feed"

    # Test case: Active feed exists
    mock_feed = Mock(spec=Feed)
    mock_feed.id = "test-id"
    mock_feed.status = "active"
    db_session.query.return_value.filter.return_value.first.return_value = mock_feed

    result = processor.check_feed_url_exists(test_url)

    assert result is True
    mock_logger.debug.assert_called_with(
        f"Found existing feed with URL: {test_url} (status: active)"
    )

    # Test case: Deprecated feed exists
    db_session.query.reset_mock()
    mock_logger.debug.reset_mock()
    mock_logger.error.reset_mock()

    mock_feed.status = "deprecated"
    db_session.query.return_value.filter.return_value.first.return_value = mock_feed

    result = processor.check_feed_url_exists(test_url)

    assert result is True
    mock_logger.error.assert_called_with(
        f"Feed URL {test_url} exists in deprecated feed (id: {mock_feed.id}). "
        "Cannot reuse URLs from deprecated feeds."
    )

    # Test case: No feed exists
    db_session.query.reset_mock()
    mock_logger.debug.reset_mock()
    db_session.query.return_value.filter.return_value.first.return_value = None

    result = processor.check_feed_url_exists(test_url)

    assert result is False
    mock_logger.debug.assert_called_with(f"No existing feed found with URL: {test_url}")


@patch("helpers.locations.create_or_get_location")
def test_process_new_feed_with_location(mock_create_location, processor, db_session, feed_payload, mock_logger):
    """Test processing new feed creation with location"""
    feed_id = "12345678-1234-5678-1234-567812345678"
    location_id = "US-CA-Test City"

    # Mock location creation
    mock_location = Mock(spec=Location)
    mock_location.id = location_id
    mock_create_location.return_value = mock_location

    with patch("uuid.uuid4", return_value=uuid.UUID(feed_id)):
        processor.process_new_feed(feed_payload)

        # Verify feed creation
        db_session.add.assert_called()
        db_session.flush.assert_called_once()

        # Verify location handling
        mock_create_location.assert_called_once_with(
            db_session,
            feed_payload.country,
            feed_payload.state_province,
            feed_payload.city_name
        )

        # Verify logging
        expected_debug_logs = [
            call(f"Generated new feed_id: {feed_id} and stable_id: {feed_payload.source}-{feed_payload.external_id}"),
            call(f"Added location information for feed: {feed_id}"),
            call(f"Successfully created feed with ID: {feed_id}")
        ]
        mock_logger.debug.assert_has_calls(expected_debug_logs, any_order=True)


def test_process_feed_update(processor, db_session, feed_payload, mock_logger):
    """Test processing feed updates"""
    old_feed_id = "old-uuid"
    new_feed_id = "12345678-1234-5678-1234-567812345678"

    # Mock reference count query
    db_session.query.return_value.join.return_value.filter.return_value.count.return_value = 2

    with patch("uuid.uuid4", return_value=uuid.UUID(new_feed_id)):
        processor.process_feed_update(feed_payload, old_feed_id)

        # Verify stable_id includes counter
        expected_stable_id = f"{feed_payload.source}-{feed_payload.external_id}_id-3"
        mock_logger.debug.assert_any_call(
            f"Generated new stable_id: {expected_stable_id} (reference count: 2)"
        )

        # Verify external ID creation
        mock_logger.debug.assert_any_call(
            f"Created new external ID mapping for feed_id: {new_feed_id}"
        )


def test_publish_to_batch_topic(processor, feed_payload, mock_logger, mock_publisher):
    """Test publishing to batch topic"""
    test_topic = "test_topic"
    mock_publisher.topic_path.return_value = test_topic
    mock_future = Mock()
    mock_publisher.publish.return_value = mock_future

    # Expected message data
    expected_data = {
        "execution_id": feed_payload.execution_id,
        "producer_url": feed_payload.feed_url,
        "feed_stable_id": f"{feed_payload.source}-{feed_payload.external_id}",
        "feed_id": feed_payload.feed_id,
        "dataset_id": None,
        "dataset_hash": None,
        "authentication_type": "0",
        "authentication_info_url": feed_payload.auth_info_url,
        "api_key_parameter_name": feed_payload.auth_param_name
    }

    processor.publish_to_batch_topic(feed_payload)

    # Verify correct message format and encoding
    json_str = json.dumps(expected_data)
    encoded_data = base64.b64encode(json_str.encode('utf-8'))
    mock_publisher.publish.assert_called_once_with(test_topic, data=encoded_data)

    mock_logger.info.assert_called_with(
        f"Published feed {feed_payload.feed_id} to dataset batch topic"
    )


def test_process_feed_error_handling(processor, db_session, feed_payload, mock_logger):
    """Test error handling during feed processing"""
    # Test SQLAlchemy error
    db_session.query.side_effect = SQLAlchemyError("Database error")

    with pytest.raises(SQLAlchemyError):
        processor.process_feed(feed_payload)

    db_session.rollback.assert_called_once()
    mock_logger.error.assert_any_call(
        f"Database error processing feed {feed_payload.external_id}: Database error"
    )

    # Test general error
    db_session.reset_mock()
    mock_logger.reset_mock()
    db_session.query.side_effect = Exception("General error")

    with pytest.raises(Exception):
        processor.process_feed(feed_payload)

    db_session.rollback.assert_called_once()
    mock_logger.error.assert_any_call(
        f"Error processing feed {feed_payload.external_id}: General error"
    )


@patch("feed_sync_process_transitland.src.main.start_db_session")
@patch("feed_sync_process_transitland.src.main.close_db_session")
def test_process_feed_event(mock_close_db, mock_start_db, processor, feed_payload, mock_logger):
    """Test cloud function entry point"""
    mock_db_session = Mock(spec=DBSession)
    mock_start_db.return_value = mock_db_session

    cloud_event = Mock()
    cloud_event.data = {
        "message": {
            "data": base64.b64encode(json.dumps(feed_payload.__dict__).encode())
        }
    }

    result = process_feed_event(cloud_event)

    assert result == ("Success", 200)
    mock_logger.info.assert_called_with(
        f"Successfully processed feed: {feed_payload.external_id}"
    )
