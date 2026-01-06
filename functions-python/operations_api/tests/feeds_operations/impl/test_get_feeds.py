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

from feeds_operations.impl.feeds_operations_impl import OperationsApiImpl


@pytest.mark.asyncio
async def test_get_feeds_no_filters():
    """
    Test get_feeds endpoint with no filters applied.
    Should return all feeds with correct pagination values.
    """
    api = OperationsApiImpl()

    response = await api.get_feeds()

    assert response is not None
    assert response.total == 3
    assert response.offset == 0
    assert response.limit == 50
    assert len(response.feeds) == 3

    feed_types = [feed.data_type for feed in response.feeds]
    assert feed_types.count("gtfs") == 2
    assert feed_types.count("gtfs_rt") == 1


@pytest.mark.asyncio
async def test_get_feeds_gtfs_rt_filter():
    """
    Test get_feeds endpoint with GTFS-RT filter.
    Should return only GTFS-RT feeds with their specific fields.
    """
    api = OperationsApiImpl()

    response = await api.get_feeds(data_type="gtfs_rt")

    assert response is not None
    assert response.total == 1
    assert len(response.feeds) == 1

    rt_feed = response.feeds[0]
    assert rt_feed.data_type == "gtfs_rt"
    assert rt_feed.stable_id == "mdb-41"


@pytest.mark.asyncio
async def test_get_feeds_gtfs_filter():
    """
    Test get_feeds endpoint with GTFS filter.
    Should return only GTFS feeds.
    """
    api = OperationsApiImpl()

    response = await api.get_feeds(data_type="gtfs")

    assert response is not None
    assert response.total == 2
    assert len(response.feeds) == 2

    for feed in response.feeds:
        assert feed.data_type == "gtfs"


@pytest.mark.asyncio
async def test_get_feeds_pagination():
    """
    Test get_feeds endpoint with pagination parameters.
    Should correctly handle offset and limit.
    """
    api = OperationsApiImpl()

    response = await api.get_feeds(limit=1)
    assert response.total == 1
    assert response.limit == 1
    assert response.offset == 0
    assert len(response.feeds) == 1
    first_feed = response.feeds[0]

    response = await api.get_feeds(offset=1, limit=1)
    assert response.total == 1
    assert response.limit == 1
    assert response.offset == 1
    assert len(response.feeds) == 1
    assert response.feeds[0].stable_id != first_feed.stable_id

    response = await api.get_feeds(offset=3)
    assert response.total == 0
    assert response.limit == 50
    assert response.offset == 3
    assert len(response.feeds) == 0

    response = await api.get_feeds(limit=10)
    assert response.total == 3
    assert response.limit == 10
    assert response.offset == 0
    assert len(response.feeds) == 3


@pytest.mark.asyncio
async def test_get_feeds_operation_status_filter():
    """
    Test get_feeds endpoint with operation status filter.
    Should return only feeds with matching operational status.
    """
    api = OperationsApiImpl()

    base_response = await api.get_feeds()
    assert base_response is not None

    feeds_by_status = {}
    for feed in base_response.feeds:
        status = feed.operational_status if feed.operational_status else "none"
        feeds_by_status[status] = feeds_by_status.get(status, 0) + 1

    for status in feeds_by_status:
        if status == "none":
            continue

        response = await api.get_feeds(operation_status=status)
        assert response is not None
        assert response.total == feeds_by_status[status]
        assert len(response.feeds) == feeds_by_status[status]

        for feed in response.feeds:
            assert feed.operational_status == status


@pytest.mark.asyncio
async def test_get_feeds_combined_filters():
    """Test get_feeds with multiple filters applied."""
    api = OperationsApiImpl()

    base_response = await api.get_feeds()
    assert base_response is not None
    print(f"\nTotal feeds in database: {len(base_response.feeds)}")

    gtfs_response = await api.get_feeds(data_type="gtfs")
    assert gtfs_response is not None
    print(f"Total GTFS feeds: {len(gtfs_response.feeds)}")
    for feed in gtfs_response.feeds:
        print(f"GTFS Feed: {feed.stable_id}, status: {feed.operational_status}")

    wip_response = await api.get_feeds(operation_status="wip")
    assert wip_response is not None
    print(f"Total WIP feeds: {len(wip_response.feeds)}")
    for feed in wip_response.feeds:
        print(f"WIP Feed: {feed.stable_id}, type: {feed.data_type}")

    response = await api.get_feeds(data_type="gtfs", operation_status="wip")
    assert response is not None
    wip_gtfs_feeds = response.feeds
    print(f"Total WIP GTFS feeds: {len(wip_gtfs_feeds)}")

    assert len(wip_gtfs_feeds) == 0

    response = await api.get_feeds(data_type="gtfs", limit=1, offset=1)
    assert response is not None
    assert len(response.feeds) == 1
    assert response.offset == 1
    assert response.limit == 1
    assert response.feeds[0].data_type == "gtfs"


@pytest.mark.asyncio
async def test_get_feeds_unpublished_status():
    """
    Test get_feeds endpoint with unpublished operational status filter.
    Should return only feeds with unpublished status.
    """
    api = OperationsApiImpl()

    # Test with unpublished status filter
    response = await api.get_feeds(operation_status="unpublished")
    assert response is not None
    for feed in response.feeds:
        assert feed.operational_status == "unpublished"


@pytest.mark.asyncio
async def test_get_feeds_all_operational_statuses():
    """
    Test get_feeds endpoint with all possible operational status values.
    Verifies that each operational status filter works correctly.
    """
    api = OperationsApiImpl()

    # Test each operational status
    for status in ["wip", "published", "unpublished"]:
        response = await api.get_feeds(operation_status=status)
        assert response is not None
        for feed in response.feeds:
            assert feed.operational_status == status


@pytest.mark.asyncio
async def test_get_feeds_unpublished_with_data_type():
    """
    Test get_feeds endpoint with unpublished status and data type filters combined.
    """
    api = OperationsApiImpl()

    gtfs_response = await api.get_feeds(
        operation_status="unpublished", data_type="gtfs"
    )
    assert gtfs_response is not None
    for feed in gtfs_response.feeds:
        assert feed.operational_status == "unpublished"
        assert feed.data_type == "gtfs"

    rt_response = await api.get_feeds(
        operation_status="unpublished", data_type="gtfs_rt"
    )
    assert rt_response is not None
    for feed in rt_response.feeds:
        assert feed.operational_status == "unpublished"
        assert feed.data_type == "gtfs_rt"


@pytest.mark.asyncio
async def test_get_feeds_search_query():
    """
    Test get_feeds endpoint with search query filter.
    Should return only feeds matching the search query.
    """
    api = OperationsApiImpl()

    response = await api.get_feeds(search_query="RT")
    assert response is not None
    assert response.total == 1
    assert len(response.feeds) == 1
    assert response.feeds[0].feed_name == "London Transit Commission(RT"

    response = await api.get_feeds(search_query=" Provider B ")
    assert response is not None
    assert response.total == 1
    assert len(response.feeds) == 1
    assert response.feeds[0].provider == "provider B"

    response = await api.get_feeds(search_query="mdb-41")
    assert response is not None
    assert response.total == 1
    assert len(response.feeds) == 1
    assert response.feeds[0].stable_id == "mdb-41"

    response = await api.get_feeds(search_query="mdb")
    assert response is not None
    assert response.total == 3
    assert len(response.feeds) == 3
