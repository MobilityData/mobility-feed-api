import pytest
from starlette.responses import Response

from conftest import feed_mdb_41
from feeds_operations.impl.feeds_operations_impl import OperationsApiImpl
from feeds_gen.models.feed_status import FeedStatus
from feeds_gen.models.source_info import SourceInfo
from feeds_gen.models.update_request_gtfs_rt_feed import (
    UpdateRequestGtfsRtFeed,
)
from shared.database.database import Database
from shared.database_gen.sqlacodegen_models import Gtfsrealtimefeed
from test_shared.test_utils.database_utils import default_db_url


@pytest.fixture
def update_request_gtfs_rt_feed():
    return UpdateRequestGtfsRtFeed(
        id=feed_mdb_41.stable_id,
        status=FeedStatus(feed_mdb_41.status.lower()),
        external_ids=[],
        provider=feed_mdb_41.provider,
        feed_name=feed_mdb_41.feed_name,
        note=feed_mdb_41.note,
        feed_contact_email=feed_mdb_41.feed_contact_email,
        source_info=SourceInfo(
            producer_url=feed_mdb_41.producer_url,
            authentication_type=int(feed_mdb_41.authentication_type),
            authentication_info_url=feed_mdb_41.authentication_info_url,
            api_key_parameter_name=feed_mdb_41.api_key_parameter_name,
            license_url=feed_mdb_41.license_url,
        ),
        redirects=[],
        operational_status_action="no_change",
        entity_types=["vp"],
        official=True,
    )


@pytest.fixture
def db_session():
    # Provide a database session fixture
    db = Database(feeds_database_url=default_db_url)
    with db.start_db_session() as session:
        yield session


@pytest.mark.asyncio
@pytest.mark.usefixtures("update_request_gtfs_rt_feed", "db_session")
async def test_update_gtfs_feed_field_change(update_request_gtfs_rt_feed, db_session):
    update_request_gtfs_rt_feed.feed_name = "New feed name"
    api = OperationsApiImpl()
    response: Response = await api.update_gtfs_rt_feed(update_request_gtfs_rt_feed)
    assert response.status_code == 200

    db_feed = (
        db_session.query(Gtfsrealtimefeed)
        .filter(Gtfsrealtimefeed.stable_id == feed_mdb_41.stable_id)
        .one()
    )
    assert db_feed.feed_name == "New feed name"


@pytest.mark.asyncio
@pytest.mark.usefixtures("update_request_gtfs_rt_feed", "db_session")
async def test_update_gtfs_feed_static_change(update_request_gtfs_rt_feed, db_session):
    update_request_gtfs_rt_feed.feed_references = ["mdb-400"]
    api = OperationsApiImpl()
    response: Response = await api.update_gtfs_rt_feed(update_request_gtfs_rt_feed)
    assert response.status_code == 200

    db_feed = (
        db_session.query(Gtfsrealtimefeed)
        .filter(Gtfsrealtimefeed.stable_id == feed_mdb_41.stable_id)
        .one()
    )
    assert len(db_feed.gtfs_feeds) == 1
    feed = next(
        (feed for feed in db_feed.gtfs_feeds if feed.stable_id == "mdb-400"), None
    )
    assert feed is not None, "Feed with stable ID 'mdb-400' not found"


@pytest.mark.asyncio
@pytest.mark.usefixtures("update_request_gtfs_rt_feed", "db_session")
async def test_update_gtfs_rt_feed_set_wip(update_request_gtfs_rt_feed, db_session):
    update_request_gtfs_rt_feed.operational_status_action = "wip"
    api = OperationsApiImpl()
    response: Response = await api.update_gtfs_rt_feed(update_request_gtfs_rt_feed)
    assert response.status_code == 200

    db_feed = (
        db_session.query(Gtfsrealtimefeed)
        .filter(Gtfsrealtimefeed.stable_id == feed_mdb_41.stable_id)
        .one()
    )
    assert db_feed.operational_status == "wip"


@pytest.mark.asyncio
@pytest.mark.usefixtures("update_request_gtfs_rt_feed", "db_session")
async def test_update_gtfs_rt_feed_set_published(
    update_request_gtfs_rt_feed, db_session
):
    update_request_gtfs_rt_feed.operational_status_action = "published"
    api = OperationsApiImpl()
    response: Response = await api.update_gtfs_rt_feed(update_request_gtfs_rt_feed)
    assert response.status_code == 200

    db_feed = (
        db_session.query(Gtfsrealtimefeed)
        .filter(Gtfsrealtimefeed.stable_id == feed_mdb_41.stable_id)
        .one()
    )
    assert db_feed.operational_status == "published"


@pytest.mark.asyncio
@pytest.mark.usefixtures("update_request_gtfs_rt_feed", "db_session")
async def test_update_gtfs_rt_feed_set_unpublished(
    update_request_gtfs_rt_feed, db_session
):
    update_request_gtfs_rt_feed.operational_status_action = "unpublished"
    api = OperationsApiImpl()
    response: Response = await api.update_gtfs_rt_feed(update_request_gtfs_rt_feed)
    assert response.status_code == 200

    db_feed = (
        db_session.query(Gtfsrealtimefeed)
        .filter(Gtfsrealtimefeed.stable_id == feed_mdb_41.stable_id)
        .one()
    )
    assert db_feed.operational_status == "unpublished"


@pytest.mark.asyncio
async def test_update_gtfs_rt_feed_official_field(
    update_request_gtfs_rt_feed, db_session
):
    """Test updating the official field of a GTFS-RT feed."""
    update_request_gtfs_rt_feed.official = True
    api = OperationsApiImpl()
    response: Response = await api.update_gtfs_rt_feed(update_request_gtfs_rt_feed)
    assert response.status_code == 200

    db_feed = (
        db_session.query(Gtfsrealtimefeed)
        .filter(Gtfsrealtimefeed.stable_id == feed_mdb_41.stable_id)
        .one()
    )
    assert db_feed.official is True
