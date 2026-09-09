import pytest
from fastapi import HTTPException
from starlette.responses import Response
from unittest.mock import patch

from conftest import feed_mdb_40
from feeds_operations.impl.feeds_operations_impl import OperationsApiImpl
from feeds_gen.models.external_id import ExternalId
from feeds_gen.models.feed_status import FeedStatus
from feeds_gen.models.source_info import SourceInfo
from feeds_gen.models.update_request_gtfs_feed import UpdateRequestGtfsFeed
from shared.database.database import Database
from shared.database_gen.sqlacodegen_models import Gtfsfeed
from test_shared.test_utils.database_utils import default_db_url


@pytest.fixture
def update_request_gtfs_feed():
    return UpdateRequestGtfsFeed(
        id=feed_mdb_40.id,
        status=FeedStatus(feed_mdb_40.status.lower()),
        external_ids=[],
        provider=feed_mdb_40.provider,
        feed_name=feed_mdb_40.feed_name,
        note=feed_mdb_40.note,
        feed_contact_email=feed_mdb_40.feed_contact_email,
        source_info=SourceInfo(
            producer_url=feed_mdb_40.producer_url,
            authentication_type=int(feed_mdb_40.authentication_type),
            authentication_info_url=feed_mdb_40.authentication_info_url,
            api_key_parameter_name=feed_mdb_40.api_key_parameter_name,
            license_url=feed_mdb_40.license_url,
            license_id=feed_mdb_40.license_id,
            license_notes=feed_mdb_40.license_notes,
            license_is_spdx=True,
        ),
        redirects=[],
        official=True,
    )


@pytest.fixture
def db_session():
    # Provide a database session fixture
    db = Database(feeds_database_url=default_db_url)
    with db.start_db_session() as session:
        yield session


@pytest.mark.asyncio
@patch("feeds_operations.impl.feeds_operations_impl.create_web_revalidation_task")
async def test_update_gtfs_feed_no_changes(mock_revalidation, update_request_gtfs_feed):
    api = OperationsApiImpl()
    response: Response = api.update_gtfs_feed(update_request_gtfs_feed)
    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.usefixtures("update_request_gtfs_feed", "db_session")
@patch("feeds_operations.impl.feeds_operations_impl.create_web_revalidation_task")
async def test_update_gtfs_feed_field_change(
    mock_revalidation, update_request_gtfs_feed, db_session
):
    update_request_gtfs_feed.feed_name = "New feed name"
    update_request_gtfs_feed.external_ids = [
        ExternalId(
            external_id="new_external_id",
            source="new_source",
        )
    ]
    api = OperationsApiImpl()
    response: Response = api.update_gtfs_feed(update_request_gtfs_feed)
    assert response.status_code == 200

    db_feed = (
        db_session.query(Gtfsfeed)
        .filter(Gtfsfeed.stable_id == feed_mdb_40.stable_id)
        .one()
    )
    assert db_feed.feed_name == "New feed name"


@pytest.mark.asyncio
@pytest.mark.usefixtures("update_request_gtfs_feed", "db_session")
@patch("feeds_operations.impl.feeds_operations_impl.create_web_revalidation_task")
async def test_update_gtfs_feed_set_wip(
    mock_revalidation, update_request_gtfs_feed, db_session
):
    update_request_gtfs_feed.operational_status = "wip"
    api = OperationsApiImpl()
    response: Response = api.update_gtfs_feed(update_request_gtfs_feed)
    assert response.status_code == 200

    db_feed = (
        db_session.query(Gtfsfeed)
        .filter(Gtfsfeed.stable_id == feed_mdb_40.stable_id)
        .one()
    )
    assert db_feed.operational_status == "wip"


@pytest.mark.asyncio
@pytest.mark.usefixtures("update_request_gtfs_feed", "db_session")
async def test_update_gtfs_feed_omitted_operational_status_is_preserved(
    update_request_gtfs_feed, db_session
):
    """Omitting `operational_status` leaves the stored value alone and reports no change.

    This replaces the old `operational_status_action="no_change"` sentinel: absence now
    carries that meaning, the same tri-state contract `seasonal` uses.
    """
    assert update_request_gtfs_feed.operational_status is None
    api = OperationsApiImpl()
    response: Response = api.update_gtfs_feed(update_request_gtfs_feed)
    assert response.status_code == 204

    db_feed = (
        db_session.query(Gtfsfeed)
        .filter(Gtfsfeed.stable_id == feed_mdb_40.stable_id)
        .one()
    )
    assert db_feed.operational_status == "wip"


