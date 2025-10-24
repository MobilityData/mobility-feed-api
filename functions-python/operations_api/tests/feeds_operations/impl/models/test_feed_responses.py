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

from datetime import datetime

from feeds_operations.impl.models.operation_gtfs_feed_impl import OperationGtfsFeedImpl
from feeds_operations.impl.models.operation_gtfs_rt_feed_impl import (
    OperationGtfsRtFeedImpl,
)


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

    feed = OperationGtfsFeedImpl(**feed_data)
    assert feed.id == "mdb-123"
    assert feed.data_type == "gtfs"
    assert feed.operational_status == "wip"

    feed_dict = feed.model_dump()
    assert "entity_types" not in feed_dict
    assert "feed_references" not in feed_dict


def test_gtfs_feed_response_optional_fields():
    """Test GtfsFeedResponse with minimal required fields."""
    feed = OperationGtfsFeedImpl()
    assert feed.id is None
    assert feed.stable_id is None
    assert feed.locations == []


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

    feed = OperationGtfsFeedImpl(**feed_data)
    assert len(feed.locations) == 1
    assert feed.locations[0].country_code == "US"
    assert feed.locations[0].municipality == "San Francisco"


def test_gtfs_rt_feed_response_optional_fields():
    """Test GtfsRtFeedResponse with minimal required fields."""
    feed = OperationGtfsRtFeedImpl()
    assert feed.id is None
    assert feed.entity_types == []
    assert feed.feed_references == []


def test_gtfs_rt_feed_response_entity_types():
    """Test GtfsRtFeedResponse entity_types validation."""
    feed_data = {"data_type": "gtfs_rt", "entity_types": ["vp", "tu", "sa"]}

    feed = OperationGtfsRtFeedImpl(**feed_data)
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

    gtfs_feed = OperationGtfsFeedImpl(**gtfs_data)
    gtfs_rt_feed = OperationGtfsRtFeedImpl(**gtfs_rt_data)

    gtfs_dict = gtfs_feed.to_dict()
    assert gtfs_dict["id"] == "mdb-123"
    assert gtfs_dict["data_type"] == "gtfs"

    gtfs_rt_dict = gtfs_rt_feed.to_dict()
    assert gtfs_rt_dict["id"] == "mdb-456"
    assert gtfs_rt_dict["entity_types"] == ["vp"]


def test_feed_response_from_orm():
    """Test creating feed responses from ORM-like objects."""
    current_time = datetime.now()
    current_time_str = current_time.isoformat()

    gtfs_feed_data = {
        "id": "mdb-123",
        "stable_id": "mdb-123",
        "data_type": "gtfs",
        "provider": "Test Provider",
        "feed_name": "Test Feed",
        "status": "active",
        "operational_status": "wip",
        "created_at": current_time_str,
        "locations": [],
        "official": False,
        "note": None,
        "feed_contact_email": None,
        "producer_url": None,
        "authentication_type": None,
        "authentication_info_url": None,
        "api_key_parameter_name": None,
        "license_url": None,
    }

    gtfs_rt_feed_data = {
        "id": "mdb-456",
        "stable_id": "mdb-456",
        "data_type": "gtfs_rt",
        "provider": "Test Provider RT",
        "feed_name": "Test RT Feed",
        "status": "active",
        "operational_status": None,
        "created_at": current_time_str,
        "locations": [],
        "official": False,
        "note": None,
        "feed_contact_email": None,
        "producer_url": None,
        "authentication_type": None,
        "authentication_info_url": None,
        "api_key_parameter_name": None,
        "license_url": None,
        "entity_types": ["vp"],
        "feed_references": ["mdb-123"],
    }

    gtfs_feed = OperationGtfsFeedImpl.model_validate(gtfs_feed_data)
    assert gtfs_feed.id == "mdb-123"
    assert gtfs_feed.data_type == "gtfs"
    assert isinstance(gtfs_feed.created_at, datetime)
    assert gtfs_feed.created_at.isoformat() == current_time_str

    gtfs_rt_feed = OperationGtfsRtFeedImpl.model_validate(gtfs_rt_feed_data)
    assert gtfs_rt_feed.id == "mdb-456"
    assert gtfs_rt_feed.data_type == "gtfs_rt"
    assert isinstance(gtfs_rt_feed.created_at, datetime)
    assert gtfs_rt_feed.created_at.isoformat() == current_time_str
    assert gtfs_rt_feed.entity_types == ["vp"]
    assert gtfs_rt_feed.feed_references == ["mdb-123"]
