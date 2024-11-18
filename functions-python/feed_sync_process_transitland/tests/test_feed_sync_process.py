import base64
import json
import uuid
from unittest.mock import Mock, patch, call
import pytest
from google.cloud import pubsub_v1
from sqlalchemy.orm import Session as DBSession
from freezegun import freeze_time


from feed_sync_process_transitland.src.main import (
    FeedProcessor,
    FeedPayload,
    process_feed_event,
)
from database_gen.sqlacodegen_models import Feed, Externalid


@pytest.fixture
def mock_feed():
    """Fixture for a Feed model instance"""
    return Mock(spec=Feed)


@pytest.fixture
def mock_external_id():
    """Fixture for an ExternalId model instance"""
    return Mock(spec=Externalid)


@pytest.fixture(autouse=True)
def mock_logger():
    with patch("feed_sync_process_transitland.src.main.logger") as mock_log:
        mock_log.info = Mock()
        mock_log.error = Mock()
        mock_log.warning = Mock()
        mock_log.debug = Mock()
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
        country="USA",
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
def processor(db_session):
    """Fixture for FeedProcessor with mocked dependencies"""
    return FeedProcessor(db_session)


def test_get_current_feed_info(processor, db_session, mock_logger):
    """Test retrieving current feed information"""
    test_external_id = "test123"
    test_source = "TLD"

    expected_feed_id = "feed-uuid"
    expected_url = "http://example.com/feed"

    db_session.query.return_value.join.return_value.filter.return_value.first.return_value = (
        expected_feed_id,
        expected_url,
    )

    feed_id, url = processor.get_current_feed_info(test_external_id, test_source)
    # Test Case 1: Feed exist
    assert feed_id == expected_feed_id
    assert url == expected_url

    mock_logger.debug.assert_called_with(
        f"Retrieved current feed info for external_id: {test_external_id}"
    )

    # Test Case 2: Feed does not exist
    db_session.query.reset_mock()
    mock_logger.debug.reset_mock()

    db_session.query.return_value.join.return_value.filter.return_value.first.return_value = (
        None
    )

    feed_id, url = processor.get_current_feed_info(test_external_id, test_source)

    assert feed_id is None
    assert url is None

    mock_logger.debug.assert_called_with(
        f"No existing feed found for external_id: {test_external_id}"
    )


def test_check_feed_url_exists(processor, db_session, mock_logger):
    """Test checking if feed URL already exists"""
    test_url = "http://example.com/feed"

    # Test Case 1: Feed exists
    # Mock the query chain
    mock_result = Mock(spec=Feed)
    db_session.query.return_value.filter.return_value.first.return_value = mock_result

    result = processor.check_feed_url_exists(test_url)

    # Verify the method called the database correctly
    db_session.query.assert_called_once_with(Feed)

    # Verify result and logging
    assert result is True
    mock_logger.debug.assert_called_with(f"Found existing feed with URL: {test_url}")

    # Reset mocks for second test
    db_session.query.reset_mock()
    mock_logger.debug.reset_mock()

    # Test Case 2: Feed doesn't exist
    db_session.query.return_value.filter.return_value.first.return_value = None
    result = processor.check_feed_url_exists(test_url)

    # Verify the method called the database correctly
    db_session.query.assert_called_once_with(Feed)

    # Verify result and logging
    assert result is False
    mock_logger.debug.assert_called_with(f"No existing feed found with URL: {test_url}")


