from unittest.mock import patch

import pytest
from fastapi import HTTPException

from conftest import feed_mdb_40
from feeds_operations.impl.feeds_operations_impl import OperationsApiImpl
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import GtfsFeedAvailabilityCheck
from shared.helpers.utils import FeedDownloadError, FeedDownloadResult
from shared.helpers.utils import FeedRequestDiagnostics


def _diagnostics(**overrides):
    defaults = dict(
        request_url="https://example.com/gtfs.zip",
        resolved_url="https://example.com/gtfs.zip",
        request_headers={"User-Agent": "agent"},
        response_headers={"Server": "cloudflare"},
        status_code=200,
        latency_ms=120,
        redirect_urls=[],
        content_type="application/zip",
        is_zip=True,
        downloaded_bytes=2038,
    )
    defaults.update(overrides)
    return FeedRequestDiagnostics(**defaults)


@pytest.mark.asyncio
async def test_download_debug_success():
    """Returns the diagnostics of a successful download."""
    api = OperationsApiImpl()
    diagnostics = _diagnostics()
    result = FeedDownloadResult(
        file_hash="abc123", is_zip=True, diagnostics=diagnostics
    )

    with patch(
        "feeds_operations.impl.feeds_operations_impl.download_feed",
        return_value=result,
    ):
        response = api.debug_gtfs_feed_download(id=feed_mdb_40.stable_id)

    assert response.feed_id == feed_mdb_40.stable_id
    assert response.success is True
    assert response.status_code == 200
    assert response.is_zip is True
    assert response.downloaded_bytes == 2038
    assert response.truncated is False
    assert response.response_headers == {"Server": "cloudflare"}


@pytest.mark.asyncio
async def test_download_debug_failure_returns_diagnostics():
    """A failed download returns 200 with the failure detail rather than raising."""
    api = OperationsApiImpl()
    diagnostics = _diagnostics(
        status_code=403,
        content_type="text/html",
        is_zip=False,
        downloaded_bytes=None,
        external_ip="34.1.2.3",
        error_type="ValueError",
        error_message="Invalid HTTP response code: [403]",
    )

    with patch(
        "feeds_operations.impl.feeds_operations_impl.download_feed",
        side_effect=FeedDownloadError("boom", diagnostics),
    ):
        response = api.debug_gtfs_feed_download(id=feed_mdb_40.stable_id)

    assert response.success is False
    assert response.status_code == 403
    assert response.error_type == "ValueError"
    assert response.external_ip == "34.1.2.3"


@pytest.mark.asyncio
async def test_download_debug_truncated_when_capped():
    """A download stopped at the byte cap is reported as truncated."""
    api = OperationsApiImpl()
    result = FeedDownloadResult(
        file_hash=None, is_zip=None, diagnostics=_diagnostics(downloaded_bytes=1024)
    )

    with patch(
        "feeds_operations.impl.feeds_operations_impl.download_feed",
        return_value=result,
    ):
        response = api.debug_gtfs_feed_download(
            id=feed_mdb_40.stable_id, max_bytes=1024
        )

    assert response.truncated is True


@pytest.mark.asyncio
async def test_download_debug_not_found():
    """Returns 404 for an unknown feed ID."""
    api = OperationsApiImpl()
    with pytest.raises(HTTPException) as exc_info:
        api.debug_gtfs_feed_download(id="mdb-9999")
    assert exc_info.value.status_code == 404


@with_db_session
def _count_availability_checks(db_session=None) -> int:
    return db_session.query(GtfsFeedAvailabilityCheck).count()


@pytest.mark.asyncio
async def test_download_debug_does_not_persist():
    """The endpoint stores nothing in gtfs_feed_availability_check."""
    api = OperationsApiImpl()
    result = FeedDownloadResult(
        file_hash="abc123", is_zip=True, diagnostics=_diagnostics()
    )

    before = _count_availability_checks()

    with patch(
        "feeds_operations.impl.feeds_operations_impl.download_feed",
        return_value=result,
    ):
        api.debug_gtfs_feed_download(id=feed_mdb_40.stable_id)

    assert _count_availability_checks() == before
