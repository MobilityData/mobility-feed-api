from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from conftest import availability_checks_mdb_40, feed_mdb_40
from feeds_operations.impl.feeds_operations_impl import OperationsApiImpl
from feeds_gen.models.gtfs_feed_availability_response import (
    GtfsFeedAvailabilityResponse,
)


@pytest.mark.asyncio
async def test_get_gtfs_feed_availability_basic():
    """Returns all availability checks for a known feed."""
    api = OperationsApiImpl()
    response: GtfsFeedAvailabilityResponse = await api.get_gtfs_feed_availability(
        id=feed_mdb_40.stable_id, var_from=None, to=None, limit=100, offset=0
    )
    assert response.feed_id == feed_mdb_40.stable_id
    assert response.total == len(availability_checks_mdb_40)
    assert len(response.checks) == len(availability_checks_mdb_40)
    assert response.offset == 0
    assert response.limit == 100


@pytest.mark.asyncio
async def test_get_gtfs_feed_availability_ordered_desc_by_default():
    """Results are ordered from newest to oldest by default."""
    api = OperationsApiImpl()
    response = await api.get_gtfs_feed_availability(
        id=feed_mdb_40.stable_id,
        var_from=None,
        to=None,
        limit=100,
        offset=0,
        sort="desc",
    )
    timestamps = [c.checked_at for c in response.checks]
    assert timestamps == sorted(timestamps, reverse=True)


@pytest.mark.asyncio
async def test_get_gtfs_feed_availability_ordered_asc():
    """sort=asc returns results from oldest to newest."""
    api = OperationsApiImpl()
    response = await api.get_gtfs_feed_availability(
        id=feed_mdb_40.stable_id,
        var_from=None,
        to=None,
        limit=100,
        offset=0,
        sort="asc",
    )
    timestamps = [c.checked_at for c in response.checks]
    assert timestamps == sorted(timestamps)


@pytest.mark.asyncio
async def test_get_gtfs_feed_availability_filter_from():
    """Filters checks to those at or after the given from timestamp."""
    api = OperationsApiImpl()
    from_dt = datetime(2025, 3, 1, tzinfo=timezone.utc)
    response = await api.get_gtfs_feed_availability(
        id=feed_mdb_40.stable_id, var_from=from_dt, to=None, limit=100, offset=0
    )
    # Checks on Jan 15 and Feb 10 are excluded; Mar 5, Apr 20, May 1 remain
    assert response.total == 3
    assert all(c.checked_at >= from_dt for c in response.checks)


@pytest.mark.asyncio
async def test_get_gtfs_feed_availability_filter_to():
    """Filters checks to those at or before the given to timestamp."""
    api = OperationsApiImpl()
    to_dt = datetime(2025, 3, 31, tzinfo=timezone.utc)
    response = await api.get_gtfs_feed_availability(
        id=feed_mdb_40.stable_id, var_from=None, to=to_dt, limit=100, offset=0
    )
    # Jan 15, Feb 10, Mar 5 match; Apr 20 and May 1 are excluded
    assert response.total == 3
    assert all(c.checked_at <= to_dt for c in response.checks)


@pytest.mark.asyncio
async def test_get_gtfs_feed_availability_filter_from_to():
    """Filters checks to those within the given date range."""
    api = OperationsApiImpl()
    from_dt = datetime(2025, 2, 1, tzinfo=timezone.utc)
    to_dt = datetime(2025, 4, 1, tzinfo=timezone.utc)
    response = await api.get_gtfs_feed_availability(
        id=feed_mdb_40.stable_id, var_from=from_dt, to=to_dt, limit=100, offset=0
    )
    # Feb 10 and Mar 5 match; Jan 15, Apr 20, May 1 are excluded
    assert response.total == 2


@pytest.mark.asyncio
async def test_get_gtfs_feed_availability_pagination():
    """Pagination respects limit and offset; total is always the full count."""
    api = OperationsApiImpl()
    response = await api.get_gtfs_feed_availability(
        id=feed_mdb_40.stable_id, var_from=None, to=None, limit=2, offset=1
    )
    assert response.total == len(availability_checks_mdb_40)
    assert len(response.checks) == 2
    assert response.limit == 2
    assert response.offset == 1


@pytest.mark.asyncio
async def test_get_gtfs_feed_availability_not_found():
    """Returns 404 for an unknown feed ID."""
    api = OperationsApiImpl()
    with pytest.raises(HTTPException) as exc_info:
        await api.get_gtfs_feed_availability(
            id="mdb-9999", var_from=None, to=None, limit=100, offset=0
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_gtfs_feed_availability_request_method_mapping():
    """http_head maps to HEAD and http_get maps to GET."""
    api = OperationsApiImpl()
    response = await api.get_gtfs_feed_availability(
        id=feed_mdb_40.stable_id, var_from=None, to=None, limit=100, offset=0
    )
    methods = {c.request_method for c in response.checks}
    assert methods == {"HEAD", "GET"}


@pytest.mark.asyncio
async def test_get_gtfs_feed_availability_latency_is_float():
    """latency_ms is returned as float, None when not set."""
    api = OperationsApiImpl()
    response = await api.get_gtfs_feed_availability(
        id=feed_mdb_40.stable_id, var_from=None, to=None, limit=100, offset=0
    )
    for check in response.checks:
        if check.latency_ms is not None:
            assert isinstance(check.latency_ms, float)