def test_process_new_feed(processor, db_session, feed_payload, mock_logger, mock_feed):
    """Test processing new feeds creation"""
    feed_id = "12345678-1234-5678-1234-567812345678"
    frozen_datetime = "2024-01-01 00:00:00"

    mock_feed = Mock(spec=Feed)
    mock_feed.id = feed_id
    mock_feed.externalids = []

    mock_external_id = Mock(spec=Externalid)
    mock_external_id.feed_id = feed_id
    mock_external_id.associated_id = feed_payload.external_id
    mock_external_id.source = feed_payload.source

    with freeze_time(frozen_datetime), patch(
        "uuid.uuid4", return_value=uuid.UUID(feed_id)
    ), patch.object(processor, "check_feed_url_exists", return_value=False), patch(
        "feed_sync_process_transitland.src.main.Feed", return_value=mock_feed
    ), patch(
        "feed_sync_process_transitland.src.main.Externalid",
        return_value=mock_external_id,
    ):
        processor.process_new_feed(feed_payload)

        db_session.add.assert_called_once()
        db_session.flush.assert_called_once()

        feed_creation_call = db_session.add.call_args_list[0]
        created_feed = feed_creation_call[0][0]

        assert created_feed == mock_feed
        assert created_feed.id == feed_id
        assert len(created_feed.externalids) == 1
        assert created_feed.externalids[0] == mock_external_id

        expected_info_logs = [
            call(
                f"Starting new feed creation for external_id: {feed_payload.external_id}"
            ),
            call(
                f"Created new feed with ID: {feed_id} for external_id: {feed_payload.external_id}"
            ),
        ]

        expected_debug_logs = [
            call(
                f"Generated new feed_id: {feed_id} and stable_id: {feed_payload.source}-{feed_payload.external_id}"
            ),
            call(f"Successfully created feed with ID: {feed_id}"),
        ]
        mock_logger.info.assert_has_calls(expected_info_logs, any_order=False)
        mock_logger.debug.assert_has_calls(expected_debug_logs, any_order=False)


def test_process_feed_update(processor, db_session, feed_payload, mock_logger):
    """Test processing feed updates"""
    old_feed_id = "old-uuid"
    new_feed_id = "12345678-1234-5678-1234-567812345678"

    with patch("uuid.uuid4", return_value=uuid.UUID(new_feed_id)):
        processor.process_feed_update(feed_payload, old_feed_id)

        mock_logger.info.assert_called_with(
            f"Updated feed for external_id: {feed_payload.external_id}, new feed_id: {new_feed_id}"
        )
        mock_logger.debug.assert_any_call(f"Deprecating old feed ID: {old_feed_id}")


def test_process_feed_full(processor, db_session, feed_payload, mock_logger):
    """Test full feed processing flow"""
    # Setup mocks for new feed scenario
    processor.get_current_feed_info = Mock(return_value=(None, None))
    processor.check_feed_url_exists = Mock(return_value=False)
    processor.process_new_feed = Mock()
    processor.publish_to_batch_topic = Mock()

    processor.process_feed(feed_payload)

    processor.get_current_feed_info.assert_called_once_with("onestop1", "TLD")
    processor.check_feed_url_exists.assert_called_once_with("https://example.com/feed1")
    processor.process_new_feed.assert_called_once_with(feed_payload)
    processor.publish_to_batch_topic.assert_called_once_with(feed_payload)
    db_session.commit.assert_called_once()

    # Verify logging
    mock_logger.info.assert_called_with("Processing new feed")


def test_process_feed_update_full(processor, db_session, feed_payload, mock_logger):
    """Test processing a feed update"""
    # Setup mocks for update scenario
    processor.get_current_feed_info = Mock(
        return_value=("old-uuid", "https://example.com/old")
    )
    processor.process_feed_update = Mock()
    processor.publish_to_batch_topic = Mock()

    processor.process_feed(feed_payload)

    mock_logger.info.assert_called_with("Processing feed update")
    mock_logger.debug.assert_any_call(
        "Found existing feed: old-uuid with different URL"
    )


def test_process_feed_no_change(processor, db_session, feed_payload, mock_logger):
    """Test processing a feed with no changes needed"""
    processor.get_current_feed_info = Mock(
        return_value=("existing-uuid", "https://example.com/feed1")
    )
    processor.process_feed_update = Mock()
    processor.publish_to_batch_topic = Mock()

    processor.process_feed(feed_payload)

    processor.process_feed_update.assert_not_called()
    processor.publish_to_batch_topic.assert_not_called()
    db_session.commit.assert_not_called()

    # Verify logging
    mock_logger.info.assert_called_with(
        f"Feed already exists with same URL: {feed_payload.external_id}"
    )


