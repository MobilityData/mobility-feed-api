import pytest
from fastapi import HTTPException
from starlette.responses import Response

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
        ),
        redirects=[],
        operational_status_action="no_change",
        official=True,
    )


@pytest.fixture
def db_session():
    # Provide a database session fixture
    db = Database(feeds_database_url=default_db_url)
    with db.start_db_session() as session:
        yield session


@pytest.mark.asyncio
async def test_update_gtfs_feed_no_changes(update_request_gtfs_feed):
    api = OperationsApiImpl()
    response: Response = await api.update_gtfs_feed(update_request_gtfs_feed)
    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.usefixtures("update_request_gtfs_feed", "db_session")
async def test_update_gtfs_feed_field_change(update_request_gtfs_feed, db_session):
    update_request_gtfs_feed.feed_name = "New feed name"
    update_request_gtfs_feed.external_ids = [
        ExternalId(
            external_id="new_external_id",
            source="new_source",
        )
    ]
    api = OperationsApiImpl()
    response: Response = await api.update_gtfs_feed(update_request_gtfs_feed)
    assert response.status_code == 200

    db_feed = (
        db_session.query(Gtfsfeed)
        .filter(Gtfsfeed.stable_id == feed_mdb_40.stable_id)
        .one()
    )
    assert db_feed.feed_name == "New feed name"


@pytest.mark.asyncio
@pytest.mark.usefixtures("update_request_gtfs_feed", "db_session")
async def test_update_gtfs_feed_set_wip(update_request_gtfs_feed, db_session):
    update_request_gtfs_feed.operational_status_action = "wip"
    api = OperationsApiImpl()
    response: Response = await api.update_gtfs_feed(update_request_gtfs_feed)
    assert response.status_code == 200

    db_feed = (
        db_session.query(Gtfsfeed)
        .filter(Gtfsfeed.stable_id == feed_mdb_40.stable_id)
        .one()
    )
    assert db_feed.operational_status == "wip"


@pytest.mark.asyncio
@pytest.mark.usefixtures("update_request_gtfs_feed", "db_session")
async def test_update_gtfs_feed_set_wip_nochange(update_request_gtfs_feed, db_session):
    update_request_gtfs_feed.operational_status_action = "no_change"
    api = OperationsApiImpl()
    response: Response = await api.update_gtfs_feed(update_request_gtfs_feed)
    assert response.status_code == 204

    db_feed = (
        db_session.query(Gtfsfeed)
        .filter(Gtfsfeed.stable_id == feed_mdb_40.stable_id)
        .one()
    )
    assert db_feed.operational_status == "wip"


@pytest.mark.asyncio
@pytest.mark.usefixtures("update_request_gtfs_feed", "db_session")
async def test_update_gtfs_feed_set_published(update_request_gtfs_feed, db_session):
    update_request_gtfs_feed.operational_status_action = "published"
    api = OperationsApiImpl()
    response: Response = await api.update_gtfs_feed(update_request_gtfs_feed)
    assert response.status_code == 200

    db_feed = (
        db_session.query(Gtfsfeed)
        .filter(Gtfsfeed.stable_id == feed_mdb_40.stable_id)
        .one()
    )
    assert db_feed.operational_status == "published"


@pytest.mark.asyncio
@pytest.mark.usefixtures("update_request_gtfs_feed", "db_session")
async def test_update_gtfs_feed_set_unpublished(update_request_gtfs_feed, db_session):
    update_request_gtfs_feed.operational_status_action = "unpublished"
    api = OperationsApiImpl()
    response: Response = await api.update_gtfs_feed(update_request_gtfs_feed)
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
        await api.update_gtfs_feed(update_request_gtfs_feed)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Feed ID not found: invalid"


@pytest.mark.asyncio
async def test_update_gtfs_feed_official_field(update_request_gtfs_feed, db_session):
    """Test updating the official field of a GTFS feed."""
    update_request_gtfs_feed.official = True
    api = OperationsApiImpl()
    response: Response = await api.update_gtfs_feed(update_request_gtfs_feed)
    assert response.status_code == 204

    db_feed = (
        db_session.query(Gtfsfeed)
        .filter(Gtfsfeed.stable_id == feed_mdb_40.stable_id)
        .one()
    )
    assert db_feed.official is True
