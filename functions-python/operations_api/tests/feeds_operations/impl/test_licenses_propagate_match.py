import pytest
from fastapi import HTTPException

from feeds_gen.models.propagate_license_request import PropagateLicenseRequest
from feeds_gen.models.propagate_license_response import PropagateLicenseResponse
from feeds_gen.models.propagate_license_affected_feed import (
    PropagateLicenseAffectedFeed,
)
from feeds_operations.impl.licenses_api_impl import LicensesApiImpl
from shared.common.license_utils import (
    PropagateLicenseResult,
    PropagateLicenseAffectedFeedResult,
)
from shared.database.database import Database
from shared.database_gen.sqlacodegen_models import (
    Feed,
    FeedLicenseChange,
)
from test_shared.test_utils.database_utils import default_db_url


LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
LICENSE_ID = "MIT"


@pytest.fixture
def db_session():
    db = Database(feeds_database_url=default_db_url)
    with db.start_db_session() as session:
        yield session


def _make_fake_result(dry_run=True, override=False, affected=None):
    """Build a fake PropagateLicenseResult for mocking."""
    if affected is None:
        affected = []
    return PropagateLicenseResult(
        license_id=LICENSE_ID,
        license_url=LICENSE_URL,
        normalized_license_url="creativecommons.org/licenses/by/4.0",
        dry_run=dry_run,
        override=override,
        total_feeds_with_same_url=len(affected),
        affected_feeds_count=len(affected),
        affected_feeds=affected,
    )


# ---------------------------------------------------------------------------
# Tests for propagate_match_license — happy path (mocked propagation utility)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_propagate_match_license_dry_run_returns_response(monkeypatch):
    """dry_run=True returns a PropagateLicenseResponse without committing."""
    affected = [
        PropagateLicenseAffectedFeedResult(
            feed_id="mdb-10", previous_license_id=None, data_type="gtfs"
        )
    ]
    fake_result = _make_fake_result(dry_run=True, affected=affected)

    monkeypatch.setattr(
        "feeds_operations.impl.licenses_api_impl.propagate_license_by_url",
        lambda **kwargs: fake_result,
    )

    api = LicensesApiImpl()
    request = PropagateLicenseRequest(
        license_id=LICENSE_ID,
        license_url=LICENSE_URL,
        dry_run=True,
        override=False,
    )
    result = await api.propagate_match_license(request)

    assert isinstance(result, PropagateLicenseResponse)
    assert result.dry_run is True
    assert result.license_id == LICENSE_ID
    assert result.affected_feeds_count == 1
    assert isinstance(result.affected_feeds[0], PropagateLicenseAffectedFeed)
    assert result.affected_feeds[0].feed_id == "mdb-10"


@pytest.mark.asyncio
async def test_propagate_match_license_not_dry_run_returns_response(monkeypatch):
    """dry_run=False returns a PropagateLicenseResponse with dry_run=False."""
    fake_result = _make_fake_result(dry_run=False)

    monkeypatch.setattr(
        "feeds_operations.impl.licenses_api_impl.propagate_license_by_url",
        lambda **kwargs: fake_result,
    )

    api = LicensesApiImpl()
    request = PropagateLicenseRequest(
        license_id=LICENSE_ID,
        license_url=LICENSE_URL,
        dry_run=False,
        override=False,
    )
    result = await api.propagate_match_license(request)

    assert isinstance(result, PropagateLicenseResponse)
    assert result.dry_run is False


