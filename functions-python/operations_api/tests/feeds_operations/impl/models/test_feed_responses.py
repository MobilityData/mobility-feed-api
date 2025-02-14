# coding: utf-8
#
#   MobilityData 2025
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import pytest
from datetime import datetime
from pydantic import ValidationError
from feeds_operations.impl.models.gtfs_feed_response import GtfsFeedResponse
from feeds_operations.impl.models.gtfs_rt_feed_response import GtfsRtFeedResponse


def test_gtfs_feed_response_creation():
    """Test creating a GtfsFeedResponse with valid data."""
    feed_data = {
        "id": "mdb-123",
        "stable_id": "mdb-123",
        "status": "active",
        "data_type": "gtfs",
        "provider": "Test Provider",
        "feed_name": "Test Feed",
        "operational_status": "wip",
        "created_at": "2024-02-14T12:00:00+00:00",
    }

    feed = GtfsFeedResponse(**feed_data)
    assert feed.id == "mdb-123"
    assert feed.data_type == "gtfs"
    assert feed.operational_status == "wip"
    assert feed.entity_types is None


def test_gtfs_feed_response_optional_fields():
    """Test GtfsFeedResponse with minimal required fields."""
    feed = GtfsFeedResponse()
    assert feed.id is None
    assert feed.stable_id is None
    assert feed.locations is None


def test_gtfs_feed_response_locations():
    """Test GtfsFeedResponse with location data."""
    feed_data = {
        "data_type": "gtfs",
        "locations": [
            {
                "country_code": "US",
                "country": "United States",
                "subdivision_name": "California",
                "municipality": "San Francisco",
            }
        ],
    }

    feed = GtfsFeedResponse(**feed_data)
    assert len(feed.locations) == 1
    assert feed.locations[0]["country_code"] == "US"
    assert feed.locations[0]["municipality"] == "San Francisco"


def test_gtfs_rt_feed_response_creation():
    """Test creating a GtfsRtFeedResponse with valid data including RT-specific fields."""
    feed_data = {
        "id": "mdb-456",
        "stable_id": "mdb-456",
        "status": "active",
        "data_type": "gtfs_rt",
        "provider": "Test Provider RT",
        "feed_name": "Test RT Feed",
        "entity_types": ["vp", "tu"],
        "feed_references": ["mdb-123", "mdb-124"],
    }

    feed = GtfsRtFeedResponse(**feed_data)
    assert feed.id == "mdb-456"
    assert feed.data_type == "gtfs_rt"
    assert set(feed.entity_types) == {"vp", "tu"}
    assert len(feed.feed_references) == 2


def test_gtfs_rt_feed_response_optional_fields():
    """Test GtfsRtFeedResponse with minimal required fields."""
    feed = GtfsRtFeedResponse()
    assert feed.id is None
    assert feed.entity_types is None
    assert feed.feed_references is None


def test_gtfs_rt_feed_response_entity_types():
    """Test GtfsRtFeedResponse entity_types validation."""
    feed_data = {"data_type": "gtfs_rt", "entity_types": ["vp", "tu", "sa"]}

    feed = GtfsRtFeedResponse(**feed_data)
    assert len(feed.entity_types) == 3
    assert all(et in ["vp", "tu", "sa"] for et in feed.entity_types)


def test_feed_response_serialization():
    """Test serialization of both feed response types."""
    gtfs_data = {"id": "mdb-123", "data_type": "gtfs", "provider": "Test Provider"}

    gtfs_rt_data = {
        "id": "mdb-456",
        "data_type": "gtfs_rt",
        "provider": "Test Provider RT",
        "entity_types": ["vp"],
    }

    gtfs_feed = GtfsFeedResponse(**gtfs_data)
    gtfs_rt_feed = GtfsRtFeedResponse(**gtfs_rt_data)

    # Test to_dict() method
    gtfs_dict = gtfs_feed.to_dict()
    assert gtfs_dict["id"] == "mdb-123"
    assert gtfs_dict["data_type"] == "gtfs"

    gtfs_rt_dict = gtfs_rt_feed.to_dict()
    assert gtfs_rt_dict["id"] == "mdb-456"
    assert gtfs_rt_dict["entity_types"] == ["vp"]


def test_feed_response_from_orm():
    """Test creating feed responses from ORM-like objects."""
    current_time = datetime.now().isoformat()

    class MockGtfsFeed:
        id = "mdb-123"
        stable_id = "mdb-123"
        data_type = "gtfs"
        provider = "Test Provider"
        feed_name = "Test Feed"
        status = "active"
        operational_status = "wip"
        created_at = current_time
        locations = []

    class MockGtfsRtFeed:
        id = "mdb-456"
        stable_id = "mdb-456"
        data_type = "gtfs_rt"
        provider = "Test Provider RT"
        feed_name = "Test RT Feed"
        status = "active"
        operational_status = None
        created_at = current_time
        locations = []
        entitytypes = [type("EntityType", (), {"name": "vp"})]
        gtfs_feeds = [type("GtfsFeed", (), {"stable_id": "mdb-123"})]

    gtfs_feed = GtfsFeedResponse.model_validate(MockGtfsFeed())
    assert gtfs_feed.id == "mdb-123"
    assert gtfs_feed.data_type == "gtfs"
    assert gtfs_feed.created_at == current_time

    gtfs_rt_feed = GtfsRtFeedResponse.model_validate(MockGtfsRtFeed())
    assert gtfs_rt_feed.id == "mdb-456"
    assert gtfs_rt_feed.data_type == "gtfs_rt"
    assert gtfs_rt_feed.created_at == current_time


def test_invalid_data_type():
    """Test that invalid data_type values are caught."""
    feed_data = {"id": "mdb-123", "data_type": "invalid"}
    with pytest.raises(ValidationError) as exc_info:
        GtfsFeedResponse(**feed_data)
    assert "data_type must be 'gtfs'" in str(exc_info.value)

    feed_data = {"id": "mdb-456", "data_type": "invalid"}
    with pytest.raises(ValidationError) as exc_info:
        GtfsRtFeedResponse(**feed_data)
    assert "data_type must be 'gtfs_rt'" in str(exc_info.value)


def test_cross_data_type_validation():
    """Test that using wrong feed type is caught."""
    feed_data = {"id": "mdb-123", "data_type": "gtfs_rt"}
    with pytest.raises(ValidationError) as exc_info:
        GtfsFeedResponse(**feed_data)
    assert "data_type must be 'gtfs'" in str(exc_info.value)

    feed_data = {"id": "mdb-456", "data_type": "gtfs"}
    with pytest.raises(ValidationError) as exc_info:
        GtfsRtFeedResponse(**feed_data)
    assert "data_type must be 'gtfs_rt'" in str(exc_info.value)