@pytest.mark.asyncio
@pytest.mark.usefixtures("update_request_gtfs_feed", "db_session")
@patch("feeds_operations.impl.feeds_operations_impl.create_web_revalidation_task")
async def test_update_gtfs_feed_set_published(
    mock_revalidation, update_request_gtfs_feed, db_session
):
    update_request_gtfs_feed.operational_status = "published"
    api = OperationsApiImpl()
    response: Response = api.update_gtfs_feed(update_request_gtfs_feed)
    assert response.status_code == 200

    db_feed = (
        db_session.query(Gtfsfeed)
        .filter(Gtfsfeed.stable_id == feed_mdb_40.stable_id)
        .one()
    )
    assert db_feed.operational_status == "published"


@pytest.mark.asyncio
@pytest.mark.usefixtures("update_request_gtfs_feed", "db_session")
@patch("feeds_operations.impl.feeds_operations_impl.create_web_revalidation_task")
async def test_update_gtfs_feed_set_unpublished(
    mock_revalidation, update_request_gtfs_feed, db_session
):
    update_request_gtfs_feed.operational_status = "unpublished"
    api = OperationsApiImpl()
    response: Response = api.update_gtfs_feed(update_request_gtfs_feed)
    assert response.status_code == 200

    db_feed = (
        db_session.query(Gtfsfeed)
        .filter(Gtfsfeed.stable_id == feed_mdb_40.stable_id)
        .one()
    )
    assert db_feed.operational_status == "unpublished"


@pytest.mark.asyncio
async def test_update_gtfs_feed_invalid_feed(update_request_gtfs_feed):
    update_request_gtfs_feed.id = "invalid"
    api = OperationsApiImpl()
    with pytest.raises(HTTPException) as exc_info:
        api.update_gtfs_feed(update_request_gtfs_feed)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Feed ID not found: invalid"


@pytest.mark.asyncio
async def test_update_gtfs_feed_official_field(update_request_gtfs_feed, db_session):
    """Test updating the official field of a GTFS feed."""
    update_request_gtfs_feed.official = True
    api = OperationsApiImpl()
    response: Response = api.update_gtfs_feed(update_request_gtfs_feed)
    assert response.status_code == 204

    db_feed = (
        db_session.query(Gtfsfeed)
        .filter(Gtfsfeed.stable_id == feed_mdb_40.stable_id)
        .one()
    )
    assert db_feed.official is True


@pytest.mark.asyncio
@patch("feeds_operations.impl.feeds_operations_impl.create_web_revalidation_task")
async def test_update_gtfs_feed_seasonal_field(
    mock_revalidation, update_request_gtfs_feed, db_session
):
    """An explicit `seasonal` in the request is persisted."""
    # Establish a known pre-state so toggling `seasonal` to True is a genuine change
    # regardless of test ordering (the row is shared across this module).
    seeded_feed = (
        db_session.query(Gtfsfeed)
        .filter(Gtfsfeed.stable_id == feed_mdb_40.stable_id)
        .one()
    )
    seeded_feed.seasonal = False
    db_session.commit()

    update_request_gtfs_feed.seasonal = True
    api = OperationsApiImpl()
    response: Response = api.update_gtfs_feed(update_request_gtfs_feed)
    assert response.status_code == 200

    db_session.expire_all()
    db_feed = (
        db_session.query(Gtfsfeed)
        .filter(Gtfsfeed.stable_id == feed_mdb_40.stable_id)
        .one()
    )
    assert db_feed.seasonal is True


@pytest.mark.asyncio
@patch("feeds_operations.impl.feeds_operations_impl.create_web_revalidation_task")
async def test_update_gtfs_feed_omitted_seasonal_is_preserved(
    mock_revalidation, update_request_gtfs_feed, db_session
):
    """A request that never mentions `seasonal` must not clear it.

    Clients generated from a spec predating the field send no `seasonal` at all. While the
    property carried `default: false`, that omission reset an operator-set flag on the next
    edit of any other field -- which would silently un-mark the TDG/ODPT/JBDA feeds this
    issue exists to mark. The no-phantom-change half of the fix is pinned in
    test_detect_changes.py, which does not depend on this shared row's state.
    """
    seeded_feed = (
        db_session.query(Gtfsfeed)
        .filter(Gtfsfeed.stable_id == feed_mdb_40.stable_id)
        .one()
    )
    seeded_feed.seasonal = True
    db_session.commit()

    # Drive an unrelated edit by making the STORED note stale, rather than by changing the
    # request. The write then restores `note` to its fixture value, so this test leaves the
    # module-shared row exactly as it found it (sibling tests assert on feed_name/provider).
    seeded_feed.note = "stale note"
    db_session.commit()

    # The fixture never sets `seasonal`; that is exactly the request shape under test.
    assert update_request_gtfs_feed.seasonal is None

    api = OperationsApiImpl()
    response: Response = api.update_gtfs_feed(update_request_gtfs_feed)
    assert response.status_code == 200

    db_session.expire_all()
    db_feed = (
        db_session.query(Gtfsfeed)
        .filter(Gtfsfeed.stable_id == feed_mdb_40.stable_id)
        .one()
    )
    assert db_feed.note == feed_mdb_40.note
    assert db_feed.seasonal is True