@pytest.mark.asyncio
async def test_propagate_match_license_invalid_license_id_returns_400(monkeypatch):
    """ValueError from propagate_license_by_url (unknown license_id) → 400."""

    def raise_value_error(**kwargs):
        raise ValueError("License 'BAD' not found")

    monkeypatch.setattr(
        "feeds_operations.impl.licenses_api_impl.propagate_license_by_url",
        raise_value_error,
    )

    api = LicensesApiImpl()
    request = PropagateLicenseRequest(
        license_id="BAD",
        license_url=LICENSE_URL,
        dry_run=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        await api.propagate_match_license(request)

    assert exc_info.value.status_code == 400
    assert "BAD" in exc_info.value.detail


@pytest.mark.asyncio
async def test_propagate_match_license_internal_error_returns_500(monkeypatch):
    """Unexpected exception → 500."""

    def raise_runtime(**kwargs):
        raise RuntimeError("db failure")

    monkeypatch.setattr(
        "feeds_operations.impl.licenses_api_impl.propagate_license_by_url",
        raise_runtime,
    )

    api = LicensesApiImpl()
    request = PropagateLicenseRequest(
        license_id=LICENSE_ID,
        license_url=LICENSE_URL,
        dry_run=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        await api.propagate_match_license(request)

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_propagate_match_license_override_false_returns_only_null_feeds(
    monkeypatch,
):
    """override=False → only feeds with null license_id in affected list."""
    affected = [
        PropagateLicenseAffectedFeedResult(
            feed_id="mdb-20", previous_license_id=None, data_type="gtfs"
        )
    ]
    fake_result = _make_fake_result(dry_run=True, override=False, affected=affected)
    fake_result.total_feeds_with_same_url = 3  # 3 total but only 1 null

    monkeypatch.setattr(
        "feeds_operations.impl.licenses_api_impl.propagate_license_by_url",
        lambda **kwargs: fake_result,
    )

    api = LicensesApiImpl()
    request = PropagateLicenseRequest(
        license_id=LICENSE_ID,
        license_url=LICENSE_URL,
        dry_run=True,
        override=False,
    )
    result = await api.propagate_match_license(request)

    assert result.total_feeds_with_same_url == 3
    assert result.affected_feeds_count == 1
    assert result.affected_feeds[0].previous_license_id is None


@pytest.mark.asyncio
async def test_propagate_match_license_override_true_includes_existing_license_feeds(
    monkeypatch,
):
    """override=True → feeds with existing license_id also appear in affected list."""
    affected = [
        PropagateLicenseAffectedFeedResult(
            feed_id="mdb-30", previous_license_id=None, data_type="gtfs"
        ),
        PropagateLicenseAffectedFeedResult(
            feed_id="mdb-31", previous_license_id="ODbL-1.0", data_type="gtfs_rt"
        ),
    ]
    fake_result = _make_fake_result(dry_run=True, override=True, affected=affected)

    monkeypatch.setattr(
        "feeds_operations.impl.licenses_api_impl.propagate_license_by_url",
        lambda **kwargs: fake_result,
    )

    api = LicensesApiImpl()
    request = PropagateLicenseRequest(
        license_id=LICENSE_ID,
        license_url=LICENSE_URL,
        dry_run=True,
        override=True,
    )
    result = await api.propagate_match_license(request)

    assert result.override is True
    assert result.affected_feeds_count == 2
    ids = [f.feed_id for f in result.affected_feeds]
    assert "mdb-30" in ids and "mdb-31" in ids


# ---------------------------------------------------------------------------
# Integration-style tests against the actual DB (using test fixtures)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_propagate_match_license_db_unknown_license_raises_400(db_session):
    """End-to-end: propagating a non-existent license_id returns 400."""
    api = LicensesApiImpl()
    request = PropagateLicenseRequest(
        license_id="LICENSE-DOES-NOT-EXIST",
        license_url=LICENSE_URL,
        dry_run=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        await api.propagate_match_license(request)

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_propagate_match_license_dry_run_no_db_changes(db_session):
    """dry_run=True should not mutate any feed rows in the database."""
    feed = (
        db_session.query(Feed)
        .filter(
            Feed.license_url == "license_url",
            Feed.operational_status != "unpublished",
        )
        .first()
    )
    if feed is None:
        pytest.skip("No feed with 'license_url' found in test DB")

    before_license_id = feed.license_id

    api = LicensesApiImpl()
    request = PropagateLicenseRequest(
        license_id=LICENSE_ID,
        license_url="license_url",
        dry_run=True,
    )

    result = await api.propagate_match_license(request)

    db_session.expire(feed)
    assert feed.license_id == before_license_id, "dry_run=True must not change the DB"
    assert isinstance(result, PropagateLicenseResponse)


@pytest.mark.asyncio
async def test_propagate_match_license_applies_changes_when_not_dry_run(db_session):
    """dry_run=False updates feeds with null license_id and creates audit rows."""
    # Use the same filter as propagate_license_by_url: operational_status != unpublished
    feed = (
        db_session.query(Feed)
        .filter(
            Feed.license_url == "license_url",
            Feed.license_id.is_(None),
            Feed.operational_status != "unpublished",
        )
        .first()
    )
    if feed is None:
        pytest.skip("No matching feed with null license_id in test DB")

    stable_id = feed.stable_id
    feed_db_id = feed.id

    audit_count_before = (
        db_session.query(FeedLicenseChange)
        .filter(FeedLicenseChange.feed_id == feed_db_id)
        .count()
    )

    api = LicensesApiImpl()
    request = PropagateLicenseRequest(
        license_id=LICENSE_ID,
        license_url="license_url",
        dry_run=False,
        override=False,
    )
    result = await api.propagate_match_license(request)

    db_session.expire_all()

    updated_feed = db_session.query(Feed).filter(Feed.stable_id == stable_id).one()
    assert updated_feed.license_id == LICENSE_ID

    audit_count_after = (
        db_session.query(FeedLicenseChange)
        .filter(FeedLicenseChange.feed_id == feed_db_id)
        .count()
    )
    assert audit_count_after == audit_count_before + 1

    # Verify the audit row details
    audit_row = (
        db_session.query(FeedLicenseChange)
        .filter(
            FeedLicenseChange.feed_id == feed_db_id,
            FeedLicenseChange.matched_license_id == LICENSE_ID,
        )
        .order_by(FeedLicenseChange.changed_at.desc())
        .first()
    )
    assert audit_row is not None
    assert audit_row.match_type == "propagated"
    assert audit_row.matched_source == "propagate_match"
    assert audit_row.verified is True

    # Result should list the feed as affected
    assert any(f.feed_id == stable_id for f in result.affected_feeds)


@pytest.mark.asyncio
async def test_propagate_match_license_override_false_skips_feeds_with_license(
    db_session,
):
    """override=False should not touch feeds that already have a license_id set."""
    feed = (
        db_session.query(Feed)
        .filter(
            Feed.license_url == "license_url",
            Feed.license_id.isnot(None),
            Feed.operational_status != "unpublished",
        )
        .first()
    )
    if feed is None:
        pytest.skip("No feed with existing license_id and 'license_url' in test DB")

    original_license_id = feed.license_id

    api = LicensesApiImpl()
    request = PropagateLicenseRequest(
        license_id=LICENSE_ID,
        license_url="license_url",
        dry_run=False,
        override=False,
    )
    result = await api.propagate_match_license(request)

    db_session.expire(feed)
    assert (
        feed.license_id == original_license_id
    ), "override=False must not change a feed that already has a license_id"
    assert not any(f.feed_id == feed.stable_id for f in result.affected_feeds)
