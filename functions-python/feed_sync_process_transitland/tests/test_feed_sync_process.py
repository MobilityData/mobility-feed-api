import base64
import json
import uuid
from unittest.mock import Mock, patch, call
import pytest
from google.cloud import pubsub_v1
from sqlalchemy.orm import Session as DBSession

from feed_sync_process_transitland.src.main import (
    FeedProcessor,
    FeedPayload,
    process_feed_event,
)


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
        feed_url="http://example.com/feed1",
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
    # Test when feed exists
    db_session.execute.return_value.fetchone.return_value = (
        "feed-uuid",
        "http://example.com/feed",
    )
    feed_id, url = processor.get_current_feed_info("onestop1", "TLD")
    assert feed_id == "feed-uuid"
    assert url == "http://example.com/feed"
    mock_logger.debug.assert_called_with(
        "Retrieved current feed info for external_id: onestop1"
    )

    # Test when feed doesn't exist
    db_session.execute.return_value.fetchone.return_value = None
    feed_id, url = processor.get_current_feed_info("onestop2", "TLD")
    assert feed_id is None
    assert url is None
    mock_logger.debug.assert_called_with(
        "No existing feed found for external_id: onestop2"
    )


def test_check_feed_url_exists(processor, db_session, mock_logger):
    """Test checking if feed URL already exists"""
    test_url = "http://example.com/feed"

    # Test URL exists
    db_session.execute.return_value.fetchone.return_value = (1,)
    assert processor.check_feed_url_exists(test_url) is True
    mock_logger.debug.assert_called_with(f"Found existing feed with URL: {test_url}")

    # Test URL doesn't exist
    db_session.execute.return_value.fetchone.return_value = None
    assert processor.check_feed_url_exists(test_url) is False
    mock_logger.debug.assert_called_with(f"No existing feed found with URL: {test_url}")


def test_process_new_feed(processor, db_session, feed_payload, mock_logger):
    """Test processing new feed creation"""
    feed_id = "12345678-1234-5678-1234-567812345678"

    # We need to patch both uuid and check_feed_url_exists
    with patch("uuid.uuid4", return_value=uuid.UUID(feed_id)), patch.object(
        processor, "check_feed_url_exists", return_value=False
    ):
        processor.process_new_feed(feed_payload)

        # Verify database operations
        assert db_session.execute.call_count == 2

        # Verify the specific calls
        execute_calls = db_session.execute.call_args_list
        assert len(execute_calls) == 2

        # First call should be inserting into feed table
        feed_query = execute_calls[0][0][0].text
        assert "INSERT INTO public.feed" in feed_query

        # Second call should be inserting into externalid table
        external_id_query = execute_calls[1][0][0].text
        assert "INSERT INTO public.externalid" in external_id_query

        # Verify logging sequence
        expected_logs = [
            # Initial log
            call(
                f"Starting new feed creation for external_id: {feed_payload.external_id}"
            ),
            # Final success log
            call(
                f"Created new feed with ID: {feed_id} for external_id: {feed_payload.external_id}"
            ),
        ]

        expected_debug_logs = [
            call(
                f"Generated new feed_id: {feed_id} and stable_id: {feed_payload.source}-{feed_payload.external_id}"
            ),
            call(f"Successfully inserted new feed record for feed_id: {feed_id}"),
            call(f"Successfully created external ID mapping for feed_id: {feed_id}"),
        ]

        # Check that all expected logs were made
        mock_logger.info.assert_has_calls(expected_logs, any_order=False)
        mock_logger.debug.assert_has_calls(expected_debug_logs, any_order=False)


def test_process_feed_update(processor, db_session, feed_payload, mock_logger):
    """Test processing feed updates"""
    old_feed_id = "old-uuid"
    new_feed_id = "12345678-1234-5678-1234-567812345678"

    with patch("uuid.uuid4", return_value=uuid.UUID(new_feed_id)):
        processor.process_feed_update(feed_payload, old_feed_id)

        # Verify logging
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
    processor.check_feed_url_exists.assert_called_once_with("http://example.com/feed1")
    processor.process_new_feed.assert_called_once_with(feed_payload)
    processor.publish_to_batch_topic.assert_called_once_with(feed_payload)
    db_session.commit.assert_called_once()

    # Verify logging
    mock_logger.info.assert_called_with("Processing new feed")


def test_process_feed_update_full(processor, db_session, feed_payload, mock_logger):
    """Test processing a feed update"""
    # Setup mocks for update scenario
    processor.get_current_feed_info = Mock(
        return_value=("old-uuid", "http://example.com/old")
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
        return_value=("existing-uuid", "http://example.com/feed1")
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
            "feed_url": "http://example.com/feed1",
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
