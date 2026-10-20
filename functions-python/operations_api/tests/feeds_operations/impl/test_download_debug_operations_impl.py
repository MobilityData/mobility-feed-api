import json
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from conftest import feed_mdb_40
from feeds_gen.models.gtfs_feed_download_debug_request import (
    GtfsFeedDownloadDebugRequest,
)
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
        file_hash=None,
        is_zip=None,
        diagnostics=_diagnostics(downloaded_bytes=1024),
        stop_reason="max_bytes",
    )

    with patch(
        "feeds_operations.impl.feeds_operations_impl.download_feed",
        return_value=result,
    ):
        response = api.debug_gtfs_feed_download(
            id=feed_mdb_40.stable_id, max_bytes=1024
        )

    assert response.truncated is True
    assert response.stop_reason == "max_bytes"


@pytest.mark.asyncio
async def test_download_debug_defaults_match_the_nightly_download():
    """No options: whole file, no read timeout, nothing written, bounded by the deadline."""
    api = OperationsApiImpl()
    result = FeedDownloadResult(
        file_hash="abc123", is_zip=True, diagnostics=_diagnostics(), duration_ms=900
    )

    with patch(
        "feeds_operations.impl.feeds_operations_impl.download_feed",
        return_value=result,
    ) as download:
        response = api.debug_gtfs_feed_download(id=feed_mdb_40.stable_id)

    kwargs = download.call_args.kwargs
    assert kwargs["file_path"] is None
    assert kwargs["max_bytes"] is None
    assert kwargs["timeout_seconds"] is None
    assert kwargs["deadline_seconds"] == 480
    assert response.truncated is False
    assert response.stop_reason is None
    assert response.duration_ms == 900


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


@pytest.mark.asyncio
async def test_download_debug_passes_custom_headers():
    """Headers in the request body replace the defaults for the download."""
    api = OperationsApiImpl()
    result = FeedDownloadResult(
        file_hash="abc123", is_zip=True, diagnostics=_diagnostics()
    )
    headers = {"User-Agent": "curl/8.0", "Accept": "*/*"}

    with patch(
        "feeds_operations.impl.feeds_operations_impl.download_feed",
        return_value=result,
    ) as download:
        api.debug_gtfs_feed_download(
            id=feed_mdb_40.stable_id,
            gtfs_feed_download_debug_request=GtfsFeedDownloadDebugRequest(
                headers=headers
            ),
        )

    assert download.call_args.kwargs["headers"] == headers


@pytest.mark.asyncio
async def test_download_debug_without_body_uses_default_headers():
    """No request body leaves header selection to the shared download path."""
    api = OperationsApiImpl()
    result = FeedDownloadResult(
        file_hash="abc123", is_zip=True, diagnostics=_diagnostics()
    )

    with patch(
        "feeds_operations.impl.feeds_operations_impl.download_feed",
        return_value=result,
    ) as download:
        api.debug_gtfs_feed_download(id=feed_mdb_40.stable_id)

    assert download.call_args.kwargs["headers"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers",
    [{"Bad Name": "x"}, {"": "x"}, {"X-Test": "a\r\nX-Injected: b"}],
)
async def test_download_debug_rejects_invalid_headers(headers):
    """Malformed header names and values with line breaks are a 400, not a download."""
    api = OperationsApiImpl()
    with patch("feeds_operations.impl.feeds_operations_impl.download_feed") as download:
        with pytest.raises(HTTPException) as exc_info:
            api.debug_gtfs_feed_download(
                id=feed_mdb_40.stable_id,
                gtfs_feed_download_debug_request=GtfsFeedDownloadDebugRequest(
                    headers=headers
                ),
            )
    assert exc_info.value.status_code == 400
    download.assert_not_called()


def _nightly(headers=None):
    return GtfsFeedDownloadDebugRequest(run_on="nightly_job", headers=headers)


@pytest.mark.asyncio
async def test_nightly_job_queues_a_dry_run():
    """run_on=nightly_job publishes a dry-run message and answers 202."""
    api = OperationsApiImpl()
    with patch(
        "feeds_operations.impl.feeds_operations_impl.DATASET_BATCH_TOPIC", "topic"
    ), patch(
        "feeds_operations.impl.feeds_operations_impl.trigger_dataset_download"
    ) as trigger, patch(
        "feeds_operations.impl.feeds_operations_impl.get_request_context",
        return_value={},
    ), patch(
        "feeds_operations.impl.feeds_operations_impl.download_feed"
    ) as download:
        response = api.debug_gtfs_feed_download(
            id=feed_mdb_40.stable_id,
            gtfs_feed_download_debug_request=_nightly({"User-Agent": "curl/8.0"}),
        )

    assert response.status_code == 202
    body = json.loads(response.body)
    assert body["feed_id"] == feed_mdb_40.stable_id
    assert body["source"] == "dataset_download_dry_run"
    assert body["execution_id"].startswith("download-dry-run")
    download.assert_not_called()
    trigger.assert_called_once()
    assert trigger.call_args.kwargs == {
        "dry_run": True,
        "headers": {"User-Agent": "curl/8.0"},
    }


@pytest.mark.asyncio
async def test_nightly_job_without_topic_is_503():
    """Without a dataset topic nothing would run, so the caller is told."""
    api = OperationsApiImpl()
    with patch(
        "feeds_operations.impl.feeds_operations_impl.DATASET_BATCH_TOPIC", None
    ), patch(
        "feeds_operations.impl.feeds_operations_impl.trigger_dataset_download"
    ) as trigger:
        with pytest.raises(HTTPException) as exc_info:
            api.debug_gtfs_feed_download(
                id=feed_mdb_40.stable_id, gtfs_feed_download_debug_request=_nightly()
            )
    assert exc_info.value.status_code == 503
    trigger.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{"max_bytes": 1024}, {"timeout_seconds": 30}])
async def test_nightly_job_rejects_api_only_options(params):
    """The nightly job has no size cap or timeout to set, so they are refused."""
    api = OperationsApiImpl()
    with patch(
        "feeds_operations.impl.feeds_operations_impl.trigger_dataset_download"
    ) as trigger:
        with pytest.raises(HTTPException) as exc_info:
            api.debug_gtfs_feed_download(
                id=feed_mdb_40.stable_id,
                gtfs_feed_download_debug_request=_nightly(),
                **params,
            )
    assert exc_info.value.status_code == 400
    trigger.assert_not_called()


@pytest.mark.asyncio
async def test_nightly_job_rejects_invalid_headers():
    api = OperationsApiImpl()
    with patch(
        "feeds_operations.impl.feeds_operations_impl.trigger_dataset_download"
    ) as trigger:
        with pytest.raises(HTTPException) as exc_info:
            api.debug_gtfs_feed_download(
                id=feed_mdb_40.stable_id,
                gtfs_feed_download_debug_request=_nightly({"Bad Name": "x"}),
            )
    assert exc_info.value.status_code == 400
    trigger.assert_not_called()