def test_process_feed_error_handling(processor, db_session, feed_payload, mock_logger):
    """Test error handling during feed processing"""
    # Setup mock to raise an exception
    error_msg = "Database error"
    processor.get_current_feed_info = Mock(side_effect=Exception(error_msg))

    # Process feed and verify error handling
    with pytest.raises(Exception):
        processor.process_feed(feed_payload)

    db_session.rollback.assert_called_once()
    mock_logger.error.assert_called_with(
        f"Error processing feed {feed_payload.external_id}: {error_msg}"
    )


def test_publish_to_batch_topic(processor, feed_payload, mock_logger):
    """Test publishing to batch topic"""
    mock_publisher = Mock(spec=pubsub_v1.PublisherClient)
    processor.publisher = mock_publisher
    mock_future = Mock()
    mock_publisher.publish.return_value = mock_future

    test_topic = "test_topic"
    mock_publisher.topic_path.return_value = test_topic

    processor.publish_to_batch_topic(feed_payload)

    # Verify logging sequence
    mock_logger.info.assert_called_with(
        f"Published feed {feed_payload.feed_id} to dataset batch topic"
    )


def test_publish_to_batch_topic_error(processor, feed_payload, mock_logger):
    """Test error handling in batch topic publishing"""
    mock_publisher = Mock(spec=pubsub_v1.PublisherClient)
    processor.publisher = mock_publisher
    error_msg = "Publishing error"
    mock_publisher.publish.side_effect = Exception(error_msg)

    with pytest.raises(Exception) as exc_info:
        processor.publish_to_batch_topic(feed_payload)

    assert (
        str(exc_info.value) == f"Error publishing to dataset batch topic: {error_msg}"
    )
    mock_logger.error.assert_called_with(
        f"Error publishing to dataset batch topic: {error_msg}"
    )


def test_process_feed_event_success(mock_logger):
    """Test successful Cloud Function execution"""
    # Mock necessary dependencies
    with patch(
        "feed_sync_process_transitland.src.main.start_db_session"
    ) as mock_start_db, patch(
        "feed_sync_process_transitland.src.main.close_db_session"
    ), patch(
        "feed_sync_process_transitland.src.main.FeedProcessor"
    ):
        # Setup mock database session
        mock_db_session = Mock(spec=DBSession)
        mock_start_db.return_value = mock_db_session

        # Create mock cloud event with valid payload
        test_payload = {
            "external_id": "test1",
            "feed_id": "feed1",
            "feed_url": "https://example.com/feed1",
            "execution_id": "exec123",
            "spec": "gtfs",
            "auth_info_url": None,
            "auth_param_name": None,
            "type": None,
            "operator_name": "Test Operator",
            "country": "USA",
            "state_province": "CA",
            "city_name": "Test City",
            "source": "TLD",
            "payload_type": "new",
        }
        feed_payload = FeedPayload(**test_payload)
        cloud_event = Mock()
        cloud_event.data = {
            "message": {
                "data": base64.b64encode(json.dumps(feed_payload.__dict__).encode())
            }
        }

        # Process event
        result = process_feed_event(cloud_event)

        # Verify result and logging
        assert result == ("Success", 200)
        mock_logger.info.assert_called_with(
            f"Successfully processed feed: {feed_payload.external_id}"
        )


def test_process_feed_event_error(mock_logger):
    """Test error handling in Cloud Function entry point"""
    with patch("feed_sync_process_transitland.src.main.start_db_session"):
        cloud_event = Mock()
        cloud_event.data = {
            "message": {"data": base64.b64encode("invalid json".encode("utf-8"))}
        }

        # Process event
        result = process_feed_event(cloud_event)

        # Verify error handling
        assert result[1] == 500
        assert "Error processing feed event" in result[0]

        assert mock_logger.error.called
        error_msg = mock_logger.error.call_args[0][0]
        assert "Error processing feed event" in error_msg
